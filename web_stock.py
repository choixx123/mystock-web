import streamlit as st
import requests
import re
import time
import math
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import xml.etree.ElementTree as ET
import urllib.parse

# 한국 표준시(KST) 설정
KST = timezone(timedelta(hours=9)) 

st.set_page_config(page_title="CEO 글로벌 터미널", page_icon="🌍", layout="wide")

st.markdown("""
    <style>
    .news-card { background: #f8f9fa; border-left: 4px solid #00b4d8; padding: 15px; border-radius: 5px; margin-bottom: 10px; }
    .news-title { font-size: 16px; font-weight: bold; color: #1E88E5 !important; text-decoration: none; }
    .delisted-alert { color: white; background-color: #ff4b4b; padding: 20px; border-radius: 10px; text-align: center; font-size: 24px; font-weight: bold; margin: 20px 0; }
    .badge { color: white; padding: 3px 8px; border-radius: 12px; font-size: 14px; font-weight: bold; margin-left: 10px; vertical-align: middle; }
    .closed-badge { background-color: #555; color: white; padding: 3px 8px; border-radius: 12px; font-size: 14px; font-weight: bold; margin-left: 10px; vertical-align: middle; }
    </style>
""", unsafe_allow_html=True)

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

@st.cache_data(ttl=5, show_spinner=False)
def get_cached_json(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200: 
            return res.json()
    except Exception: 
        return None
    return None

@st.cache_data(ttl=86400, show_spinner=False)
def translate_to_english(text):
    if re.match(r'^[a-zA-Z0-9\.\-\s]+$', text.strip()): 
        return text, True 
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl=en&dt=t&q={text}"
        res = requests.get(url, timeout=3)
        if res.status_code == 200: 
            return res.json()[0][0][0], True
    except: 
        pass
    return text, False 

@st.cache_data(ttl=5, show_spinner=False)
def get_quick_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
    res = get_cached_json(url)
    if res and res.get('chart') and res['chart'].get('result'):
        result = res['chart']['result'][0]
        meta = result['meta']
        quotes = result['indicators']['quote'][0]
        valid_closes = [p for p in quotes.get('close', []) if p is not None]
        price = meta.get('regularMarketPrice', valid_closes[-1] if valid_closes else 0)
        prev = valid_closes[-2] if len(valid_closes) >= 2 else meta.get('previousClose', price)
        return price, ((price - prev) / prev * 100) if prev else 0
    return 0, 0

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_news(original_name):
    clean_search_term = original_name.split('(')[0].strip()
    encoded_query = urllib.parse.quote(f"{clean_search_term} 주식")
    news_url = f"https://news.google.com/rss/search?q={encoded_query}+when:7d&hl=ko&gl=KR&ceid=KR:ko"
    news_list = []
    try:
        res = requests.get(news_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall('.//item')[:5]:
                title = item.find('title').text
                link = item.find('link').text
                source_elem = item.find('source')
                source = source_elem.text if source_elem is not None else "구글 뉴스"
                if " - " in title: title = " - ".join(title.split(" - ")[:-1])
                news_list.append({"title": title, "link": link, "source": source})
    except Exception: 
        pass
    return news_list, clean_search_term

def calc_ma(prices, window):
    ma = []
    for i in range(len(prices)):
        if i < window - 1: ma.append(None)
        else: ma.append(sum(prices[i-window+1:i+1]) / window)
    return ma

def calc_ema(prices, days):
    ema = [None] * len(prices)
    if not prices or len(prices) < days: return ema
    k = 2 / (days + 1)
    ema[days-1] = sum(prices[:days]) / days
    for i in range(days, len(prices)): ema[i] = prices[i] * k + ema[i-1] * (1 - k)
    return ema

def calc_macd(prices):
    ema12 = calc_ema(prices, 12)
    ema26 = calc_ema(prices, 26)
    macd = []
    for e12, e26 in zip(ema12, ema26):
        if e12 is not None and e26 is not None: macd.append(e12 - e26)
        else: macd.append(None)
            
    valid_idx = [i for i, m in enumerate(macd) if m is not None]
    signal = [None] * len(prices)
    if valid_idx and len(valid_idx) >= 9:
        first_idx = valid_idx[0]
        signal[first_idx+8] = sum(macd[first_idx:first_idx+9]) / 9
        k = 2 / (9 + 1)
        for i in range(first_idx+9, len(prices)): signal[i] = macd[i] * k + signal[i-1] * (1 - k)
    return macd, signal

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
            
        if avg_loss == 0: rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    return rsi

with st.sidebar:
    st.header("⚡ 라이트 터미널")
    st.write("불필요한 데이터 통신을 줄여 실시간 반응 속도를 극대화한 버전입니다.")
    st.markdown("---")
    st.caption("CEO 터미널 V13.0 (풀옵션 패치 완료)")

st.title("🌍 글로벌 주식 터미널")

if "search_input" not in st.session_state: st.session_state.search_input = "테슬라"
if "vip_dropdown" not in st.session_state: st.session_state.vip_dropdown = "🔽 주요 종목 선택"

def apply_vip_search():
    if st.session_state.vip_dropdown != "🔽 주요 종목 선택":
        st.session_state.search_input = st.session_state.vip_dropdown
        st.session_state.vip_dropdown = "🔽 주요 종목 선택" 

col1, col2, col3 = st.columns([4, 2, 2])
with col1: search_term = st.text_input("🔍 직접 검색 (종목명/티커 입력 후 Enter)", key="search_input")
with col2: st.selectbox("⭐ 빠른 검색", ["🔽 주요 종목 선택"] + list(vip_dict.keys()), key="vip_dropdown", on_change=apply_vip_search)
with col3:
    st.write("") 
    live_mode = st.toggle("🔴 라이브 모드 (5초 갱신)")
    use_candle = st.toggle("🕯️ 캔들 차트 모드", value=True)
    bottom_indicator = st.radio("하단 지표", ["RSI", "MACD"], horizontal=True, label_visibility="collapsed")

timeframe = st.radio("⏳ 조회 기간 선택", ["1일", "1주일", "1달", "1년", "5년", "10년"], horizontal=True, index=2)
st.markdown("---")

original_name = search_term.strip()
symbol = ""
official_name = original_name

if original_name in vip_dict:
    symbol = vip_dict[original_name]
else:
    english_name, trans_success = translate_to_english(original_name)
    if trans_success:
        search_res = get_cached_json(f"https://query2.finance.yahoo.com/v1/finance/search?q={english_name}")
        if search_res and search_res.get('quotes') and len(search_res['quotes']) > 0:
            symbol = search_res['quotes'][0]['symbol']
            official_name = search_res['quotes'][0].get('shortname', english_name)

if not symbol:
    st.markdown(f'<div class="delisted-alert">🚨 상장폐지 또는 검색 불가 ({original_name})<br><span style="font-size: 16px; font-weight: normal;">야후 파이낸스에서 완전히 삭제되었거나 종목명을 잘못 입력했습니다.</span></div>', unsafe_allow_html=True)
    st.stop() 

@st.fragment(run_every=5 if live_mode else None)
def render_live_metrics(target_symbol, target_name):
    m1, m2, m3, m4 = st.columns(4)
    indices = [("나스닥", "^IXIC", ""), ("S&P 500", "^GSPC", ""), ("코스피", "^KS11", ""), ("원/달러", "USDKRW=X", "₩")]
    for col, (name, sym, sign) in zip([m1, m2, m3, m4], indices):
        p, pct = get_quick_quote(sym)
        with col:
            if p > 0: st.metric(label=name, value=f"{sign}{p:,.2f}" if name != "코스피" else f"{p:,.2f}", delta=f"{pct:+.2f}%")
            else: st.metric(label=name, value="로딩중", delta="-")
    st.markdown("---")

    res_1y_data = get_cached_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{target_symbol}?range=1y&interval=1d")
    
    if not res_1y_data or 'chart' not in res_1y_data or not res_1y_data['chart']['result']: 
        st.markdown(f'<div class="delisted-alert">🚨 상장폐지 또는 검색 불가 ({target_symbol})</div>', unsafe_allow_html=True)
        return False
        
    result_1y = res_1y_data['chart']['result'][0]
    meta = result_1y['meta']
    
    last_trade_ts = meta.get('regularMarketTime', 0)
    if last_trade_ts == 0 and result_1y.get('timestamp'):
        last_trade_ts = result_1y['timestamp'][-1]
        
    is_dead = False
    if last_trade_ts > 0:
        last_trade_date = datetime.fromtimestamp(last_trade_ts, KST)
        days_dead = (datetime.now(KST) - last_trade_date).days
        
        if days_dead > 7:
            is_dead = True
            st.markdown(f'<div class="delisted-alert">🚨 상장폐지 / 거래정지 됨 ({target_symbol}) <br><span style="font-size: 16px; font-weight: normal;">마지막 거래일: {last_trade_date.strftime("%Y-%m-%d")}</span></div>', unsafe_allow_html=True)

    market_state = meta.get('marketState', 'REGULAR')
    
    if is_dead:
        closed_html = '<span class="badge" style="background-color: #000000;">💀 영구 휴장(상폐)</span>'
    elif market_state == 'REGULAR':
        closed_html = '' 
    elif market_state == 'PRE':
        closed_html = '<span class="badge" style="background-color: #ff9900;">🌅 프리마켓</span>'
    elif market_state in ['POST', 'POSTPOST']:
        closed_html = '<span class="badge" style="background-color: #9933cc;">🌃 애프터마켓</span>'
    else: 
        closed_html = '<span class="closed-badge">💤 장 휴장일</span>'
    
    quotes_1y = result_1y['indicators']['quote'][0]
    valid_closes = [p for p in quotes_1y.get('close', []) if p is not None]
    valid_highs = [h for h in quotes_1y.get('high', []) if h is not None]
    valid_lows = [l for l in quotes_1y.get('low', []) if l is not None]
    
    price = meta.get('regularMarketPrice', valid_closes[-1] if valid_closes else 0)
    prev_close = meta.get('previousClose', valid_closes[-2] if len(valid_closes) >= 2 else price)
    today_volume = meta.get('regularMarketVolume', 0)
    currency = meta.get('currency', 'USD') 
    
    day_change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
    high_52 = max(max(valid_highs) if valid_highs else 0, price)
    low_52 = min(min(valid_lows) if valid_lows else 0, price) if valid_lows else price

    c_sym = "₩" if currency == "KRW" else "＄" if currency == "USD" else "€" if currency == "EUR" else "¥" if currency == "JPY" else f"{currency} "
    
    price_str = f"{int(price):,} 원" if currency == "KRW" else f"{c_sym}{price:,.2f}"
    highlow_str = f"{int(high_52):,} / {int(low_52):,} 원" if currency == "KRW" else f"{c_sym}{high_52:,.2f} / {c_sym}{low_52:,.2f}"

    st.markdown(f"<h3>{target_name} ({target_symbol}) {closed_html}</h3>", unsafe_allow_html=True)
    
    # 🔥 5칸으로 확장 및 거래대금 로직 이식 완벽 적용
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns([1.1, 1.1, 1.4, 1.1, 1.2]) 
    with kpi1: st.metric(label=f"💰 {'마지막 가격' if is_dead else '현재가'}", value=price_str, delta=f"{day_change_pct:+.2f}%")
    with kpi2: 
        if currency != "KRW":
            ex_rate_res = get_cached_json("https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X")
            if ex_rate_res: st.metric(label="🇰🇷 원화 환산가", value=f"약 {int(price * ex_rate_res['chart']['result'][0]['meta']['regularMarketPrice']):,} 원")
        else: st.empty() 
    with kpi3: st.metric(label="⚖️ 52주 최고/최저", value=highlow_str)
    with kpi4: st.metric(label=f"📊 {'마지막 거래량' if is_dead else '거래량'}", value=f"{int(today_volume):,} 주")
    
    trading_val = price * today_volume
    if currency == "KRW":
        tval_str = f"{int(trading_val / 100000000):,}억 원"
    else:
        tval_str = f"{c_sym}{trading_val / 1000000:,.2f}M"
        
    with kpi5: st.metric(label="💸 거래대금", value=tval_str)
    
    if is_dead:
        return False
        
    return True 

is_valid_stock = render_live_metrics(symbol, official_name)

if is_valid_stock:
    st.write("") 
    st.markdown("---")

    # 🔥 10년 조회 시 에러 나던 1mo(월봉)을 1wk(주봉)으로 수정 완벽 적용
    fetch_range_map = {"1일": "5d", "1주일": "1mo", "1달": "6mo", "1년": "2y", "5년": "10y", "10년": "max"}
    interval_map = {"1일": "5m", "1주일": "15m", "1달": "1d", "1년": "1d", "5년": "1wk", "10년": "1wk"}

    chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={fetch_range_map[timeframe]}&interval={interval_map[timeframe]}"
    chart_res_json = get_cached_json(chart_url)

    if chart_res_json and chart_res_json['chart']['result']:
        chart_res = chart_res_json['chart']['result'][0]
        
        has_split = False
        if 'events' in chart_res and 'splits' in chart_res['events']:
            has_split = True
            
        split_html = '<span class="badge" style="background-color: #ff9900;">✂️ 액면분할 됨</span>' if has_split else ''
        
        dt_objects = [datetime.fromtimestamp(ts, KST) for ts in chart_res.get('timestamp', [])]
        quote = chart_res['indicators']['quote'][0]
        opens = quote.get('open', [])
        highs = quote.get('high', [])
        lows = quote.get('low', [])
        closes = quote.get('close', [])
        volumes = quote.get('volume', [])
        
        clean_data = []
        for i in range(len(dt_objects)):
            if i < len(closes) and closes[i] is not None:
                v = volumes[i] if (i < len(volumes) and volumes[i] is not None) else 0
                o = opens[i] if i < len(opens) else closes[i]
                h = highs[i] if i < len(highs) else closes[i]
                l = lows[i] if i < len(lows) else closes[i]
                clean_data.append((dt_objects[i], o, h, l, closes[i], v))

        full_prices = [row[4] for row in clean_data]
        ma20_full = calc_ma(full_prices, 20)
        ma60_full = calc_ma(full_prices, 60)
        rsi_full = calc_rsi(full_prices, 14) 
        macd_full, macd_signal_full = calc_macd(full_prices)

        f_dates, f_opens, f_highs, f_lows, f_closes, f_volumes = [], [], [], [], [], []
        f_ma20, f_ma60, f_rsi, f_macd, f_signal = [], [], [], [], []

        if timeframe == "1일" and len(clean_data) > 0:
            session_start_idx = 0
            for i in range(len(clean_data) - 1, 0, -1):
                if (clean_data[i][0] - clean_data[i-1][0]).total_seconds() > 4 * 3600: 
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
                f_macd.append(macd_full[i])
                f_signal.append(macd_signal_full[i])
                
        elif timeframe != "1일":
            cutoff_days = {"1주일": 7, "1달": 30, "1년": 365, "5년": 365*5, "10년": 365*10}.get(timeframe, 30)
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
                    f_macd.append(macd_full[i])
                    f_signal.append(macd_signal_full[i])

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, 
            vertical_spacing=0.03, row_heights=[0.75, 0.25], 
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
        )
        
        is_kr = symbol.endswith(".KS") or symbol.endswith(".KQ")
        up_color = '#ff4b4b' if is_kr else '#00cc96'
        down_color = '#00b4d8' if is_kr else '#ff4b4b'

        if use_candle and len(f_dates) > 0:
            fig.add_trace(go.Candlestick(
                x=f_dates, open=f_opens, high=f_highs, low=f_lows, close=f_closes, 
                increasing_line_color=up_color, decreasing_line_color=down_color, name='캔들'
            ), row=1, col=1, secondary_y=False)
        elif len(f_dates) > 0:
            fig.add_trace(go.Scatter(
                x=f_dates, y=f_closes, mode='lines', name='주가', line=dict(color='#00b4d8', width=3)
            ), row=1, col=1, secondary_y=False)

        if timeframe in ["1일", "1주일", "1달", "1년"] and len(f_dates) > 0:
            fig.add_trace(go.Scatter(x=f_dates, y=f_ma20, mode='lines', name='20선', line=dict(color='#ff9900', width=1.5, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=f_dates, y=f_ma60, mode='lines', name='60선', line=dict(color='#9933cc', width=1.5, dash='dash')), row=1, col=1)

        vol_colors = []
        for i in range(len(f_closes)):
            if i > 0 and f_closes[i] < f_closes[i-1]: vol_colors.append(down_color)
            else: vol_colors.append(up_color)

        if len(f_dates) > 0:
            fig.add_trace(go.Bar(x=f_dates, y=f_volumes, name='거래량', marker_color=vol_colors, opacity=0.3), row=1, col=1, secondary_y=True)
            
            if bottom_indicator == "RSI":
                fig.add_trace(go.Scatter(x=f_dates, y=f_rsi, mode='lines', name='RSI', line=dict(color='#9c27b0', width=1.5)), row=2, col=1)
                fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dot", line_color="blue", row=2, col=1)
                fig.update_yaxes(range=[0, 100], row=2, col=1)
            else:
                fig.add_trace(go.Scatter(x=f_dates, y=f_macd, mode='lines', name='MACD', line=dict(color='#00b4d8', width=1.5)), row=2, col=1)
                fig.add_trace(go.Scatter(x=f_dates, y=f_signal, mode='lines', name='Signal', line=dict(color='#ff9900', width=1.5)), row=2, col=1)
                
                macd_hist = []
                hist_colors = []
                for m, s in zip(f_macd, f_signal):
                    if m is not None and s is not None:
                        macd_hist.append(m - s)
                        hist_colors.append('#ff4b4b' if m > s else '#00b4d8')
                    else:
                        macd_hist.append(0)
                        hist_colors.append('#00b4d8')
                        
                fig.add_trace(go.Bar(x=f_dates, y=macd_hist, marker_color=hist_colors, name='Histogram'), row=2, col=1)

        st.markdown(f"<h4>📈 {official_name} 차트 & 보조지표 {split_html}</h4>", unsafe_allow_html=True)
        
        fig.update_layout(
            hovermode="x unified", height=700, margin=dict(l=0, r=0, t=20, b=0), xaxis_rangeslider_visible=False
        )
        max_vol = max(f_volumes) if f_volumes else 0
        fig.update_yaxes(showgrid=False, range=[0, max_vol * 4 if max_vol > 0 else 100], row=1, col=1, secondary_y=True)
        
        if timeframe in ["1달", "1년"]: fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.markdown(f"### 📰 {original_name} 최신 뉴스")
news_list, clean_search_term = get_cached_news(original_name)
if news_list:
    for news in news_list:
        st.markdown(f"""
            <div class="news-card">
                <a class="news-title" href="{news['link']}" target="_blank">📰 {news['title']}</a>
                <div style="font-size: 13px; color: #666; margin-top: 5px;">🏢 출처: {news['source']}</div>
            </div>
        """, unsafe_allow_html=True)
else:
    st.info("💡 뉴스를 불러올 수 없습니다.")
    