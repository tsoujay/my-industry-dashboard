import streamlit as st
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import google.generativeai as genai
import threading 
from youtube_transcript_api import YouTubeTranscriptApi # 新增：YouTube 字幕抓取神器

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
            if len(news_list) >= 10: break
        return news_list
    except: return None

# --- Yahoo 抓取神技 (單一與多執行緒) ---
def fetch_yahoo_single(sym, result_dict):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        valid = [p for p in closes if p is not None]
        if len(valid) >= 2:
            result_dict[sym] = {'price': valid[-1], 'change': ((valid[-1] - valid[-2]) / valid[-2]) * 100}
        elif len(valid) == 1:
            result_dict[sym] = {'price': valid[0], 'change': 0.0}
    except: pass 

def get_yahoo_bulk_threaded(symbols_list):
    result = {}
    threads = []
    for sym in symbols_list:
        t = threading.Thread(target=fetch_yahoo_single, args=(sym, result))
        threads.append(t)
        t.start()
    for t in threads: t.join()
    return result

# --- 新增：YouTube 網址解析工具 ---
def get_yt_video_id(url):
    try:
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.hostname == 'youtu.be': return parsed_url.path[1:]
        if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
            if parsed_url.path == '/watch': return urllib.parse.parse_qs(parsed_url.query)['v'][0]
    except: return None
    return None

# --- 2. 介面與設定 ---
st.set_page_config(page_title="即時產業問答中心", page_icon="📈", layout="wide")
st.title("📈 我的終極財經資訊中心")

st.sidebar.header("⚙️ 系統設定")
api_key = st.sidebar.text_input("輸入 Gemini API Key (啟動 AI):", type="password").strip()

# --- 建立 5 大分頁 ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🪙 全市場儀表板", "💾 記憶體產業", "⭐ 投資與試算", "📖 SA 助理", "🎧 KOL 提煉"
])

# 【分頁 1】全市場即時儀表板 (保留原本的強大雙引擎)
with tab1:
    st.subheader("🪙 全市場即時儀表板 (Crypto & 美股)")
    st.caption("⏱️ 每 30 秒自動抓取最新報價...")
    pionex_tokens = {"Bitcoin (BTC)": "BTC_USDT", "Ethereum (ETH)": "ETH_USDT", "Cardano (ADA)": "ADA_USDT"}
    yahoo_groups = {
        "💻 科技巨頭與半導體": {"英偉達 (NVDA)": "NVDA", "特斯拉 (TSLA)": "TSLA", "蘋果 (AAPL)": "AAPL", "微軟 (MSFT)": "MSFT", "美光 (MU)": "MU", "超微 (AMD)": "AMD", "台積電 (TSM)": "TSM"},
        "🥇 貴金屬與期貨": {"黃金期貨 (GC=F)": "GC=F", "白銀期貨 (SI=F)": "SI=F", "原油 (USO)": "USO"},
        "📈 指數與 ETF": {"納斯達克 (QQQ)": "QQQ", "標普500 (SPY)": "SPY", "半導體 (SOXX)": "SOXX"}
    }
    @st.fragment(run_every="30s")
    def auto_refresh_dual_engine():
        pionex_data = {}
        try:
            res = requests.get("https://api.pionex.com/api/v1/market/tickers", timeout=5)
            for t in res.json().get('data', {}).get('tickers', []): pionex_data[t['symbol']] = t
        except: pass

        with st.expander("🌟 加密貨幣 (Pionex)"):
            cols = st.columns(3)
            for idx, (label, symbol) in enumerate(pionex_tokens.items()):
                if crypto := pionex_data.get(symbol):
                    cols[idx % 3].metric(label, f"${float(crypto.get('close', 0)):,.2f}", f"{float(crypto.get('change24h', 0))*100:.2f}%")

        all_yahoo = [sym for group in yahoo_groups.values() for sym in group.values()]
        yahoo_data = get_yahoo_bulk_threaded(all_yahoo)
        for group_name, tokens in yahoo_groups.items():
            with st.expander(f"{group_name} (Yahoo實時)"):
                cols = st.columns(4)
                for idx, (label, symbol) in enumerate(tokens.items()):
                    if stock := yahoo_data.get(symbol):
                        if stock['price'] > 0: cols[idx % 4].metric(label, f"${stock['price']:,.2f}", f"{stock['change']:.2f}%")
    auto_refresh_dual_engine()

# 【分頁 2】記憶體產業
with tab2:
    st.subheader("💾 記憶體大廠指標股")
    memory_tickers = {"美光 Micron": "MU", "南亞科": "2408.TW", "華邦電": "2344.TW", "威騰 WD": "WDC"}
    selected_memory = st.selectbox("選擇記憶體指標：", list(memory_tickers.keys()))
    if st.button("取得記憶體指標報價"):
        res_dict = {}
        fetch_yahoo_single(memory_tickers[selected_memory], res_dict)
        if memory_tickers[selected_memory] in res_dict:
            st.metric(label=f"{selected_memory} 最新報價", value=f"{res_dict[memory_tickers[selected_memory]]['price']:.2f}")

