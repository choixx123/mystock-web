import streamlit as st
import requests
import re
import time
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- [전역 설정 및 스타일] ---
st.set_page_config(page_title="CEO 글로벌 터미널 Pro", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .reportview-container { background: #f0f2f6; }
    .news-card {
        border: 1px solid #e6e9ef;
        padding: 20px;
        border-radius: 12px;
        background-color: white;
        margin-bottom: 12px;
        transition: transform 0.2s;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    .news-card:hover { transform: translateY(-3px); box-shadow: 2px 5px 15px rgba(0,0,0,0.1); }
    .news-title { font-size: 18px; font-weight: bold; color: #1E88E5; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

# --- [유틸리티 함수] ---
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def translate(text, target='ko'):
    if not text: return ""
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={text}"
        res = requests.get(url, timeout=3).json()
        return res[0][0][0]
    except: return text

def format_num(num):
    if num == "N/A" or num is None: return "데이터 준비중"
    if num >= 1e12: return f"{num/1e12:.2f}T (조)"
    if num >= 1e8: return f"{num/1e8:.2f}억"
    return f"{num:,.2f}"

# --- [메인 로직] ---
vip_dict = {
    "삼성전자": "005930.KS", "현대차": "005380.KS", "네이버": "035420.KS",
    "테슬라": "TSLA", "엔비디아": "NVDA", "애플": "AAPL", "마이크로소프트": "MSFT"
}

st.title("🛡️ CEO 글로벌 터미널 (Pro Mode)")

# 검색 섹션
col_search, col_vip, col_toggle = st.columns([4, 2, 2])
with col_search:
    query = st.text_input("🔍 종목명 또는 티커를 입력해라", "테슬라")
with col_vip:
    vip_choice = st.selectbox("⭐ 주요 종목", ["🔽 직접 입력"] + list(vip_dict.keys()))
with col_toggle:
    st.write("")
    use_candle = st.toggle("📊 캔들 차트 모드", value=True)

search_term = vip_dict[vip_choice] if vip_choice != "🔽 직접 입력" else query

if search_term:
    try:
        # 1. 심볼 검색
        s_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={search_term}"
        s_res = requests.get(s_url, headers=HEADERS).json()
        if not s_res.get('quotes'):
            st.error("종목을 찾을 수 없다!")
            st.stop()
        
        symbol = s_res['quotes'][0]['symbol']
        name = s_res['quotes'][0].get('shortname', symbol)
        
        # 2. 지표 데이터 긁어오기 (SummaryDetail 이용)
        sum_url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=summaryDetail,defaultKeyStatistics,price"
        sum_res = requests.get(sum_url, headers=HEADERS).json()
        
        raw_data = sum_res['quoteSummary']['result'][0]
        detail = raw_data.get('summaryDetail', {})
        stats = raw_data.get('defaultKeyStatistics', {})
        price_data = raw_data.get('price', {})

        # 지표 추출
        curr_price = price_data.get('regularMarketPrice', {}).get('raw')
        change_pct = price_data.get('regularMarketChangePercent', {}).get('raw', 0) * 100
        currency = price_data.get('currency', 'USD')
        
        m_cap = detail.get('marketCap', {}).get('raw')
        per = detail.get('trailingPE', {}).get('raw') or stats.get('forwardPE', {}).get('raw')
        div_yield = detail.get('dividendYield', {}).get('raw')
        if div_yield: div_yield = f"{div_yield * 100:.2f}%"

        # 3. 상단 대시보드 출력
        st.subheader(f"{name} ({symbol})")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("현재가", f"{curr_price:,.2f} {currency}")
        m2.metric("전일대비", f"{change_pct:+.2f}%")
        m3.metric("시가총액", format_num(m_cap))
        m4.metric("PER (수익비율)", f"{per:.2f}배" if per else "데이터 없음")
        m5.metric("배당수익률", div_yield if div_yield else "0.00%")

        # 4. 차트 데이터 (1년치)
        timeframe = st.radio("기간", ["1주일", "1달", "6달", "1년"], horizontal=True, index=3)
        tf_map = {"1주일":"5d", "1달":"1mo", "6달":"6mo", "1년":"1y"}
        iv_map = {"1주일":"15m", "1달":"1d", "6달":"1d", "1년":"1d"}
        
        c_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={tf_map[timeframe]}&interval={iv_map[timeframe]}"
        c_res = requests.get(c_url, headers=HEADERS).json()
        chart_res = c_res['chart']['result'][0]
        
        times = [datetime.fromtimestamp(t) for t in chart_res['timestamp']]
        quotes = chart_res['indicators']['quote'][0]
        
        # 5. 차트 렌더링
        is_kr = symbol.endswith(".KS") or symbol.endswith(".KQ")
        up, down = ('red', 'blue') if is_kr else ('green', 'red')

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
        
        if use_candle:
            fig.add_trace(go.Candlestick(
                x=times, open=quotes['open'], high=quotes['high'], 
                low=quotes['low'], close=quotes['close'],
                increasing_line_color=up, decreasing_line_color=down, name="캔들"
            ), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(x=times, y=quotes['close'], mode='lines', line=dict(color='#1E88E5', width=2), name="종가"), row=1, col=1)

        # 거래량 추가
        fig.add_trace(go.Bar(x=times, y=quotes['volume'], marker_color='#cfd8dc', name="거래량"), row=2, col=1)
        fig.update_layout(xaxis_rangeslider_visible=False, height=550, margin=dict(l=10, r=10, t=10, b=10), hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

        # 6. 뉴스 섹션 (카드형 UI + 번역)
        st.markdown("---")
        st.subheader("📰 CEO 전용 브리핑 (기사 제목 클릭 시 이동)")
        
        news_list = s_res.get('news', [])
        if news_list:
            for n in news_list[:5]:
                title_ko = translate(n['title'])
                st.markdown(f"""
                    <div class="news-card">
                        <a class="news-title" href="{n['link']}" target="_blank">🔗 {title_ko}</a>
                        <div style="color: #666; font-size: 13px; margin-top: 8px;">
                            <b>{n['publisher']}</b> | 원문: {n['title']}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("현재 관련 뉴스가 없다.")

    except Exception as e:
        st.error(f"⚠️ 시스템 오류 발생: {e}")
        