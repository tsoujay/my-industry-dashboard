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

# --- 新增：直連 Yahoo 底層的報價神技 (繞過阻擋) ---
def get_yahoo_price(symbol):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
    # 這段 Header 就是關鍵！讓 Yahoo 以為我們是正常的 Chrome 瀏覽器
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        
        # 潛入 JSON 資料庫深處，把每天的收盤價挖出來
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        
        # 過濾掉那些因為沒開盤而產生空值 (None) 的日子
        valid_prices = [p for p in closes if p is not None]
        
        if valid_prices:
            return valid_prices[-1] # 回傳最後一天的最新價格
        return None
    except Exception as e:
        raise Exception(f"Yahoo 伺服器拒絕連線或代號錯誤 ({e})")

# --- 2. 介面與設定 ---
st.set_page_config(page_title="即時產業問答中心", page_icon="📈")
st.title("📈 我的即時產業問答中心")

st.sidebar.header("⚙️ 系統設定")
api_key = st.sidebar.text_input("輸入你的 Gemini API Key (用於啟動 AI):", type="password").strip()
st.sidebar.caption("※ 貼上後請按 Enter 鍵確認。")

# --- 3. 多重即時數據區塊 ---
st.header("📊 即時市場數據")

tab1, tab2, tab3 = st.tabs(["🪙 加密貨幣 (Pionex)", "💾 記憶體產業 (Yahoo)", "⭐ 個人關注清單"])

# 【分頁 1】加密貨幣區塊 (升級為儀表板模式)
with tab1:
    # 【分頁 1】加密貨幣區塊 (升級為自動更新儀表板)
with tab1:
    st.subheader("🪙 加密貨幣即時儀表板")
    st.caption("⏱️ 系統將每 30 秒自動在背景為您抓取最新報價...")
    
    # 🌟 魔法指令：告訴系統「這個函數裡面的東西」要每 30 秒自己重跑一次
    @st.fragment(run_every="30s")
    def auto_refresh_crypto():
        col1, col2, col3 = st.columns(3)
        try:
            url = "https://api.pionex.com/api/v1/market/tickers"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            tickers_data = {t['symbol']: t for t in data['data']['tickers']}
            
            def display_crypto_metric(col, label, symbol_name):
                crypto = tickers_data.get(symbol_name)
                if crypto:
                    price = float(crypto.get('close', 0))
                    change = float(crypto.get('change24h', 0)) * 100
                    col.metric(label, f"${price:,.2f}", f"{change:.2f}%")
                else:
                    col.warning(f"找不到 {symbol_name}")

            display_crypto_metric(col1, "Bitcoin (BTC)", "BTC_USDT")
            display_crypto_metric(col2, "Ethereum (ETH)", "ETH_USDT")
            display_crypto_metric(col3, "Solana (SOL)", "SOL_USDT")
            
        except Exception as e:
            st.error(f"儀表板更新失敗，原因：{e}")
            
    # 啟動自動更新函數
    auto_refresh_crypto()
    
    st.divider()
    
    # --- 原本的單一幣種查詢功能保留 ---
    st.caption("🔍 查詢其他特定幣種：")
    crypto_tickers = {
        "狗狗幣 (DOGE)": "DOGE_USDT",
        "瑞波幣 (XRP)": "XRP_USDT",
        "艾達幣 (ADA)": "ADA_USDT"
    }
    selected_crypto = st.selectbox("選擇加密貨幣：", list(crypto_tickers.keys()))
    
    if st.button("手動取得報價"):
        symbol = crypto_tickers[selected_crypto]
        with st.spinner(f"連線至 Pionex 抓取中..."):
            try:
                url = f"https://api.pionex.com/api/v1/market/tickers?symbol={symbol}"
                response = requests.get(url)
                response.raise_for_status() 
                data = response.json()
                if data.get("data") and data["data"].get("tickers"):
                    current_price = float(data["data"]["tickers"][0]["close"])
                    st.metric(label=f"{selected_crypto} 最新價格 (USDT)", value=f"{current_price:,.4f}")
                else:
                    st.warning("⚠️ 系統回傳空白資料。")
            except Exception as e:
                st.error(f"❌ 報價抓取失敗：{e}")
