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
from bs4 import BeautifulSoup  # 🌟 네이버 크롤링을 위한 필수 라이브러리 추가됨

# 한국 표준시(KST) 설정
KST = timezone(timedelta(hours=9)) 

st.set_page_config(page_title="CEO 글로벌 터미널", page_icon="🌍", layout="wide")

if "dark_mode" not in st.session_state: st.session_state.dark_mode = False
if st.session_state.dark_mode:
    st.markdown("""
        <style>
        .stApp { background-color: #1a1a2e; color: #e0e0e0; }
        .news-card { background: #16213e !important; border-left: 4px solid #00b4d8; padding: 15px; border-radius: 5px; margin-bottom: 10px; }
        .stMetric { background: #16213e; border-radius: 8px; padding: 8px; }
        </style>
    """, unsafe_allow_html=True)

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

# ==========================================
# 🚀 [엔진 1] 야후 파이낸스 & API 로직
# ==========================================
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

# ==========================================
# 🇰🇷 [엔진 2] 네이버 증권 실시간 엔진 (한국주식 전용)
# ==========================================
@st.cache_data(ttl=5, show_spinner=False)
def get_naver_stock_data(code):
    url = f"https://finance.naver.com/item/sise.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')

        price_str = re.sub(r'[^\d]', '', soup.select_one('#_nowVal').text)
        rate_str = re.sub(r'[^\d\.\-]', '', soup.select_one('#_rate').text)
        vol_str = re.sub(r'[^\d]', '', soup.select_one('#_quant').text)
        amount_str = re.sub(r'[^\d]', '', soup.select_one('#_amount').text)

        return {
            "price": float(price_str),
            "rate": float(rate_str),
            "volume": int(vol_str),
            "amount": int(amount_str) * 1000000
        }
    except Exception as e:
        return None

# ==========================================
# 🧠 뉴스 및 차트 지표 계산 로직
# ==========================================
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

# ✅ [추가] 볼린저 밴드 계산 함수
def calc_bb(prices, window=20, num_std=2):
    upper, mid, lower = [], [], []
    for i in range(len(prices)):
        if i < window - 1:
            upper.append(None); mid.append(None); lower.append(None)
        else:
            subset = prices[i-window+1:i+1]
            m = sum(subset) / window
            std = (sum((x - m) ** 2 for x in subset) / window) ** 0.5
            mid.append(m)
            upper.append(m + num_std * std)
            lower.append(m - num_std * std)
    return upper, mid, lower

def format_abbrev(val, sym):
    if val == 0: return f"{sym}0"
    if val >= 1_000_000_000_000: return f"{sym}{val/1_000_000_000_000:.2f}T"
    if val >= 1_000_000_000: return f"{sym}{val/1_000_000_000:.2f}B"
    if val >= 1_000_000: return f"{sym}{val/1_000_000:.2f}M"
    if val >= 1_000: return f"{sym}{val/1_000:.2f}K"
    return f"{sym}{val:.2f}"

# ==========================================
# 🖥️ UI 및 메인 실행부
# ==========================================
with st.sidebar:
    st.header("⚡ 라이트 터미널")
    st.write("불필요한 데이터 통신을 줄여 실시간 반응 속도를 극대화한 버전입니다.")
    st.markdown("---")
    st.caption("CEO 터미널 V13.8 (볼린저밴드 + 프로그레스바 + 봉 단위 패치)")

st.title("🌍 글로벌 주식 터미널")

if "search_input" not in st.session_state: st.session_state.search_input = "삼성전자"
if "vip_dropdown" not in st.session_state: st.session_state.vip_dropdown = "🔽 주요 종목 선택"
if "dark_mode" not in st.session_state: st.session_state.dark_mode = False  # ✅ 추가

def apply_vip_search():
    if st.session_state.vip_dropdown != "🔽 주요 종목 선택":
        st.session_state.search_input = st.session_state.vip_dropdown
        st.session_state.vip_dropdown = "🔽 주요 종목 선택" 

col1, col2, col3 = st.columns([4, 2, 2])
with col1: search_term = st.text_input("🔍 직접 검색 (종목명/티커 입력 후 Enter)", key="search_input")
with col2: st.selectbox("⭐ 빠른 검색", ["🔽 주요 종목 선택"] + list(vip_dict.keys()), key="vip_dropdown", on_change=apply_vip_search)
with col3:
    st.write("")
    dark_mode = st.toggle("🌙 다크모드", key="dark_mode")
    live_mode = st.toggle("🔴 라이브 모드 (5초 갱신)")
    use_candle = st.toggle("🕯️ 캔들 차트 모드", value=True)
    show_bb = st.toggle("📐 볼린저 밴드", value=False)  # ✅ [추가] 볼린저 밴드 토글
    bottom_indicator = st.radio("하단 지표", ["RSI", "MACD"], horizontal=True, label_visibility="collapsed")

