import streamlit as st
import requests
import re
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go

# 🔥 CEO 전용 VIP 장부 (글로벌 거인들 본진/미국섭 대거 추가!)
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

st.set_page_config(page_title="CEO 글로벌 터미널", page_icon="🌍", layout="wide")
st.title("🌍 글로벌 주식 터미널 (Live Pro Version)")

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
    headers = {'User-Agent': 'Mozilla/5.0'}
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
        
        range_map = {"1주일": "5d", "1달": "1mo", "3달": "3mo", "6달": "6mo", "1년": "1y", "3년": "5y", "5년": "5y", "10년": "10y"}
        interval_map = {"1주일": "15m", "1달": "1d", "3달": "1d", "6달": "1d", "1년": "1d", "3년": "1wk", "5년": "1wk", "10년": "1mo"}
        
        selected_range = range_map[timeframe]
        selected_interval = interval_map[timeframe]
        
        chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={selected_range}&interval={selected_interval}"
        chart_res = requests.get(chart_url, headers=headers).json()
        
        result = chart_res['chart']['result'][0]
        meta = result['meta']
        
        price = meta['regularMarketPrice']
        prev_close = meta['chartPreviousClose']
        currency = meta['currency']
        
        change = price - prev_close
        change_pct = (change / prev_close) * 100
        
        # 🔥 대만(TWD), 홍콩(HKD) 등 다양한 화폐 기호 완벽 지원!
        if currency == "KRW": curr_symbol = "₩"
        elif currency == "JPY": curr_symbol = "¥"
        elif currency == "USD": curr_symbol = "$"
        elif currency == "EUR": curr_symbol = "€"
        elif currency == "TWD": curr_symbol = "NT$"
        elif currency == "HKD": curr_symbol = "HK$"
        else: curr_symbol = currency
        
        sign = "-" if change < 0 else "+"
        abs_change = abs(change)
        
        st.subheader(f"{official_name} ({symbol})")
        
        if currency == 'KRW':
            delta_str = f"{change:+.0f} 원 ({change_pct:+.2f}%)"
            st.metric(label="현재가 (KRW)", value=f"{int(price):,} 원", delta=delta_str)
        else:
            delta_str = f"{sign}{curr_symbol}{abs_change:,.2f} ({change_pct:+.2f}%)"
            col1, col2 = st.columns(2)
            col1.metric(label=f"현재가 ({currency})", value=f"{curr_symbol}{price:,.2f}", delta=delta_str)
            try:
                ex_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{currency}KRW=X"
                ex_res = requests.get(ex_url, headers=headers).json()
                ex_rate = ex_res['chart']['result'][0]['meta']['regularMarketPrice']
                krw_price = int(price * ex_rate)
                col2.metric(label="원화 환산가 (KRW)", value=f"약 {krw_price:,} 원")
            except:
                pass
        
        # --- 📈 차트 그리기 ---
        st.markdown("---")
        try:
            timestamps = result['timestamp']
            close_prices = result['indicators']['quote'][0]['close']
            dt_objects = [datetime.fromtimestamp(ts) for ts in timestamps]
            clean_data = [(d, p) for d, p in zip(dt_objects, close_prices) if p is not None]
            
            if timeframe == "3년":
                cutoff_date = datetime.now() - timedelta(days=3*365)
                clean_data = [(d, p) for d, p in clean_data if d >= cutoff_date]
            
            if timeframe == "1주일":
                clean_dates = [x[0].strftime('%Y-%m-%d %H:%M') for x in clean_data]
            else:
                clean_dates = [x[0].strftime('%Y-%m-%d') for x in clean_data]
                
            clean_prices = [x[1] for x in clean_data]
            
            fig = go.Figure(data=go.Scatter(
                x=clean_dates, y=clean_prices, mode='lines',
                line=dict(color='#00b4d8', width=3),
                hovertemplate=f"<b>시간:</b> %{{x}}<br><b>종가:</b> %{{y:,.2f}} {curr_symbol}<extra></extra>"
            ))
            
            fig.update_layout(
                title=f"📈 {official_name} 주가 흐름 ({timeframe})",
                xaxis_title="시간 (Time)" if timeframe == "1주일" else "날짜 (Date)",
                yaxis_title=f"주가 ({currency})",
                hovermode="x unified", margin=dict(l=0, r=0, t=40, b=0)
            )
            
            if timeframe in ["1주일", "1달", "3달", "6달", "1년"]:
                fig.update_xaxes(
                    rangebreaks=[
                        dict(bounds=["sat", "mon"]) 
                    ]
                )

            st.plotly_chart(fig, use_container_width=True)
            
            if live_mode:
                if "live_on" not in st.session_state:
                    st.toast("🔴 라이브 모드 ON: 5초마다 자동 갱신됩니다!", icon="⚡")
                    st.session_state.live_on = True 
                time.sleep(5)
                st.rerun()
            else:
                st.session_state.pop("live_on", None) 
                
        except Exception as e:
            st.info(f"차트 데이터를 불러오는 데 실패했습니다: {e}")
            
    except Exception as e:
        st.error(f"❌ 시스템 에러 발생: {e}")
        