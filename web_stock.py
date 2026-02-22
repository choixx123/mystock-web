import streamlit as st
import requests
import re
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 🔥 CEO 전용 VIP 장부
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

st.set_page_config(page_title="CEO 글로벌 터미널", page_icon="🌍", layout="wide")
st.title("🌍 글로벌 주식 터미널 (Pro Max Version 🚀)")

if "search_input" not in st.session_state:
    st.session_state.search_input = "테슬라"
if "vip_dropdown" not in st.session_state:
    st.session_state.vip_dropdown = "🔽 VIP 종목 선택"

def apply_vip_search():
    selected = st.session_state.vip_dropdown
    if selected != "🔽 VIP 종목 선택":
        st.session_state.search_input = selected
        st.session_state.vip_dropdown = "🔽 VIP 종목 선택" 

col1, col2, col3 = st.columns([4, 2, 2])
with col1:
    st.text_input("🔍 직접 검색 (종목명/티커 입력 후 Enter)", key="search_input")
with col2:
    st.selectbox("⭐ 빠른 검색", ["🔽 VIP 종목 선택"] + list(vip_dict.keys()), key="vip_dropdown", on_change=apply_vip_search)
with col3:
    st.write("") 
    st.write("")
    live_mode = st.toggle("🔴 라이브 모드 (5초 갱신)")