# ✅ [변경] 조회기간: 분봉/일봉/월봉/연봉/5년/10년
timeframe = st.radio("⏳ 조회 기간 선택", ["분봉", "일봉", "월봉", "연봉", "5년", "10년"], horizontal=True, index=1)
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
    if is_dead: closed_html = '<span class="badge" style="background-color: #000000;">💀 영구 휴장(상폐)</span>'
    elif market_state == 'REGULAR': closed_html = '' 
    elif market_state == 'PRE': closed_html = '<span class="badge" style="background-color: #ff9900;">🌅 프리마켓</span>'
    elif market_state in ['POST', 'POSTPOST']: closed_html = '<span class="badge" style="background-color: #9933cc;">🌃 애프터마켓</span>'
    else: closed_html = '<span class="closed-badge">💤 장 휴장일</span>'
    
    quotes_1y = result_1y['indicators']['quote'][0]
    valid_closes = [p for p in quotes_1y.get('close', []) if p is not None]
    valid_highs = [h for h in quotes_1y.get('high', []) if h is not None]
    valid_lows = [l for l in quotes_1y.get('low', []) if l is not None]
    
    price = meta.get('regularMarketPrice', valid_closes[-1] if valid_closes else 0)
    prev_close = meta.get('previousClose', valid_closes[-2] if len(valid_closes) >= 2 else price)
    today_volume = meta.get('regularMarketVolume', 0)
    day_change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
    currency = meta.get('currency', 'USD') 
    
    naver_amount = None
    is_kr_stock = target_symbol.endswith(".KS") or target_symbol.endswith(".KQ")
    if is_kr_stock:
        naver_code = target_symbol.split('.')[0]
        naver_data = get_naver_stock_data(naver_code)
        if naver_data:
            price = naver_data["price"]
            day_change_pct = naver_data["rate"]
            today_volume = naver_data["volume"]
            naver_amount = naver_data["amount"]

    c_sym_st = "₩" if currency == "KRW" else "\\$" if currency == "USD" else "€" if currency == "EUR" else "¥" if currency == "JPY" else f"{currency} "
    high_52 = max(max(valid_highs) if valid_highs else 0, price)
    low_52 = min(min(valid_lows) if valid_lows else 0, price) if valid_lows else price

    price_str = f"{c_sym_st}{int(price):,}" if currency in ["KRW", "JPY"] else f"{c_sym_st}{price:,.2f}"
    highlow_str = f"{c_sym_st}{int(high_52):,} / {c_sym_st}{int(low_52):,}" if currency in ["KRW", "JPY"] else f"{c_sym_st}{high_52:,.2f} / {c_sym_st}{low_52:,.2f}"

    st.markdown(f"<h3>{target_name} ({target_symbol}) {closed_html}</h3>", unsafe_allow_html=True)
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4) 
    with kpi1: st.metric(label=f"💰 {'마지막 가격' if is_dead else '현재가'}", value=price_str, delta=f"{day_change_pct:+.2f}%")
    
    with kpi2: 
        if is_kr_stock and naver_amount is not None:
            st.metric(label="💸 거래대금", value=format_abbrev(naver_amount, "₩"))
        elif currency != "KRW":
            ex_rate_res = get_cached_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{currency}KRW=X")
            if ex_rate_res and ex_rate_res.get('chart') and ex_rate_res['chart'].get('result'): 
                curr_rate = ex_rate_res['chart']['result'][0]['meta']['regularMarketPrice']
                st.metric(label="🇰🇷 원화 환산가", value=f"약 ₩{int(price * curr_rate):,}")
            else: st.empty()
        else: st.empty() 
        
    with kpi3: st.metric(label="⚖️ 52주 최고/최저", value=highlow_str)
    
    with kpi4: 
        try:
            if today_volume is None or str(today_volume).strip() == "" or str(today_volume) == "nan":
                volume_str = "데이터 없음"
            else:
                volume_str = format_abbrev(today_volume, "")
        except Exception:
            volume_str = "에러"
            
        st.metric(label="📊 거래량", value=volume_str)

    # ✅ [추가] 52주 프로그레스 바
    if high_52 > low_52:
        progress_pct = int(max(0, min(100, (price - low_52) / (high_52 - low_52) * 100)))
        bar_color = "#ff4b4b" if progress_pct >= 80 else "#ff9900" if progress_pct >= 50 else "#00b4d8"
        st.markdown(f"""
            <div style="margin: 12px 0 4px 0; font-size: 13px; color: #888;">
                📍 52주 위치 &nbsp;<b style="color:{bar_color}">{progress_pct}%</b>
                &nbsp;|&nbsp; 저가 {c_sym_st}{int(low_52):,} ↔ 고가 {c_sym_st}{int(high_52):,}
            </div>
            <div style="background:#e0e0e0; border-radius:6px; height:10px; margin-bottom:8px;">
                <div style="background:{bar_color}; width:{progress_pct}%; height:10px; border-radius:6px;"></div>
            </div>
        """, unsafe_allow_html=True)

    if is_dead: return False
    return True

