import streamlit as st
import requests
import re
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 🔥 CEO 전용 주요 종목 장부
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

def calc_ma(prices, window):
    ma = []
    for i in range(len(prices)):
        if i < window - 1:
            ma.append(None)
        else:
            ma.append(sum(prices[i-window+1:i+1]) / window)
    return ma

# 🔥 RSI (상대강도지수) 계산 함수
def calc_rsi(prices, period=14):
    rsi = [None] * len(prices)
    if len(prices) < period + 1:
        return rsi
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        rsi[period] = 100
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100 - (100 / (1 + rs))
        
    for i in range(period + 1, len(prices)):
        avg_gain = (avg_gain * (period - 1) + gains[i-1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i-1]) / period
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    return rsi

st.set_page_config(page_title="CEO 글로벌 터미널", page_icon="🌍", layout="wide")
st.title("🌍 글로벌 주식 터미널")

if "search_input" not in st.session_state:
    st.session_state.search_input = "테슬라"
if "vip_dropdown" not in st.session_state:
    st.session_state.vip_dropdown = "🔽 주요 종목 선택"

def apply_vip_search():
    selected = st.session_state.vip_dropdown
    if selected != "🔽 주요 종목 선택":
        st.session_state.search_input = selected
        st.session_state.vip_dropdown = "🔽 주요 종목 선택" 

col1, col2, col3 = st.columns([4, 2, 2])
with col1:
    st.text_input("🔍 직접 검색 (종목명/티커 입력 후 Enter)", key="search_input")
with col2:
    st.selectbox("⭐ 빠른 검색", ["🔽 주요 종목 선택"] + list(vip_dict.keys()), key="vip_dropdown", on_change=apply_vip_search)
with col3:
    st.write("") 
    st.write("")
    live_mode = st.toggle("🔴 라이브 모드 (5초 갱신)")

search_term = st.session_state.search_input
timeframe = st.radio("⏳ 조회 기간 선택", ["1일", "1주일", "1달", "6달", "1년", "3년", "5년", "10년"], horizontal=True, index=3)

