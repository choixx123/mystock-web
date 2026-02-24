import streamlit as st
import requests
import re
import time
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import xml.etree.ElementTree as ET
import urllib.parse

# 한국 표준시(KST) 설정
KST = timezone(timedelta(hours=9)) 

vip_dict = {
    "현대자동차": "005380.KS", "네이버": "035420.KS", "카카오": "035720.KS",
    "삼성전자": "005930.KS", "엔비디아": "NVDA", "테슬라": "TSLA",
    "애플": "AAPL", "마이크로소프트": "MSFT",
    "토요타 (일본)": "7203.T", "토요타 (미국)": "TM",
    "TSMC (대만)": "2330.TW", "TSMC (미국)": "TSM",
    "소니 (일본)": "6758.T", "소니 (미국)": "SONY",
    "알리바바 (홍콩)": "9988.HK", "알리바바 (미국)": "BABA",
    "ASML (네덜란드)": "ASML.AS", "ASML (미국)": "ASML",
    "루이비통 (프랑스)": "MC.PA", "루이비통 (미국)": "LVMUY"
}

def translate_to_english(text):
    if re.match(r'^[a-zA-Z0-9\.\-\s]+$', text.strip()): 
        return text, True 
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl=en&dt=t&q={text}"
        res = requests.get(url, timeout=3)
        return res.json()[0][0][0], True
    except: 
        return text, False 

def translate_to_korean(text):
    if not text or text == "N/A": 
        return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ko&dt=t&q={text}"
        res = requests.get(url, timeout=3)
        return res.json()[0][0][0]
    except: 
        return text

def calc_ma(prices, window):
    ma = []
    for i in range(len(prices)):
        if i < window - 1: 
            ma.append(None)
        else: 
            ma.append(sum(prices[i-window+1:i+1]) / window)
    return ma

def calc_rsi(prices, period=14):
    rsi = [None] * len(prices)
    if len(prices) < period + 1: return rsi
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(change if change > 0 else 0)
        losses.append(-change if change < 0 else 0)

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(prices)):
        if i > period:
            change = prices[i] - prices[i-1]
            gain = change if change > 0 else 0
            loss = -change if change < 0 else 0
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    return rsi

st.set_page_config(page_title="CEO 글로벌 터미널", page_icon="🌍", layout="wide")

st.markdown("""
    <style>
    .news-card { background: #f8f9fa; border-left: 4px solid #00b4d8; padding: 15px; border-radius: 5px; margin-bottom: 10px; }
    .news-title { font-size: 16px; font-weight: bold; color: #1E88E5 !important; text-decoration: none; }
    .company-profile { background: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 8px; margin-top: 15px; margin-bottom: 20px; font-size: 14px; color: #444; }
    </style>
""", unsafe_allow_html=True)

st.title("🌍 글로벌 주식 터미널")

# 세션 상태 초기화
if "search_input" not in st.session_state: 
    st.session_state.search_input = "테슬라"
if "vip_dropdown" not in st.session_state: 
    st.session_state.vip_dropdown = "🔽 주요 종목 선택"

def apply_vip_search():
    selected = st.session_state.vip_dropdown
    if selected != "🔽 주요 종목 선택":
        st.session_state.search_input = selected
        st.session_state.vip_dropdown = "🔽 주요 종목 선택" 

# 상단 검색 및 토글 UI
col1, col2, col3 = st.columns([4, 2, 2])
with col1: 
    st.text_input("🔍 직접 검색 (종목명/티커 입력 후 Enter)", key="search_input")
with col2: 
    st.selectbox("⭐ 빠른 검색", ["🔽 주요 종목 선택"] + list(vip_dict.keys()), key="vip_dropdown", on_change=apply_vip_search)
with col3:
    st.write("") 
    live_mode = st.toggle("🔴 라이브 모드 (5초 갱신)")
    use_candle = st.toggle("🕯️ 캔들 차트 모드", value=True)

search_term = st.session_state.search_input
timeframe = st.radio("⏳ 조회 기간 선택", ["1일", "1주일", "1달", "1년", "5년", "10년"], horizontal=True, index=2)

dashboard_container = st.empty()