is_valid_stock = render_live_metrics(symbol, official_name)

if is_valid_stock:
    st.write("") 
    st.markdown("---")

    # ✅ [변경] 분봉/일봉/월봉/연봉/5년/10년 에 맞는 range & interval
    fetch_range_map = {"분봉": "1d", "일봉": "1y", "월봉": "5y", "연봉": "max", "5년": "5y", "10년": "max"}
    interval_map    = {"분봉": "5m", "일봉": "1d", "월봉": "1mo", "연봉": "3mo", "5년": "1wk", "10년": "1wk"}

    chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={fetch_range_map[timeframe]}&interval={interval_map[timeframe]}"
    chart_res_json = get_cached_json(chart_url)

    if chart_res_json and chart_res_json['chart']['result']:
        chart_res = chart_res_json['chart']['result'][0]
        
        chart_currency = chart_res['meta'].get('currency', 'USD')
        c_sym_plot = "₩" if chart_currency == "KRW" else "$" if chart_currency == "USD" else "€" if chart_currency == "EUR" else "¥" if chart_currency == "JPY" else f"{chart_currency} "

        ex_rate_for_chart = 1.0
        if chart_currency != "KRW":
            ex_rate_req = get_cached_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{chart_currency}KRW=X?range=1d&interval=1d")
            if ex_rate_req and ex_rate_req.get('chart') and ex_rate_req['chart'].get('result'):
                ex_rate_for_chart = ex_rate_req['chart']['result'][0]['meta']['regularMarketPrice']

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

        # ✅ [변경] "1일" → "분봉"
        if timeframe == "분봉" and len(clean_data) > 0:
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
                
        # ✅ [변경] "1일" → "분봉"
        elif timeframe != "분봉":
            # ✅ [변경] cutoff_days 새 timeframe에 맞게 변경
            cutoff_days = {"일봉": 365, "월봉": 365*5, "연봉": 365*30, "5년": 365*5, "10년": 365*10}.get(timeframe, 365)
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

        # ✅ [추가] 볼린저 밴드 계산 (이미 필터링된 f_closes 사용, API 추가 없음)
        if show_bb and len(f_closes) >= 20:
            f_bb_upper, f_bb_mid, f_bb_lower = calc_bb(f_closes)
        else:
            f_bb_upper = f_bb_mid = f_bb_lower = [None] * len(f_closes)

        # ✅ [변경] 분봉만 시:분 표시, 나머지는 날짜만
        f_dates_str = [d.strftime('%Y-%m-%d %H:%M') + '\u200b' if timeframe == '분봉' else d.strftime('%Y-%m-%d') + '\u200b' for d in f_dates]
        
        formatted_tvals = []
        for c, v in zip(f_closes, f_volumes):
            orig_str = format_abbrev(c * v, c_sym_plot)
            if chart_currency != "KRW" and ex_rate_for_chart != 1.0:
                krw_str = format_abbrev(c * v * ex_rate_for_chart, "₩")
                formatted_tvals.append(f"약 {krw_str} ({orig_str})")
            else:
                formatted_tvals.append(orig_str)

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True, 
            vertical_spacing=0.03, row_heights=[0.75, 0.25], 
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
        )
        
        is_kr = symbol.endswith(".KS") or symbol.endswith(".KQ")
        up_color = '#ff4b4b' if is_kr else '#00cc96'
        down_color = '#00b4d8' if is_kr else '#ff4b4b'

        if use_candle and len(f_dates_str) > 0:
            fig.add_trace(go.Candlestick(
                x=f_dates_str, open=f_opens, high=f_highs, low=f_lows, close=f_closes, 
                increasing_line_color=up_color, decreasing_line_color=down_color, name='캔들'
            ), row=1, col=1, secondary_y=False)
        elif len(f_dates_str) > 0:
            fig.add_trace(go.Scatter(
                x=f_dates_str, y=f_closes, mode='lines', name='주가', line=dict(color='#00b4d8', width=3)
            ), row=1, col=1, secondary_y=False)

        # ✅ [변경] MA는 분봉/일봉/월봉/연봉에서 표시
        if timeframe in ["분봉", "일봉", "월봉", "연봉"] and len(f_dates_str) > 0:
            fig.add_trace(go.Scatter(x=f_dates_str, y=f_ma20, mode='lines', name='20선', line=dict(color='#ff9900', width=1.5, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=f_dates_str, y=f_ma60, mode='lines', name='60선', line=dict(color='#9933cc', width=1.5, dash='dash')), row=1, col=1)

        # ✅ [추가] 볼린저 밴드 트레이스
        if show_bb and len(f_dates_str) > 0 and any(v is not None for v in f_bb_upper):
            fig.add_trace(go.Scatter(x=f_dates_str, y=f_bb_upper, mode='lines', name='BB 상단', line=dict(color='rgba(0,180,216,0.4)', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=f_dates_str, y=f_bb_lower, mode='lines', name='BB 하단', line=dict(color='rgba(0,180,216,0.4)', width=1), fill='tonexty', fillcolor='rgba(0,180,216,0.05)'), row=1, col=1)
            fig.add_trace(go.Scatter(x=f_dates_str, y=f_bb_mid, mode='lines', name='BB 중심', line=dict(color='rgba(0,180,216,0.6)', width=1, dash='dot')), row=1, col=1)

        vol_colors = []
        for i in range(len(f_closes)):
            if i > 0 and f_closes[i] < f_closes[i-1]: vol_colors.append(down_color)
            else: vol_colors.append(up_color)

        if len(f_dates_str) > 0:
            fig.add_trace(go.Bar(
                x=f_dates_str, y=f_volumes, name='거래량', marker_color=vol_colors, opacity=0.3,
                customdata=formatted_tvals,
                hovertemplate="%{y:,.0f}<br><b>거래대금:</b> %{customdata}<extra></extra>"
            ), row=1, col=1, secondary_y=True)
            
            if bottom_indicator == "RSI":
                fig.add_trace(go.Scatter(x=f_dates_str, y=f_rsi, mode='lines', name='RSI', line=dict(color='#9c27b0', width=1.5)), row=2, col=1)
                fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dot", line_color="blue", row=2, col=1)
                fig.update_yaxes(range=[0, 100], row=2, col=1)
            else:
                fig.add_trace(go.Scatter(x=f_dates_str, y=f_macd, mode='lines', name='MACD', line=dict(color='#00b4d8', width=1.5)), row=2, col=1)
                fig.add_trace(go.Scatter(x=f_dates_str, y=f_signal, mode='lines', name='Signal', line=dict(color='#ff9900', width=1.5)), row=2, col=1)
                
                macd_hist = []
                hist_colors = []
                for m, s in zip(f_macd, f_signal):
                    if m is not None and s is not None:
                        macd_hist.append(m - s)
                        hist_colors.append('#ff4b4b' if m > s else '#00b4d8')
                    else:
                        macd_hist.append(0)
                        hist_colors.append('#00b4d8')
                        
                fig.add_trace(go.Bar(x=f_dates_str, y=macd_hist, marker_color=hist_colors, name='Histogram'), row=2, col=1)

        st.markdown(f"<h4>📈 {official_name} 차트 & 보조지표 {split_html}</h4>", unsafe_allow_html=True)
        
        fig.update_layout(
             hovermode="x unified", height=700, margin=dict(l=0, r=0, t=20, b=0), xaxis_rangeslider_visible=False,
             template="plotly_dark" if dark_mode else "plotly"
)
        
        fig.update_xaxes(type='category', nticks=15, row=1, col=1)
        fig.update_xaxes(type='category', nticks=15, row=2, col=1)
        
        max_vol = max(f_volumes) if f_volumes else 0
        fig.update_yaxes(showgrid=False, range=[0, max_vol * 4 if max_vol > 0 else 100], row=1, col=1, secondary_y=True)
        
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