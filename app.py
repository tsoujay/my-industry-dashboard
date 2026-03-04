import streamlit as st
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import google.generativeai as genai
import threading 

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

# --- 新增：Yahoo 單一神技 ---
def fetch_yahoo_single(sym, result_dict):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        data = res.json()
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        valid = [p for p in closes if p is not None]
        if len(valid) >= 2:
            price = valid[-1]
            prev = valid[-2]
            result_dict[sym] = {'price': price, 'change': ((price - prev) / prev) * 100}
        elif len(valid) == 1:
            result_dict[sym] = {'price': valid[0], 'change': 0.0}
    except:
        pass 

# --- 新增：多執行緒批次抓取 ---
def get_yahoo_bulk_threaded(symbols_list):
    result = {}
    threads = []
    for sym in symbols_list:
        t = threading.Thread(target=fetch_yahoo_single, args=(sym, result))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return result

# --- 2. 介面與設定 ---
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
    
    pionex_tokens = {
        "Bitcoin (BTC)": "BTC_USDT", "Ethereum (ETH)": "ETH_USDT", "Cardano (ADA)": "ADA_USDT"
    }
    
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
        pionex_data = {}
        try:
            res = requests.get("https://api.pionex.com/api/v1/market/tickers", timeout=5)
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

        all_yahoo_symbols = []
        for group in yahoo_groups.values():
            all_yahoo_symbols.extend(group.values())
        
        yahoo_data = get_yahoo_bulk_threaded(all_yahoo_symbols)

        for group_name, tokens in yahoo_groups.items():
            expanded = True if "科技巨頭" in group_name else False
            with st.expander(f"{group_name} (來源：Yahoo實時)", expanded=expanded):
                cols = st.columns(4)
                for idx, (label, symbol) in enumerate(tokens.items()):
                    stock = yahoo_data.get(symbol)
                    if stock and stock['price'] > 0:
                        formatted_price = f"${stock['price']:,.4f}" if stock['price'] < 1 else f"${stock['price']:,.2f}"
                        cols[idx % 4].metric(label, formatted_price, f"{stock['change']:.2f}%")
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
                res_dict = {}
                fetch_yahoo_single(symbol, res_dict)
                if symbol in res_dict: 
                    st.metric(label=f"{selected_memory} 最新報價", value=f"{res_dict[symbol]['price']:.2f}")
                else: 
                    st.warning("⚠️ 查無有效報價，可能為非交易時間。")
            except Exception as e: st.error(f"❌ 抓取失敗：{e}")

# 【分頁 3】超級複利試算機 (009816 & QQQM)
with tab3:
    st.subheader("⭐ 長期投資計畫與複利試算")
    st.info("透過設定每月投入與預估年化報酬，推算未來的資產成長軌跡！")
    
    live_qqqm_price = 0.0
    live_009816_price = 0.0
    with st.spinner("正在抓取最新市場價格..."):
        try:
            res_dict = {}
            fetch_yahoo_single("QQQM", res_dict)
            fetch_yahoo_single("009816.TW", res_dict)
            live_qqqm_price = res_dict.get("QQQM", {}).get("price", 0.0)
            live_009816_price = res_dict.get("009816.TW", {}).get("price", 0.0)
        except: pass

    if live_qqqm_price and live_009816_price:
        # --- 第一區塊：現值計算 ---
        st.markdown("### 1️⃣ 目前資產現值")
        col_inv1, col_inv2 = st.columns(2)
        
        with col_inv1:
            qqqm_shares = st.number_input("目前持有 QQQM 股數：", min_value=0.0, value=0.0, step=0.1)
            qqqm_current_value_usd = qqqm_shares * live_qqqm_price
            st.write(f"現值：**${qqqm_current_value_usd:,.2f}** USD")
            
        with col_inv2:
            tw_shares = st.number_input("目前持有 009816 股數：", min_value=0.0, value=0.0, step=1.0)
            tw_current_value_twd = tw_shares * live_009816_price
            st.write(f"現值：**NT$ {tw_current_value_twd:,.0f}**")
            
        exchange_rate = st.number_input("預估美金匯率：", min_value=28.0, value=32.5, step=0.1)
        total_current_twd = (qqqm_current_value_usd * exchange_rate) + tw_current_value_twd
        st.success(f"**當前總資產估值：NT$ {total_current_twd:,.0f}**")

        st.divider()

        # --- 第二區塊：未來複利推算 ---
        st.markdown("### 2️⃣ 🚀 未來複利推算 (定期定額)")
        invest_years = st.slider("預計投資年限 (年)：", min_value=1, max_value=40, value=20)
        
        col_calc1, col_calc2 = st.columns(2)
        with col_calc1:
            st.markdown("#### 🇺🇸 QQQM 計畫")
            qqqm_monthly = st.number_input("每月投入 (USD)：", min_value=0, value=40, step=10)
            qqqm_rate = st.number_input("預估年化報酬率 (%)：", min_value=1.0, value=10.0, step=0.5, key="q_rate")

        with col_calc2:
            st.markdown("#### 🇹🇼 009816 計畫")
            tw_monthly = st.number_input("每月投入 (TWD)：", min_value=0, value=24375, step=1000)
            tw_rate = st.number_input("預估年化報酬率 (%)：", min_value=1.0, value=8.0, step=0.5, key="tw_rate")

        # --- 複利計算邏輯 ---
        months = invest_years * 12

        # QQQM 計算 (按月複利)
        qqqm_monthly_rate = (qqqm_rate / 100) / 12
        qqqm_fv_present = qqqm_current_value_usd * ((1 + qqqm_monthly_rate) ** months)
        qqqm_fv_future = qqqm_monthly * (((1 + qqqm_monthly_rate) ** months - 1) / qqqm_monthly_rate) if qqqm_monthly_rate > 0 else qqqm_monthly * months
        qqqm_total_fv_usd = qqqm_fv_present + qqqm_fv_future

        # 009816 計算 (按月複利)
        tw_monthly_rate = (tw_rate / 100) / 12
        tw_fv_present = tw_current_value_twd * ((1 + tw_monthly_rate) ** months)
        tw_fv_future = tw_monthly * (((1 + tw_monthly_rate) ** months - 1) / tw_monthly_rate) if tw_monthly_rate > 0 else tw_monthly * months
        tw_total_fv_twd = tw_fv_present + tw_fv_future

        total_future_twd = (qqqm_total_fv_usd * exchange_rate) + tw_total_fv_twd
        total_invested_twd = total_current_twd + (qqqm_monthly * exchange_rate * months) + (tw_monthly * months)

        # 顯示最終結果
        st.info(f"💡 {invest_years} 年後，您的累積投入總本金約為：**NT$ {total_invested_twd:,.0f}**")
        st.error(f"🎉 **{invest_years} 年後總資產預估達：NT$ {total_future_twd:,.0f}**")

        with st.expander("📊 查看詳細試算結果"):
            st.write(f"- **QQQM 未來總價值**：${qqqm_total_fv_usd:,.2f} USD (折合台幣約 NT$ {qqqm_total_fv_usd*exchange_rate:,.0f})")
            st.write(f"- **009816 未來總價值**：NT$ {tw_total_fv_twd:,.0f}")
            profit = total_future_twd - total_invested_twd
            st.write(f"- **時間創造的複利淨收益**：NT$ {profit:,.0f}")

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