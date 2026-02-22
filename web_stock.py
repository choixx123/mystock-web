import streamlit as st
import requests
import re
import time  # 🔥 10초 타이머를 위한 시간 부품 추가!
from datetime import datetime, timedelta
import plotly.graph_objects as go

# 🔥 CEO 전용 VIP 장부
vip_dict = {
    "현대차": "005380.KS", "네이버": "035420.KS", "카카오": "035720.KS",
    "루이비통": "MC.PA", "엔비": "NVDA", "삼전": "005930.KS",
    "테슬라": "TSLA", "애플": "AAPL", "마소": "MSFT"
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

# 🎨 웹페이지 기본 설정
st.set_page_config(page_title="CEO 글로벌 터미널", page_icon="🌍", layout="wide")

st.title("🌍 글로벌 주식 터미널 (Live Pro Version)")

# 🔥 [업그레이드] 검색창과 라이브 스위치를 나란히 예쁘게 배치!
col1, col2 = st.columns([3, 1])
with col1:
    search_term = st.text_input("🔍 종목명/티커 입력 후 [Enter]를 누르세요 (예: 테슬라)", "테슬라")
with col2:
    st.write("") # 줄 맞춤용 빈칸
    st.write("")
    live_mode = st.toggle("🔴 라이브 모드 (10초 자동 갱신)") # 마법의 스위치!

timeframe = st.radio("⏳ 조회 기간 선택", ["1주일", "1달", "3달", "6달", "1년", "3년", "5년", "10년"], horizontal=True, index=2)

# 버튼이 사라지고, 검색어만 있으면 '자동'으로 실행된다!
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
        curr_symbol = "₩" if currency == "KRW" else ("$" if currency == "USD" else ("€" if currency == "EUR" else currency))
        
        st.subheader(f"{official_name} ({symbol})")
        
        if currency == 'KRW':
            st.metric(label="현재가 (KRW)", value=f"{int(price):,} 원", delta=f"{change:,.0f} 원 ({change_pct:+.2f}%)")
        else:
            col1, col2 = st.columns(2)
            col1.metric(label=f"현재가 ({currency})", value=f"{curr_symbol}{price:,.2f}", delta=f"{curr_symbol}{change:,.2f} ({change_pct:+.2f}%)")
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
            st.plotly_chart(fig, use_container_width=True)
            
         # 🔥 UI 개선: 팝업은 스위치를 켤 때 딱 한 번만! 5초마다 '조용히' 새로고침!
            if live_mode:
                if "live_on" not in st.session_state:
                    st.toast("🔴 라이브 모드 ON: 이제부터 5초마다 조용히 자동 갱신됩니다!", icon="⚡")
                    st.session_state.live_on = True # 알림을 띄웠다고 메모장에 기록!
                
                time.sleep(5)
                st.rerun()
            else:
                # 스위치를 끄면 메모장 기록을 지워서 다음에 켤 때 다시 알림이 뜨게 만듦
                st.session_state.pop("live_on", None)
                
        except Exception as e:
            st.info(f"차트 데이터를 불러오는 데 실패했습니다: {e}")
            
    except Exception as e:
        st.error(f"❌ 시스템 에러 발생: {e}")
