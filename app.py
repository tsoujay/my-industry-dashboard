import streamlit as st
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import google.generativeai as genai

# --- 1. 新聞抓取模組 ---
def get_google_news(query):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        response = requests.get(url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        news_list = []
        for item in root.findall('./channel/item'):
            title = item.find('title').text
            link = item.find('link').text
            news_list.append({'title': title, 'link': link})
            if len(news_list) >= 10:
                break
        return news_list
    except Exception:
        return None

# --- 2. 舊版單一 Yahoo 報價 (保留給其他分頁使用) ---
def get_yahoo_price(symbol):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers)
        closes = res.json()['chart']['result'][0]['indicators']['quote'][0]['close']
        valid = [p for p in closes if p is not None]
        return valid[-1] if valid else None
    except:
        return None

# --- 新增：超級批次 Yahoo 報價引擎 (一次抓 40 檔，速度極快) ---
def get_yahoo_bulk(symbols_list):
    if not symbols_list: return {}
    symbols_str = ",".join(symbols_list)
    url = f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={symbols_str}"
    headers = {"User-Agent": "Mozilla/5.0"}
    result = {}
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        for item in data['quoteResponse']['result']:
            sym = item['symbol']
            price = item.get('regularMarketPrice', 0)
            change = item.get('regularMarketChangePercent', 0)
            result[sym] = {'price': price, 'change': change}
    except:
        pass
    return result

# --- 3. 介面與設定 ---
st.set_page_config(page_title="即時產業問答中心", page_icon="📈", layout="wide")
st.title("📈 我的即時產業問答中心")

st.sidebar.header("⚙️ 系統設定")
api_key = st.sidebar.text_input("輸入你的 Gemini API Key (用於啟動 AI):", type="password").strip()

st.header("📊 即時市場數據")
tab1, tab2, tab3 = st.tabs(["🪙 全市場儀表板 (雙引擎)", "💾 記憶體產業", "⭐ 投資計畫與試算"])

# 【分頁 1】混合雙引擎全市場儀表板
with tab1:
    st.subheader("🪙 全市場即時儀表板 (Crypto & 美股)")
    st.caption("⏱️ 雙引擎運作中：系統將每 30 秒自動為您抓取最新報價...")
    
    # 定義 Pionex 抓取的加密貨幣
    pionex_tokens = {
        "Bitcoin (BTC)": "BTC_USDT", "Ethereum (ETH)": "ETH_USDT", "Cardano (ADA)": "ADA_USDT"
    }
    
    # 定義 Yahoo 抓取的真實美股與期貨 (將派網代幣對應到真實世界代號)
    yahoo_groups = {
        "💻 科技巨頭與半導體 (真實美股)": {
            "英偉達 (NVDA)": "NVDA", "特斯拉 (TSLA)": "TSLA", "蘋果 (AAPL)": "AAPL", 
            "微軟 (MSFT)": "MSFT", "谷歌 (GOOGL)": "GOOGL", "亞馬遜 (AMZN)": "AMZN",
            "美光 (MU)": "MU", "超微 (AMD)": "AMD", "博通 (AVGO)": "AVGO", 
            "阿斯麥 (ASML)": "ASML", "英特爾 (INTC)": "INTC", "Meta (META)": "META", 
            "甲骨文 (ORCL)": "ORCL", "奈飛 (NFLX)": "NFLX"
        },
        "🥇 貴金屬與能源期貨": {
            "黃金期貨 (GC=F)": "GC=F", "白銀期貨 (SI=F)": "SI=F", "鈀金期貨 (PA=F)": "PA=F", 
            "鉑金期貨 (PL=F)": "PL=F", "原油ETF (USO)": "USO", "布倫特原油 (BNO)": "BNO", 
            "天然氣ETF (UNG)": "UNG", "切尼爾能源 (LNG)": "LNG"
        },
        "📈 指數與原物料 ETF": {
            "納斯達克 (QQQ)": "QQQ", "標普500 (SPY)": "SPY", "半導體ETF (SOXX)": "SOXX", 
            "韓國ETF (EWY)": "EWY", "白銀ETF (SLV)": "SLV", "鈀金ETF (PALL)": "PALL", 
            "鉑金ETF (PPLT)": "PPLT", "銅ETF (CPER)": "CPER"
        },
        "🚀 其他熱門話題美股": {
            "Coinbase (COIN)": "COIN", "微策略 (MSTR)": "MSTR", "Palantir (PLTR)": "PLTR", 
            "Robinhood (HOOD)": "HOOD", "禮來 (LLY)": "LLY", "聯合健康 (UNH)": "UNH", 
            "洛克希德馬丁 (LMT)": "LMT", "威騰/閃迪 (WDC)": "WDC", "Rocket Lab (RKLB)": "RKLB", 
            "Hims (HIMS)": "HIMS", "IREN (IREN)": "IREN", "Rigetti (RGTI)": "RGTI", 
            "MP Materials (MP)": "MP", "OKLO (OKLO)": "OKLO"
        }
    }

    @st.fragment(run_every="30s")
    def auto_refresh_dual_engine():
        # --- 1. Pionex 加密貨幣引擎 ---
        pionex_data = {}
        try:
            res = requests.get("https://api.pionex.com/api/v1/market/tickers")
            for t in res.json().get('data', {}).get('tickers', []):
                pionex_data[t['symbol']] = t
        except: pass

        with st.expander("🌟 主流加密貨幣 (來源：Pionex)", expanded=True):
            cols = st.columns(4)
            for idx, (label, symbol) in enumerate(pionex_tokens.items()):
                crypto = pionex_data.get(symbol)
                if crypto:
                    price = float(crypto.get('close', 0))
                    change = float(crypto.get('change24h', 0)) * 100
                    cols[idx % 4].metric(label, f"${price:,.2f}", f"{change:.2f}%")
                else:
                    cols[idx % 4].warning(f"無 {symbol}")

        # --- 2. Yahoo 批次引擎 ---
        # 收集所有需要抓取的 Yahoo 代號
        all_yahoo_symbols = []
        for group in yahoo_groups.values():
            all_yahoo_symbols.extend(group.values())
        
        # 一次性發送請求抓回所有資料 (超快速)
        yahoo_data = get_yahoo_bulk(all_yahoo_symbols)

        # 顯示資料
        for group_name, tokens in yahoo_groups.items():
            expanded = True if "科技巨頭" in group_name else False
            with st.expander(f"{group_name} (來源：Yahoo實時)", expanded=expanded):
                cols = st.columns(4)
                for idx, (label, symbol) in enumerate(tokens.items()):
                    stock = yahoo_data.get(symbol)
                    if stock and stock['price'] > 0:
                        cols[idx % 4].metric(label, f"${stock['price']:,.2f}", f"{stock['change']:.2f}%")
                    else:
                        cols[idx % 4].warning(f"無 {symbol}")

    auto_refresh_dual_engine()