# 【分頁 3】超級複利試算機
with tab3:
    st.subheader("⭐ 長期投資計畫與複利試算")
    res_dict = {}
    fetch_yahoo_single("QQQM", res_dict)
    fetch_yahoo_single("009816.TW", res_dict)
    live_qqqm = res_dict.get("QQQM", {}).get("price", 0.0)
    live_tw = res_dict.get("009816.TW", {}).get("price", 0.0)
    
    if live_qqqm and live_tw:
        col1, col2 = st.columns(2)
        with col1: qqqm_shares = st.number_input("持有 QQQM 股數：", value=0.0, step=0.1)
        with col2: tw_shares = st.number_input("持有 009816 股數：", value=0.0, step=1.0)
        ex_rate = st.number_input("預估匯率：", value=32.5)
        st.success(f"**當前總資產現值：NT$ {(qqqm_shares*live_qqqm*ex_rate) + (tw_shares*live_tw):,.0f}**")

# 【分頁 4】Seeking Alpha
with tab4:
    st.subheader("📖 Seeking Alpha AI 助理")
    sa_article = st.text_area("貼上 SA 英文長文：", height=200)
    if st.button("🚀 深度解析 SA 文章"):
        if api_key and sa_article:
            with st.spinner("分析中..."):
                genai.configure(api_key=api_key)
                res = genai.GenerativeModel('gemini-2.5-flash').generate_content(f"請以繁體中文總結：1.核心觀點 2.看多理由 3.看空風險 4.關鍵數據\n\n{sa_article}")
                st.write(res.text)

# 【分頁 5】全新：財經 KOL 影音/貼文提煉引擎
with tab5:
    st.subheader("🎧 財經 KOL 重點提煉引擎")
    st.info("支援名單：股癌、財女珍妮、游庭皓、宏爺講股、各大 FB 財經粉專等。")
    
    # 選擇來源類型
    source_type = st.radio("請選擇您要提煉的資訊來源：", ["🎥 YouTube 影片網址 (自動抓取字幕)", "📝 Facebook 貼文 (手動複製貼上)"])
    
    if "YouTube" in source_type:
        yt_url = st.text_input("🔗 請貼上 YouTube 影片網址 (例如股癌最新一集)：")
        if st.button("🎯 擷取字幕並整理重點"):
            if not api_key: st.warning("請先輸入 API Key！")
            elif not yt_url: st.warning("請貼上網址！")
            else:
                video_id = get_yt_video_id(yt_url)
                if video_id:
                    with st.spinner("正在破解 YouTube 字幕..."):
                        try:
                            # 嘗試抓取繁體/簡體中文或自動翻譯的字幕
                            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['zh-TW', 'zh-Hant', 'zh-Hans', 'en'])
                            full_text = " ".join([t['text'] for t in transcript])
                            
                            with st.spinner("🤖 字幕抓取成功！AI 正在提煉總結..."):
                                genai.configure(api_key=api_key)
                                prompt = f"""
                                這是一段財經 YouTube 節目的完整字幕。請幫我過濾掉閒聊與廣告，用專業的繁體中文條列式整理出精華：
                                1. 🌍 宏觀經濟與大盤觀點 (利率、通膨、美股台股大盤趨勢)
                                2. 🎯 點名的產業與個股 (提到哪些股票？看好還是看壞？)
                                3. ⚠️ 潛在風險與操作建議 (講者建議的資金控管或避開的雷區)
                                
                                節目字幕內容：
                                {full_text}
                                """
                                res = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
                                st.success("✅ 重點提煉完成！")
                                st.write(res.text)
                        except Exception as e:
                            st.error("❌ 無法抓取這部影片的字幕。可能影片未提供 cc 字幕，或受到版權保護。")
                else:
                    st.error("❌ 網址格式錯誤，請確認是有效的 YouTube 網址。")
                    
    else:
        # Facebook 貼文區塊
        fb_post = st.text_area("📝 請貼上 Facebook 長篇貼文內容：", height=200)
        if st.button("🎯 分析貼文重點"):
            if not api_key: st.warning("請先輸入 API Key！")
            elif not fb_post: st.warning("請貼上貼文內容！")
            else:
                with st.spinner("🤖 AI 正在解構大神的貼文邏輯..."):
                    genai.configure(api_key=api_key)
                    prompt = f"""
                    這是一篇來自知名財經 KOL 的社群貼文。請用專業的繁體中文，精煉出貼文中的投資價值：
                    1. 💡 核心觀點 (用兩句話總結這篇貼文最想表達的重點)
                    2. 📊 數據支持與邏輯 (作者用了哪些總經數據或財報來支持他的論點？)
                    3. 💰 提到的標的與板塊 (若無則寫「未提及具體標的」)
                    4. 結論 (投資人可以從中獲得什麼啟發？)
                    
                    貼文內容：
                    {fb_post}
                    """
                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
                    st.success("✅ 重點提煉完成！")
                    st.write(res.text) 