if search_term:
    # 💡 야후 API 차단을 막기 위해 더 강력한 User-Agent 설정
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        with dashboard_container.container():
            original_name = search_term.strip()
            symbol = ""
            official_name = original_name
            
            # 1. 종목 심볼 확인 및 번역
            if original_name in vip_dict:
                symbol = vip_dict[original_name]
            else:
                english_name, trans_success = translate_to_english(original_name)
                if not trans_success:
                    st.error("⚠️ 번역 서버 지연. 코드를 직접 입력하세요.")
                    st.stop()
                    
                search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={english_name}"
                search_res = requests.get(search_url, headers=headers).json()
                
                if not search_res.get('quotes') or len(search_res['quotes']) == 0:
                    st.error(f"❌ '{original_name}' 정보가 없습니다.")
                    st.stop()
                    
                best_match = search_res['quotes'][0]
                symbol = best_match['symbol']
                official_name = best_match.get('shortname', english_name)

            # 2. 메타 데이터 및 상세 재무/기업 프로필 수집
            url_1y = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
            res_1y_data = requests.get(url_1y, headers=headers).json()
            
            market_cap_str, pe_ratio_str, div_yield_str = "N/A", "N/A", "배당 없음"
            sector_kr, industry_kr, summary_kr = "정보 없음", "정보 없음", "기업 설명이 제공되지 않았습니다."
            
            # 💡 [핵심 수정 1] 시총, PER, 배당률을 가장 안정적인 v7 quote API에서 가져오기
            try:
                quote_url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
                quote_res = requests.get(quote_url, headers=headers).json()
                if quote_res.get('quoteResponse', {}).get('result'):
                    q_data = quote_res['quoteResponse']['result'][0]
                    
                    # 시가총액 포맷팅 (조 단위, 빌리언/밀리언 단위 깔끔하게)
                    mc_raw = q_data.get('marketCap')
                    if mc_raw:
                        if symbol.endswith(".KS") or symbol.endswith(".KQ"):
                            market_cap_str = f"{mc_raw / 1000000000000:.2f}조 원"
                        else:
                            if mc_raw >= 1000000000000:
                                market_cap_str = f"{mc_raw / 1000000000000:.2f}T (조)" 
                            elif mc_raw >= 1000000000:
                                market_cap_str = f"{mc_raw / 1000000000:.2f}B (십억)" 
                            else:
                                market_cap_str = f"{mc_raw / 1000000:.2f}M (백만)" 
                                
                    pe_raw = q_data.get('trailingPE')
                    if pe_raw: pe_ratio_str = f"{pe_raw:.2f} 배"
                    
                    div_raw = q_data.get('trailingAnnualDividendYield')
                    if div_raw: div_yield_str = f"{div_raw * 100:.2f}%"
            except:
                pass

            # 💡 [핵심 수정 2] 기업 개요를 더 확실한 assetProfile 모듈에서 가져오기
            try:
                profile_url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=assetProfile"
                prof_res = requests.get(profile_url, headers=headers).json()
                if prof_res.get('quoteSummary', {}).get('result'):
                    profile_data = prof_res['quoteSummary']['result'][0].get('assetProfile', {})
                    sector = profile_data.get('sector', 'N/A')
                    industry = profile_data.get('industry', 'N/A')
                    summary_eng = profile_data.get('longBusinessSummary', '')
                    
                    if sector != 'N/A': sector_kr = translate_to_korean(sector)
                    if industry != 'N/A': industry_kr = translate_to_korean(industry)
                    if summary_eng:
                        summary_kr = translate_to_korean(summary_eng[:350] + ("..." if len(summary_eng) > 350 else ""))
            except:
                pass
            
            # 주가 데이터 수집
            if 'chart' in res_1y_data and res_1y_data['chart']['result']:
                result_1y = res_1y_data['chart']['result'][0]
                meta = result_1y['meta']
                quotes_1y = result_1y['indicators']['quote'][0]
                
                valid_closes = [p for p in quotes_1y.get('close', []) if p is not None]
                valid_highs = [h for h in quotes_1y.get('high', []) if h is not None]
                valid_lows = [l for l in quotes_1y.get('low', []) if l is not None]
                
                price = meta.get('regularMarketPrice', valid_closes[-1] if valid_closes else 0)
                prev_close = meta.get('previousClose', valid_closes[-2] if len(valid_closes) >= 2 else price)
                today_volume = meta.get('regularMarketVolume', 0)
                currency = meta.get('currency', 'USD') 
                
                day_change = price - prev_close
                day_change_pct = (day_change / prev_close) * 100 if prev_close else 0
                historical_high = max(valid_highs) if valid_highs else 0
                historical_low = min(valid_lows) if valid_lows else 0
                high_52 = max(historical_high, price)
                low_52 = min(historical_low, price) if historical_low > 0 else price
            else:
                st.error("❌ 데이터를 불러올 수 없습니다.")
                st.stop()

            # 3. 통화 포맷팅
            c_symbol = "₩" if currency == "KRW" else "＄" if currency == "USD" else "€" if currency == "EUR" else "¥" if currency == "JPY" else f"{currency} "
            
            if currency == "KRW":
                price_str = f"{int(price):,} 원"
                change_val_str = f"{day_change:+,.0f} 원"
                highlow_52_str = f"{int(high_52):,} / {int(low_52):,} 원" 
            else:
                price_str = f"{c_symbol}{price:,.2f}"
                change_val_str = f"{day_change:+,.2f} {c_symbol}" 
                highlow_52_str = f"{c_symbol}{high_52:,.2f} / {c_symbol}{low_52:,.2f}" 
                if market_cap_str != "N/A" and "원" not in market_cap_str:
                    market_cap_str = f"{c_symbol}{market_cap_str}"

            # 4. 상단 지표(KPI) 및 🏢 기업 상세 정보 렌더링
            st.subheader(f"{official_name} ({symbol})")
            
            st.markdown(f"""
                <div class="company-profile">
                    <strong>🏢 업종:</strong> {sector_kr} / {industry_kr} <br>
                    <strong>📝 개요:</strong> {summary_kr}
                </div>
            """, unsafe_allow_html=True)

            # 💡 [핵심 수정 3] 52주 최고/최저가 긴 칸(kpi2)에 1.6배 더 넓은 공간을 할당해서 '...' 방지
            kpi1, kpi2, kpi3, kpi4 = st.columns([1.0, 1.6, 1.1, 1.3])
            with kpi1: st.metric(label=f"💰 현재가", value=price_str, delta=f"{day_change_pct:+.2f}%")
            with kpi2: st.metric(label="⚖️ 52주 최고/최저", value=highlow_52_str if high_52 else "데이터 없음")
            with kpi3: st.metric(label="📊 거래량", value=f"{int(today_volume):,} 주")
            with kpi4: 
                if currency != "KRW":
                    try:
                        ex_rate = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X", headers=headers).json()['chart']['result'][0]['meta']['regularMarketPrice']
                        st.metric(label="🇰🇷 원화 환산가", value=f"약 {int(price * ex_rate):,} 원")
                    except:
                        st.metric(label="🇰🇷 원화 환산가", value="계산 불가")
                else:
                    st.empty() 

            st.write("") 
            # 재무 지표 칸 비율도 보기 좋게 조정
            fin1, fin2, fin3, fin4 = st.columns([1.2, 1.0, 1.0, 1.8])
            with fin1: st.metric(label="🏢 시가총액 (규모)", value=market_cap_str)
            with fin2: st.metric(label="📈 PER (수익성)", value=pe_ratio_str)
            with fin3: st.metric(label="💸 배당수익률", value=div_yield_str)
            with fin4: st.empty()

            # 5. 차트 데이터 수집
            st.markdown("---")
            fetch_range_map = {"1일": "5d", "1주일": "1mo", "1달": "6mo", "1년": "2y", "5년": "10y", "10년": "max"}
            interval_map = {"1일": "5m", "1주일": "15m", "1달": "1d", "1년": "1d", "5년": "1wk", "10년": "1mo"}
            
            chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={fetch_range_map[timeframe]}&interval={interval_map[timeframe]}"
            chart_res = requests.get(chart_url, headers=headers).json()['chart']['result'][0]
            
            dt_objects = [datetime.fromtimestamp(ts, KST) for ts in chart_res['timestamp']]
            quote = chart_res['indicators']['quote'][0]
            opens = quote.get('open', [])
            highs = quote.get('high', [])
            lows = quote.get('low', [])
            closes = quote.get('close', [])
            volumes = quote.get('volume', [])
            
            clean_data = []
            for i in range(len(dt_objects)):
                if closes[i] is not None:
                    v = volumes[i] if volumes[i] is not None else 0
                    clean_data.append((dt_objects[i], opens[i], highs[i], lows[i], closes[i], v))

            full_prices = [row[4] for row in clean_data]
            ma20_full = calc_ma(full_prices, 20)
            ma60_full = calc_ma(full_prices, 60)
            rsi_full = calc_rsi(full_prices, 14) 

            f_dates, f_opens, f_highs, f_lows, f_closes, f_volumes, f_ma20, f_ma60, f_rsi = [], [], [], [], [], [], [], [], []

            if timeframe == "1일" and len(clean_data) > 0:
                session_start_idx = 0
                for i in range(len(clean_data) - 1, 0, -1):
                    time_diff = clean_data[i][0] - clean_data[i-1][0]
                    if time_diff.total_seconds() > 4 * 3600: 
                        session_start_idx = i
                        break
                
                for i in range(session_start_idx, len(clean_data)):
                    f_dates.append(clean_data[i][0])
                    f_opens.append(clean_data[i][1])
                    f_highs.append(clean_data[i][2])
                    f_lows.append(clean_data[i][3])
                    f_closes.append(clean_data[i][4])
                    f_volumes.append(clean_data[i][5])
                    f_ma20.append(ma20_full[i])
                    f_ma60.append(ma60_full[i])
                    f_rsi.append(rsi_full[i])
                    
            elif timeframe != "1일":
                cutoff_map = {"1주일": 7, "1달": 30, "1년": 365, "5년": 365*5, "10년": 365*10}
                cutoff_days = cutoff_map.get(timeframe, 30)
                cutoff_date = datetime.now(KST) - timedelta(days=cutoff_days)
                
                for i in range(len(clean_data)):
                    if clean_data[i][0] >= cutoff_date:
                        f_dates.append(clean_data[i][0])
                        f_opens.append(clean_data[i][1])
                        f_highs.append(clean_data[i][2])
                        f_lows.append(clean_data[i][3])
                        f_closes.append(clean_data[i][4])
                        f_volumes.append(clean_data[i][5])
                        f_ma20.append(ma20_full[i])
                        f_ma60.append(ma60_full[i])
                        f_rsi.append(rsi_full[i])

            # 7. 차트 그리기 
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True, 
                vertical_spacing=0.03, row_heights=[0.75, 0.25],
                specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
            )
            
            is_kr = symbol.endswith(".KS") or symbol.endswith(".KQ")
            up_color = '#ff4b4b' if is_kr else '#00cc96'
            down_color = '#00b4d8' if is_kr else '#ff4b4b'

            if use_candle:
                fig.add_trace(go.Candlestick(
                    x=f_dates, open=f_opens, high=f_highs, low=f_lows, close=f_closes, 
                    increasing_line_color=up_color, decreasing_line_color=down_color, name='캔들'
                ), row=1, col=1, secondary_y=False)
            else:
                fig.add_trace(go.Scatter(
                    x=f_dates, y=f_closes, mode='lines', name='주가', 
                    line=dict(color='#00b4d8', width=3), connectgaps=True
                ), row=1, col=1, secondary_y=False)

            if timeframe in ["1일", "1주일"]:
                fig.add_trace(go.Scatter(x=f_dates, y=f_ma20, mode='lines', name='20선', line=dict(color='#ff9900', width=1.5, dash='dash')), row=1, col=1, secondary_y=False)
                fig.add_trace(go.Scatter(x=f_dates, y=f_ma60, mode='lines', name='60선', line=dict(color='#9933cc', width=1.5, dash='dash')), row=1, col=1, secondary_y=False)
            elif timeframe == "1달":
                fig.add_trace(go.Scatter(x=f_dates, y=f_ma20, mode='lines', name='20일선', line=dict(color='#ff9900', width=1.5, dash='dash')), row=1, col=1, secondary_y=False)
            elif timeframe == "1년":
                fig.add_trace(go.Scatter(x=f_dates, y=f_ma20, mode='lines', name='20일선', line=dict(color='#ff9900', width=1.5, dash='dash')), row=1, col=1, secondary_y=False)
                fig.add_trace(go.Scatter(x=f_dates, y=f_ma60, mode='lines', name='60일선', line=dict(color='#9933cc', width=1.5, dash='dash')), row=1, col=1, secondary_y=False)
            elif timeframe == "5년":
                fig.add_trace(go.Scatter(x=f_dates, y=f_ma20, mode='lines', name='20주선', line=dict(color='#ff9900', width=1.5, dash='dash')), row=1, col=1, secondary_y=False)
                fig.add_trace(go.Scatter(x=f_dates, y=f_ma60, mode='lines', name='60주선', line=dict(color='#9933cc', width=1.5, dash='dash')), row=1, col=1, secondary_y=False)
            elif timeframe == "10년":
                fig.add_trace(go.Scatter(x=f_dates, y=f_ma20, mode='lines', name='20개월선', line=dict(color='#ff9900', width=1.5, dash='dash')), row=1, col=1, secondary_y=False)
                fig.add_trace(go.Scatter(x=f_dates, y=f_ma60, mode='lines', name='60개월선', line=dict(color='#9933cc', width=1.5, dash='dash')), row=1, col=1, secondary_y=False)

            vol_colors = []
            f_amounts_str = [] 
            
            for i in range(len(f_closes)):
                if i > 0 and f_closes[i] < f_closes[i-1]:
                    vol_colors.append(down_color)
                else:
                    vol_colors.append(up_color)
                
                amount = f_closes[i] * f_volumes[i]
                if currency == "KRW":
                    f_amounts_str.append(f"{int(amount):,} 원")
                else:
                    f_amounts_str.append(f"{c_symbol}{int(amount):,}")
                    
            fig.add_trace(go.Bar(
                x=f_dates, y=f_volumes, name='거래량', marker_color=vol_colors, opacity=0.3,
                customdata=f_amounts_str, 
                hovertemplate="거래량: %{y:,} 주<br>거래 대금: %{customdata}<extra></extra>" 
            ), row=1, col=1, secondary_y=True)
            
            fig.add_trace(go.Scatter(
                x=f_dates, y=f_rsi, mode='lines', name='RSI(14)', 
                line=dict(color='#9c27b0', width=1.5)
            ), row=2, col=1)
            
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1, annotation_text="과열 (70)", annotation_position="top right")
            fig.add_hline(y=30, line_dash="dot", line_color="blue", row=2, col=1, annotation_text="침체 (30)", annotation_position="bottom right")

            fig.update_layout(
                title=f"📈 {official_name} 차트 & 보조지표", hovermode="x unified", margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), xaxis_rangeslider_visible=False,
                height=700 
            )
            
            fig.update_yaxes(title_text=f"주가 ({currency})", row=1, col=1, secondary_y=False)
            max_vol = max(f_volumes) if f_volumes and len(f_volumes) > 0 else 0
            fig.update_yaxes(showgrid=False, range=[0, max_vol * 4 if max_vol > 0 else 100], row=1, col=1, secondary_y=True)
            fig.update_yaxes(title_text="RSI", range=[0, 100], tickvals=[30, 50, 70], row=2, col=1)
            
            if timeframe in ["1달", "1년"]:
                fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

            st.plotly_chart(fig, use_container_width=True)

            # --- 📰 진짜 한국 언론사 뉴스 가져오기 ---
            st.markdown("---")
            st.markdown(f"### 📰 {original_name} 최신 뉴스")
            
            try:
                clean_search_term = original_name.split('(')[0].strip()
                search_query = f"{clean_search_term} 주식"
                encoded_query = urllib.parse.quote(search_query)
                
                news_url = f"https://news.google.com/rss/search?q={encoded_query}+when:7d&hl=ko&gl=KR&ceid=KR:ko"
                news_res = requests.get(news_url, headers=headers)
                
                root = ET.fromstring(news_res.content)
                items = root.findall('.//item')
                
                if items:
                    for item in items[:5]:
                        title = item.find('title').text
                        link = item.find('link').text
                        source_elem = item.find('source')
                        source = source_elem.text if source_elem is not None else "구글 뉴스"
                        
                        if " - " in title:
                            title = " - ".join(title.split(" - ")[:-1])
                            
                        st.markdown(f"""
                            <div class="news-card">
                                <a class="news-title" href="{link}" target="_blank">
                                    📰 {title}
                                </a>
                                <div style="font-size: 13px; color: #666; margin-top: 5px;">
                                    🏢 출처: {source}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info(f"💡 현재 '{clean_search_term}'와 관련된 주식 뉴스가 없습니다.")
            except Exception as e:
                st.warning("⚠️ 뉴스를 불러오는 중 오류가 발생했습니다.")

    except Exception as e:
        dashboard_container.error(f"❌ 데이터 연산 오류: {e}")

# 라이브 모드 실행
if live_mode and search_term:
    time.sleep(5)
    st.rerun()
    