import streamlit as st
import requests
import re
from datetime import datetime, timedelta  # 🔥 날짜 계산을 위한 부품 추가
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

st.title("🌍 글로벌 주식 터미널 (Pro Version)")
st.write("스마트폰, 태블릿, PC 어디서든 전 세계 주가를 실시간으로 확인하세요.")

# 검색창 만들기
search_term = st.text_input("🔍 종목명 또는 티커(기호)를 입력하세요 (예: 테슬라, NVDA, 삼전)", "")

# 🔥 [업그레이드] 세밀한 기간 선택 버튼
timeframe = st.radio(
    "⏳ 조회 기간 선택", 
    ["1주일", "1달", "3달", "6달", "1년", "3년", "5년", "10년"], 
    horizontal=True, 
    index=2 # 기본 선택값을 '3달'로 세팅
)

# 버튼 누르면 실행될 로직
if st.button("🚀 실시간 주가 조회", use_container_width=True):
    if not search_term:
        st.warning("종목을 입력해주세요!")
    else:
        with st.spinner('글로벌 금융망에 접속 중입니다... ⏳'):
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
                
                # 🔥 기간별 야후 파이낸스 데이터 요청 규칙 (1주일은 15분 단위로 세밀하게!)
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
                
                # 화폐 단위 기호
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
                
                # --- 📈 프로용 차트 그리기 (Plotly) ---
                st.markdown("---")
                
                try:
                    timestamps = result['timestamp']
                    close_prices = result['indicators']['quote'][0]['close']
                    
                    # 1. 타임스탬프를 시간 객체로 변환
                    dt_objects = [datetime.fromtimestamp(ts) for ts in timestamps]
                    
                    # 2. 빈 데이터 제거
                    clean_data = [(d, p) for d, p in zip(dt_objects, close_prices) if p is not None]
                    
                    # 🔥 [핵심] '3년'을 선택했을 경우, 5년 치 데이터에서 최근 3년(약 1095일)만 잘라내기
                    if timeframe == "3년":
                        cutoff_date = datetime.now() - timedelta(days=3*365)
                        clean_data = [(d, p) for d, p in clean_data if d >= cutoff_date]
                    
                    # 3. 1주일 차트는 '시간'까지 표시되도록 포맷 변경
                    if timeframe == "1주일":
                        clean_dates = [x[0].strftime('%Y-%m-%d %H:%M') for x in clean_data]
                    else:
                        clean_dates = [x[0].strftime('%Y-%m-%d') for x in clean_data]
                        
                    clean_prices = [x[1] for x in clean_data]
                    
                    # 플롯리(Plotly) 차트 세팅
                    fig = go.Figure(data=go.Scatter(
                        x=clean_dates, 
                        y=clean_prices,
                        mode='lines',
                        line=dict(color='#00b4d8', width=3),
                        hovertemplate=f"<b>시간:</b> %{{x}}<br><b>종가:</b> %{{y:,.2f}} {curr_symbol}<extra></extra>"
                    ))
                    
                    fig.update_layout(
                        title=f"📈 {official_name} 주가 흐름 ({timeframe})",
                        xaxis_title="시간 (Time)" if timeframe == "1주일" else "날짜 (Date)",
                        yaxis_title=f"주가 ({currency})",
                        hovermode="x unified",
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                except Exception as e:
                    st.info(f"차트 데이터를 불러오는 데 실패했습니다: {e}")
                    
                st.success("조회 및 차트 분석 완료!")
                
            except Exception as e:
                st.error(f"❌ 시스템 에러 발생: {e}")
                