# 【分頁 2】記憶體產業區塊
with tab2:
    st.subheader("記憶體大廠指標股")
    memory_tickers = {
        "美光 Micron": "MU", "南亞科": "2408.TW", "華邦電": "2344.TW", "威騰 WD": "WDC"
    }
    selected_memory = st.selectbox("選擇記憶體指標：", list(memory_tickers.keys()))
    if st.button("取得記憶體指標報價"):
        symbol = memory_tickers[selected_memory]
        with st.spinner("連線至 Yahoo 抓取中..."):
            try:
                current_price = get_yahoo_price(symbol)
                if current_price: st.metric(label=f"{selected_memory} 最新報價", value=f"{current_price:.2f}")
                else: st.warning("⚠️ 查無報價。")
            except Exception as e: st.error(f"❌ 抓取失敗：{e}")

# 【分頁 3】投資計畫與資產試算 (009816 & QQQM)
with tab3:
    st.subheader("⭐ 長期投資計畫與資產試算")
    st.info("根據你的計畫：長期投資 QQQM (美股) 與 009816 (台股不配息市值型 ETF)")
    
    live_qqqm_price = 0.0
    live_009816_price = 0.0
    with st.spinner("正在更新試算匯率與價格..."):
        try:
            live_qqqm_price = get_yahoo_price("QQQM")
            live_009816_price = get_yahoo_price("009816.TW")
        except: pass

    if live_qqqm_price and live_009816_price:
        col_inv1, col_inv2 = st.columns(2)
        with col_inv1:
            qqqm_shares = st.number_input("目前持有 QQQM 股數：", min_value=0.0, value=0.0, step=0.1)
            st.write(f"現值：**${(qqqm_shares * live_qqqm_price):,.2f}** USD")
        with col_inv2:
            tw_shares = st.number_input("目前持有 009816 股數：", min_value=0.0, value=0.0, step=1.0)
            tw_value_twd = tw_shares * live_009816_price
            st.write(f"現值：**NT$ {tw_value_twd:,.0f}**")
            
        st.divider()
        exchange_rate = 32.5
        total_twd = (qqqm_shares * live_qqqm_price * exchange_rate) + tw_value_twd
        st.success(f"### 總資產估值：**NT$ {total_twd:,.0f}**")
    else:
        st.warning("無法取得試算價格，請稍後再試。")

st.divider()

# --- 4. 產業新聞與 AI 總結區塊 ---
st.header("📰 產業新聞與 AI 總結")
search_query = st.text_input("請輸入你想查詢的產業或公司：", "例如：009816 凱基台灣 表現")
if st.button("取得最新消息與 AI 總結"):
    with st.spinner("抓取新聞中..."):
        news_data = get_google_news(search_query)
        if news_data:
            news_text = ""
            for idx, news in enumerate(news_data):
                st.markdown(f"**{idx + 1}. [{news['title']}]({news['link']})**")
                news_text += f"- {news['title']}\n"
            if api_key:
                with st.spinner("🤖 AI 正在閱讀..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        res = model.generate_content(f"請總結3個產業重點：\n\n{news_text}")
                        st.info("### 🤖 AI 重點總結")
                        st.write(res.text)
                    except Exception as e: st.error(f"❌ AI 錯誤：{e}")
            else: st.warning("⚠️ 請輸入 Gemini API Key！")
        else: st.error("❌ 抓取失敗。")