search_term = st.session_state.search_input
timeframe = st.radio("⏳ 조회 기간 선택", ["1주일", "1달", "3달", "6달", "1년", "3년", "5년", "10년"], horizontal=True, index=2)

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
            
            prev_close = meta.get('previousClose')
            if not prev_close:
                if len(valid_closes) >= 2:
                    prev_close = valid_closes[-2]
                else:
                    prev_close = price
            
            # 🛠️ [패치 적용] 실시간 거래량 지속 갱신!
            today_volume = meta.get('regularMarketVolume', 0)
            currency = meta.get('currency', 'USD')
            
            day_change = price - prev_close
            day_change_pct = (day_change / prev_close) * 100 if prev_close else 0
            
            # 🛠️ [패치 적용] 과거 52주 최고/최저 데이터 추출 후, 현재 '라이브 가격'과 무한 배틀!
            historical_high = max(valid_highs) if valid_highs else 0
            historical_low = min(valid_lows) if valid_lows else 0
            
            # 라이브 가격이 기존 최고가를 뚫으면 즉시 반영!
            high_52 = max(historical_high, price)
            # 라이브 가격이 기존 최저가를 뚫으면 즉시 반영!
            low_52 = min(historical_low, price) if historical_low > 0 else price
            
        else:
            st.error("❌ 야후 파이낸스에서 종목 데이터를 불러올 수 없습니다.")
            st.stop()

        if currency == "KRW":
            price_str = f"{int(price):,} 원"
            change_val_str = f"{day_change:+,.0f} 원"
            highlow_52_str = f"{int(high_52):,} / {int(low_52):,} 원" 
        else:
            curr_symbol = "＄"
            price_str = f"{curr_symbol} {price:,.2f}"
            change_val_str = f"{day_change:+,.2f} {curr_symbol}" 
            highlow_52_str = f"{curr_symbol}{high_52:,.2f} / {curr_symbol}{low_52:,.2f}" 

        st.subheader(f"{official_name} ({symbol})")
        
        # --- 💰 상단 요약판 ---
        if currency == "KRW":
            kpi1, kpi2, kpi4, kpi5 = st.columns([1.1, 1.3, 1.3, 2.0]) 
            kpi1.metric(label=f"💰 현재가", value=price_str)
            kpi2.metric(label="📈 전일 대비 상승률", value=change_val_str, delta=f"{day_change_pct:+.2f}%")
            kpi4.metric(label="📊 당일 총 거래량", value=f"{int(today_volume):,} 주")
            if high_52 and low_52:
                kpi5.metric(label="⚖️ 52주 최고/최저", value=highlow_52_str)
            else:
                kpi5.metric(label="⚖️ 52주 최고/최저", value="데이터 없음")
        else:
            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns([1.0, 1.2, 1.2, 1.2, 1.8]) 
            kpi1.metric(label=f"💰 현재가 ({currency})", value=price_str)
            kpi2.metric(label="📈 전일 대비 상승률", value=change_val_str, delta=f"{day_change_pct:+.2f}%")
            try:
                ex_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{currency}KRW=X"
                ex_rate = requests.get(ex_url, headers=headers).json()['chart']['result'][0]['meta']['regularMarketPrice']
                kpi3.metric(label="🇰🇷 원화 환산가", value=f"약 {int(price * ex_rate):,} 원")
            except:
                kpi3.metric(label="🇰🇷 원화 환산가", value="계산 불가")
            kpi4.metric(label="📊 당일 총 거래량", value=f"{int(today_volume):,} 주")
            if high_52 and low_52:
                kpi5.metric(label="⚖️ 52주 최고/최저", value=highlow_52_str)
            else:
                kpi5.metric(label="⚖️ 52주 최고/최저", value="데이터 없음")

        # --- 📈 차트 그리기 ---
        st.markdown("---")
        try:
            fetch_range_map = {"1주일": "1mo", "1달": "6mo", "3달": "1y", "6달": "1y", "1년": "2y", "3년": "10y", "5년": "10y", "10년": "max"}
            interval_map = {"1주일": "15m", "1달": "1d", "3달": "1d", "6달": "1d", "1년": "1d", "3년": "1wk", "5년": "1wk", "10년": "1mo"}
            
            selected_range = fetch_range_map[timeframe]
            selected_interval = interval_map[timeframe]
            
            chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={selected_range}&interval={selected_interval}"
            chart_res = requests.get(chart_url, headers=headers).json()
            
            result = chart_res['chart']['result'][0]
            timestamps = result['timestamp']
            close_prices = result['indicators']['quote'][0]['close']
            volumes = result['indicators']['quote'][0].get('volume', [0]*len(close_prices))
            
            dt_objects = [datetime.fromtimestamp(ts) for ts in timestamps]
            clean_data = [(d, p, v if v else 0) for d, p, v in zip(dt_objects, close_prices, volumes) if p is not None]

            full_prices = [x[1] for x in clean_data]
            ma20_full = calc_ma(full_prices, 20)
            ma60_full = calc_ma(full_prices, 60)

            cutoff_map = {"1주일": 7, "1달": 30, "3달": 90, "6달": 180, "1년": 365, "3년": 365*3, "5년": 365*5, "10년": 365*10}
            cutoff_date = datetime.now() - timedelta(days=cutoff_map[timeframe])

            filtered_dates, filtered_prices, filtered_volumes = [], [], []
            filtered_ma20, filtered_ma60 = [], []

            for i in range(len(clean_data)):
                if clean_data[i][0] >= cutoff_date:
                    if timeframe == "1주일":
                        d_str = clean_data[i][0].strftime('%Y-%m-%d %H:%M')
                    elif timeframe == "10년":
                        d_str = clean_data[i][0].strftime('%Y-%m')
                    else:
                        d_str = clean_data[i][0].strftime('%Y-%m-%d')
                    
                    filtered_dates.append(d_str)
                    filtered_prices.append(clean_data[i][1])
                    filtered_volumes.append(clean_data[i][2])
                    filtered_ma20.append(ma20_full[i])
                    filtered_ma60.append(ma60_full[i])

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=filtered_dates, y=filtered_prices, mode='lines', name='주가', line=dict(color='#00b4d8', width=3)), secondary_y=False)

            if timeframe == "1달":
                fig.add_trace(go.Scatter(x=filtered_dates, y=filtered_ma20, mode='lines', name='20일선', line=dict(color='#ff9900', width=1.5, dash='dot')), secondary_y=False)
            elif timeframe in ["3달", "6달", "1년"]:
                fig.add_trace(go.Scatter(x=filtered_dates, y=filtered_ma20, mode='lines', name='20일선', line=dict(color='#ff9900', width=1.5, dash='dot')), secondary_y=False)
                fig.add_trace(go.Scatter(x=filtered_dates, y=filtered_ma60, mode='lines', name='60일선', line=dict(color='#9933cc', width=1.5, dash='dot')), secondary_y=False)
            elif timeframe in ["3년", "5년"]:
                fig.add_trace(go.Scatter(x=filtered_dates, y=filtered_ma20, mode='lines', name='20주선', line=dict(color='#ff9900', width=1.5, dash='dot')), secondary_y=False)
                fig.add_trace(go.Scatter(x=filtered_dates, y=filtered_ma60, mode='lines', name='60주선', line=dict(color='#9933cc', width=1.5, dash='dot')), secondary_y=False)
            elif timeframe == "10년":
                fig.add_trace(go.Scatter(x=filtered_dates, y=filtered_ma20, mode='lines', name='20개월선', line=dict(color='#ff9900', width=1.5, dash='dot')), secondary_y=False)
                fig.add_trace(go.Scatter(x=filtered_dates, y=filtered_ma60, mode='lines', name='60개월선', line=dict(color='#9933cc', width=1.5, dash='dot')), secondary_y=False)

            vol_colors = ['#ff4b4b' if i > 0 and filtered_prices[i] < filtered_prices[i-1] else '#00cc96' for i in range(len(filtered_prices))]
            fig.add_trace(go.Bar(x=filtered_dates, y=filtered_volumes, name='거래량', marker_color=vol_colors, opacity=0.3), secondary_y=True)
            
            fig.update_layout(
                title=f"📈 {official_name} 전문가용 분석 차트 ({timeframe})",
                xaxis_title="시간 (Time)" if timeframe == "1주일" else "날짜 (Date)",
                hovermode="x unified", margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            fig.update_yaxes(title_text=f"주가 ({currency})", secondary_y=False)
            fig.update_yaxes(showgrid=False, secondary_y=True, range=[0, max(filtered_volumes)*4 if filtered_volumes and max(filtered_volumes) > 0 else 100])
            
            if timeframe in ["1주일", "1달", "3달", "6달", "1년"]:
                fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

            st.plotly_chart(fig, use_container_width=True)
            
            if live_mode:
                if "live_on" not in st.session_state:
                    st.toast("🔴 라이브 모드 ON: 주가, 거래량, 최고/최저가 실시간 갱신 중!", icon="⚡")
                    st.session_state.live_on = True 
                time.sleep(5)
                st.rerun()
            else:
                st.session_state.pop("live_on", None) 
                
        except Exception as e:
            st.info(f"차트 데이터를 불러오는 데 실패했습니다: {e}")
            
    except Exception as e:
        st.error(f"❌ 시스템 에러 발생: {e}")
        