# 【分頁 2】記憶體產業區塊
with tab2:
    st.subheader("記憶體大廠指標股")
    st.caption("💡 追蹤全球記憶體巨頭股價，掌握 DRAM 與 NAND 市場資金動向。")
    memory_tickers = {
        "美光 Micron (全球記憶體指標)": "MU",
        "南亞科 (台灣 DRAM 大廠)": "2408.TW",
        "華邦電 (台灣 NOR Flash 大廠)": "2344.TW",
        "威騰 WD (全球 NAND 指標)": "WDC"
    }
    selected_memory = st.selectbox("選擇記憶體指標：", list(memory_tickers.keys()))
    
    if st.button("取得記憶體指標報價"):
        symbol = memory_tickers[selected_memory]
        with st.spinner("偽裝瀏覽器連線至 Yahoo 抓取中..."):
            try:
                current_price = get_yahoo_price(symbol)
                if current_price:
                    st.metric(label=f"{selected_memory} ({symbol}) 最新報價", value=f"{current_price:.2f}")
                else:
                    st.warning("⚠️ 查無有效報價，可能為非交易時間。")
            except Exception as e:
                st.error(f"❌ 報價抓取失敗：{e}")

# 【分頁 3】個人關注清單區塊
with tab3:
    st.subheader("常用關注標的")
    watchlist_tickers = {
        "那斯達克 100 ETF": "QQQ",
        "那斯達克 100 迷你 ETF": "QQQM",
        "雙鴻 (散熱模組)": "3324.TW",
        "Willdan Group (能源基建)": "WLDN"
    }
    selected_watch = st.selectbox("選擇關注標的：", list(watchlist_tickers.keys()))
    
    if st.button("取得關注標的報價"):
        symbol = watchlist_tickers[selected_watch]
        with st.spinner("偽裝瀏覽器連線至 Yahoo 抓取中..."):
            try:
                current_price = get_yahoo_price(symbol)
                if current_price:
                    st.metric(label=f"{selected_watch} ({symbol}) 最新報價", value=f"{current_price:.2f}")
                else:
                    st.warning("⚠️ 查無有效報價，可能為非交易時間。")
            except Exception as e:
                st.error(f"❌ 報價抓取失敗：{e}")

st.divider()

# --- 4. 產業新聞與 AI 總結區塊 ---
st.header("📰 產業新聞與 AI 總結")
search_query = st.text_input("請輸入你想查詢的產業或公司：", "例如：DRAM 記憶體 最新報價與趨勢")

if st.button("取得最新消息與 AI 總結"):
    with st.spinner(f"正在為您抓取「{search_query}」的最新新聞..."):
        news_data = get_google_news(search_query)
        
        if news_data:
            news_text_for_ai = ""
            for idx, news in enumerate(news_data):
                st.markdown(f"**{idx + 1}. [{news['title']}]({news['link']})**")
                news_text_for_ai += f"- {news['title']}\n"
            
            if api_key:
                with st.spinner("🤖 AI 正在閱讀上述新聞，並為您生成重點總結..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        prompt = f"你是一個專業的財經產業分析師。請根據以下最新新聞標題，總結出 3 個最重要的產業趨勢或重點，並用繁體中文條列式回答：\n\n{news_text_for_ai}"
                        response = model.generate_content(prompt)
                        st.info("### 🤖 AI 重點總結")
                        st.write(response.text)
                    except Exception as e:
                        st.error(f"❌ AI 總結失敗！系統回傳錯誤：\n\n {e}")
            else:
                st.warning("⚠️ 若要啟用 AI 自動總結功能，請先在左側欄位貼上你的 Gemini API Key！")
        else:
            st.error("❌ 抓取失敗，沒有相關新聞。")