if search_term:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        original_name = search_term.strip()
        symbol = ""
        official_name = original_name
        
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

        # 🔥 종목 상세 정보 (재무 지표) 가져오기
        quote_url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
        quote_data = requests.get(quote_url, headers=headers).json()
        quote_result = quote_data['quoteResponse']['result'][0] if quote_data['quoteResponse']['result'] else {}

        market_cap = quote_result.get('marketCap', 0)
        pe_ratio = quote_result.get('trailingPE', None)
        div_yield = quote_result.get('trailingAnnualDividendYield', 0) * 100

        # 주가 및 기본 정보 가져오기
        url_1y = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
        res_1y_data = requests.get(url_1y, headers=headers).json()
        
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
            
            high_52 = max(valid_highs) if valid_highs else price
            low_52 = min(valid_lows) if valid_lows else price
        else:
            st.error("❌ 야후 파이낸스에서 종목 데이터를 불러올 수 없습니다.")
            st.stop()

        # 🔥 국가별 캔들 색상 로직 (천재적인 아이디어 반영!)
        is_korean = symbol.endswith('.KS') or symbol.endswith('.KQ')
        inc_color = '#ff4b4b' if is_korean else '#00cc96' # 한국: 빨강 / 해외: 초록
        dec_color = '#00b4d8' if is_korean else '#ff4b4b' # 한국: 파랑 / 해외: 빨강

        st.subheader(f"{official_name} ({symbol})")
        
        # --- 💰 1단: 가격 및 거래량 요약판 ---
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        if currency == "KRW":
            kpi1.metric(label=f"💰 현재가", value=f"{int(price):,} 원")
            kpi2.metric(label="📈 전일 대비", value=f"{day_change:+,.0f} 원", delta=f"{day_change_pct:+.2f}%")
            kpi3.metric(label="📊 거래량", value=f"{int(today_volume):,} 주")
            kpi4.metric(label="⚖️ 52주 고/저", value=f"{int(high_52):,} / {int(low_52):,}")
            mc_str = f"{int(market_cap / 100000000000):,}조 원" if market_cap else "N/A"
        else:
            kpi1.metric(label=f"💰 현재가 ({currency})", value=f"$ {price:,.2f}")
            kpi2.metric(label="📈 전일 대비", value=f"{day_change:+,.2f} $", delta=f"{day_change_pct:+.2f}%")
            kpi3.metric(label="📊 거래량", value=f"{int(today_volume):,} 주")
            kpi4.metric(label="⚖️ 52주 고/저", value=f"${high_52:,.2f} / ${low_52:,.2f}")
            mc_str = f"$ {market_cap / 1000000000:,.2f}B" if market_cap else "N/A"

        # --- 🏢 2단: 뼈대 꿰뚫는 재무 지표 (깔끔하게 분리) ---
        with st.expander("🏢 기업 펀더멘털 (가치 지표)", expanded=True):
            f1, f2, f3 = st.columns(3)
            f1.metric("👑 시가총액 (Market Cap)", mc_str)
            f2.metric("⏱️ PER (주가수익비율)", f"{pe_ratio:.2f} 배" if pe_ratio else "N/A")
            f3.metric("💸 배당수익률 (Dividend Yield)", f"{div_yield:.2f} %" if div_yield > 0 else "배당 없음")

        # --- 📈 차트 그리기 ---
        st.markdown("---")
        try:
            fetch_range_map = {"1일": "5d", "1주일": "1mo", "1달": "6mo", "6달": "1y", "1년": "2y", "3년": "10y", "5년": "10y", "10년": "max"}
            interval_map = {"1일": "5m", "1주일": "15m", "1달": "1d", "6달": "1d", "1년": "1d", "3년": "1wk", "5년": "1wk", "10년": "1mo"}
            
            selected_range = fetch_range_map[timeframe]
            selected_interval = interval_map[timeframe]
            
            chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={selected_range}&interval={selected_interval}"
            chart_res = requests.get(chart_url, headers=headers).json()
            
            result = chart_res['chart']['result'][0]
            timestamps = result['timestamp']
            quote = result['indicators']['quote'][0]
            
            open_p = quote.get('open', [0]*len(timestamps))
            high_p = quote.get('high', [0]*len(timestamps))
            low_p = quote.get('low', [0]*len(timestamps))
            close_p = quote['close']
            volumes = quote.get('volume', [0]*len(timestamps))
            
            dt_objects = [datetime.fromtimestamp(ts) for ts in timestamps]
            clean_data = [(d, o, h, l, c, v if v else 0) for d, o, h, l, c, v in zip(dt_objects, open_p, high_p, low_p, close_p, volumes) if c is not None]

            full_prices = [x[4] for x in clean_data]
            ma20_full = calc_ma(full_prices, 20)
            ma60_full = calc_ma(full_prices, 60)
            rsi_full = calc_rsi(full_prices, 14) # 🔥 RSI 계산 완료!

            if timeframe == "1일":
                cutoff_date = datetime(clean_data[-1][0].year, clean_data[-1][0].month, clean_data[-1][0].day) if clean_data else datetime.now() - timedelta(days=1)
            else:
                cutoff_map = {"1주일": 7, "1달": 30, "6달": 180, "1년": 365, "3년": 365*3, "5년": 365*5, "10년": 365*10}
                cutoff_date = datetime.now() - timedelta(days=cutoff_map[timeframe])

            f_dates, f_opens, f_highs, f_lows, f_closes, f_vols = [], [], [], [], [], []
            f_ma20, f_ma60, f_rsi = [], [], []

            for i in range(len(clean_data)):
                if clean_data[i][0] >= cutoff_date:
                    f_dates.append(clean_data[i][0])
                    f_opens.append(clean_data[i][1])
                    f_highs.append(clean_data[i][2])
                    f_lows.append(clean_data[i][3])
                    f_closes.append(clean_data[i][4])
                    f_vols.append(clean_data[i][5])
                    f_ma20.append(ma20_full[i])
                    f_ma60.append(ma60_full[i])
                    f_rsi.append(rsi_full[i])

            # 🔥 3단 분리 깔끔한 차트 레이아웃 생성!
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
            
            # 1층: 캔들 차트 & 이평선
            fig.add_trace(go.Candlestick(x=f_dates, open=f_opens, high=f_highs, low=f_lows, close=f_closes, 
                                         increasing_line_color=inc_color, decreasing_line_color=dec_color, name='주가'), row=1, col=1)
            fig.add_trace(go.Scatter(x=f_dates, y=f_ma20, mode='lines', name='20선', line=dict(color='#ff9900', width=1.5, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=f_dates, y=f_ma60, mode='lines', name='60선', line=dict(color='#9933cc', width=1.5, dash='dash')), row=1, col=1)

            # 2층: 거래량 (캔들 색깔과 깔맞춤)
            vol_colors = [inc_color if i==0 or f_closes[i] >= f_closes[i-1] else dec_color for i in range(len(f_closes))]
            fig.add_trace(go.Bar(x=f_dates, y=f_vols, marker_color=vol_colors, name='거래량', opacity=0.5), row=2, col=1)
            
            # 3층: RSI 지표
            fig.add_trace(go.Scatter(x=f_dates, y=f_rsi, mode='lines', name='RSI(14)', line=dict(color='#ab63fa', width=2)), row=3, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1, annotation_text="과열(70)", annotation_position="top right")
            fig.add_hline(y=30, line_dash="dot", line_color="blue", row=3, col=1, annotation_text="침체(30)", annotation_position="bottom right")
            
            fig.update_layout(
                title=f"📈 {official_name} 전문가용 분석 차트 ({timeframe})",
                xaxis_rangeslider_visible=False, # 캔들 차트 하단 지저분한 슬라이더 제거
                hovermode="x unified", margin=dict(l=0, r=0, t=40, b=0),
                showlegend=False # 깔끔함을 위해 레전드 숨김 (마우스 올리면 다 보임)
            )
            
            if timeframe in ["1일", "1주일", "1달", "6달", "1년"]:
                fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

            st.plotly_chart(fig, use_container_width=True)
            
            # --- 📰 4단: 최신 종목 뉴스 (클릭 시 이동) ---
            st.markdown("### 📰 실시간 관련 뉴스 속보")
            news_items = search_res.get('news', [])
            if news_items:
                for news in news_items[:4]: # 가장 최신 4개만 깔끔하게 출력
                    title = news.get('title', '제목 없음')
                    publisher = news.get('publisher', '알 수 없음')
                    link = news.get('link', '#')
                    
                    st.markdown(f"""
                    <div style="padding: 10px; border-left: 5px solid #00b4d8; background-color: rgba(0, 180, 216, 0.1); margin-bottom: 10px; border-radius: 5px;">
                        <h5 style="margin: 0;"><a href="{link}" target="_blank" style="text-decoration: none; color: inherit;">🔗 {title}</a></h5>
                        <p style="margin: 5px 0 0 0; font-size: 0.8em; color: gray;">출처: {publisher}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("현재 이 종목과 관련된 최신 뉴스가 없습니다.")

            if live_mode:
                if "live_on" not in st.session_state:
                    st.toast("🔴 라이브 모드 ON: 주가 및 뉴스 실시간 갱신 중!", icon="⚡")
                    st.session_state.live_on = True 
                time.sleep(5)
                st.rerun()
            else:
                st.session_state.pop("live_on", None) 
                
        except Exception as e:
            st.info(f"차트 데이터를 불러오는 데 실패했습니다: {e}")
            
    except Exception as e:
        st.error(f"❌ 시스템 에러 발생: {e}")
        