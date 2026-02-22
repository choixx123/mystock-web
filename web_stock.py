import streamlit as st
import requests
import re

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
st.set_page_config(page_title="CEO 글로벌 터미널", page_icon="🌍")

st.title("🌍 글로벌 주식 터미널 (Web)")
st.write("스마트폰, 태블릿, PC 어디서든 전 세계 주가를 실시간으로 확인하세요.")

# 검색창 만들기
search_term = st.text_input("🔍 종목명 또는 티커(기호)를 입력하세요 (예: 테슬라, NVDA, 삼전)", "")

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
                
                # 🔥 [업그레이드 포인트] 최근 3개월 치 데이터를 가져오도록 URL 수정!
                chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=3mo&interval=1d"
                chart_res = requests.get(chart_url, headers=headers).json()
                
                result = chart_res['chart']['result'][0]
                meta = result['meta']
                
                price = meta['regularMarketPrice']
                prev_close = meta['chartPreviousClose']
                currency = meta['currency']
                
                change = price - prev_close
                change_pct = (change / prev_close) * 100
                
                # 1. 상단: 종목명 및 현재가 표시
                st.subheader(f"{official_name} ({symbol})")
                
                if currency == 'KRW':
                    st.metric(label="현재가 (KRW)", value=f"{int(price):,} 원", delta=f"{change:,.0f} 원 ({change_pct:+.2f}%)")
                else:
                    ex_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{currency}KRW=X"
                    ex_res = requests.get(ex_url, headers=headers).json()
                    ex_rate = ex_res['chart']['result'][0]['meta']['regularMarketPrice']
                    krw_price = int(price * ex_rate)
                    
                    col1, col2 = st.columns(2)
                    col1.metric(label=f"현재가 ({currency})", value=f"{price:,.2f} {currency}", delta=f"{change:,.2f} {currency} ({change_pct:+.2f}%)")
                    col2.metric(label="원화 환산가 (KRW)", value=f"약 {krw_price:,} 원")
                
                # 2. 하단: 최근 3개월 주가 차트 (Streamlit 마법)
                st.markdown("---")
                st.markdown("### 📈 최근 3개월 주가 흐름")
                
                try:
                    # 야후에서 종가(close) 리스트만 뽑아내기
                    close_prices = result['indicators']['quote'][0]['close']
                    # 에러 방지를 위해 빈 데이터(None) 제거
                    clean_prices = [p for p in close_prices if p is not None]
                    
                    # 꺾은선 차트 그리기 (단 한 줄이면 끝난다!)
                    st.line_chart(clean_prices)
                except Exception as e:
                    st.info("차트 데이터를 불러오는 데 실패했습니다.")
                    
                st.success("조회 및 차트 분석 완료!")
                
            except Exception as e:
                st.error(f"❌ 시스템 에러 발생: {e}")
                