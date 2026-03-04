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

# --- 直連 Yahoo 底層的報價神技 ---
def get_yahoo_price(symbol):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        valid_prices = [p for p in closes if p is not None]
        if valid_prices:
            return valid_prices[-1]
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

tab1, tab2, tab3 = st.tabs(["🪙 加密貨幣與美股代幣 (Pionex)", "💾 記憶體產業 (Yahoo)", "⭐ 投資計畫與試算"])

# 【分頁 1】加密貨幣與美股代幣區塊 (30秒自動更新)
with tab1:
    st.subheader("🪙 Pionex 全市場即時儀表板")
    st.caption("⏱️ 系統將每 30 秒自動在背景為您抓取最新報價...")
    
    @st.fragment(run_every="30s")
    def auto_refresh_crypto():
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
                    col.metric(label, f"${price:,.4f}" if price < 1 else f"${price:,.2f}", f"{change:.2f}%")
                else:
                    col.warning(f"無 {symbol_name}")

            # 主流加密貨幣
            st.markdown("**🌟 主流加密貨幣**")
            c1, c2, c3 = st.columns(3)
            display_crypto_metric(c1, "Bitcoin (BTC)", "BTC_USDT")
            display_crypto_metric(c2, "Ethereum (ETH)", "ETH_USDT")
            display_crypto_metric(c3, "Cardano (ADA)", "ADA_USDT")
            
            # 黃金與白銀代幣
            st.markdown("**🌟 貴金屬代幣**")
            c4, c5, c6 = st.columns(3)
            display_crypto_metric(c4, "Pax Gold (PAXG)", "PAXG_USDT")
            display_crypto_metric(c5, "Tether Gold (XAUT)", "XAUT_USDT")
            display_crypto_metric(c6, "Silver (XAG 等效)", "XAG_USDT") # 若派網未上架白銀會顯示警告
            
            # 美股代幣 (24小時交易)
            st.markdown("**🌟 熱門美股代幣 (24H)**")
            c7, c8, c9 = st.columns(3)
            display_crypto_metric(c7, "Tesla (TSLAX)", "TSLAX_USDT")
            display_crypto_metric(c8, "Nvidia (NVDAX)", "NVDAX_USDT")
            display_crypto_metric(c9, "TSMC (TSMX)", "TSMX_USDT")
            
            c10, c11, c12 = st.columns(3)
            display_crypto_metric(c10, "Apple (AAPLX)", "AAPLX_USDT")
            display_crypto_metric(c11, "Microsoft (MSFTX)", "MSFTX_USDT")
            display_crypto_metric(c12, "Coinbase (COINX)", "COINX_USDT")
            
        except Exception as e:
            st.error(f"儀表板更新失敗，原因：{e}")
            
    auto_refresh_crypto()

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
        with st.spinner("連線至 Yahoo 抓取中..."):
            try:
                current_price = get_yahoo_price(symbol)
                if current_price:
                    st.metric(label=f"{selected_memory} ({symbol}) 最新報價", value=f"{current_price:.2f}")
                else:
                    st.warning("⚠️ 查無有效報價，可能為非交易時間。")
            except Exception as e:
                st.error(f"❌ 報價抓取失敗：{e}")

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
        except:
            live_qqqm_price = 0.0
            live_009816_price = 0.0

    if live_qqqm_price and live_009816_price:
        col_inv1, col_inv2 = st.columns(2)
        
        with col_inv1:
            qqqm_shares = st.number_input("目前持有 QQQM 股數：", min_value=0.0, value=0.0, step=0.1)
            qqqm_value_usd = qqqm_shares * live_qqqm_price
            st.write(f"現值：**${qqqm_value_usd:,.2f}** USD")
            
        with col_inv2:
            tw_shares = st.number_input("目前持有 009816 股數：", min_value=0.0, value=0.0, step=1.0)
            tw_value_twd = tw_shares * live_009816_price
            st.write(f"現值：**NT$ {tw_value_twd:,.0f}**")
            
        st.divider()
        # 假設匯率 32.5 進行加總計算
        exchange_rate = 32.5
        total_twd = (qqqm_value_usd * exchange_rate) + tw_value_twd
        total_usd = qqqm_value_usd + (tw_value_twd / exchange_rate)
        
        st.success(f"### 總資產估值：**NT$ {total_twd:,.0f}**")
        st.caption(f"折合美金約：$ {total_usd:,.2f} USD (以匯率 {exchange_rate} 估算)")
    else:
        st.warning("暫時無法取得試算價格，請確認網路連線或稍後再試。")

st.divider()

# --- 4. 產業新聞與 AI 總結區塊 ---
st.header("📰 產業新聞與 AI 總結")
search_query = st.text_input("請輸入你想查詢的產業或公司：", "例如：009816 凱基台灣 表現")

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