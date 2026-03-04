import streamlit as st
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import google.generativeai as genai
import threading 
from youtube_transcript_api import YouTubeTranscriptApi

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

# --- YouTube 網址解析工具 ---
def get_yt_video_id(url):
    try:
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.hostname == 'youtu.be': return parsed_url.path[1:]
        if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
            if parsed_url.path == '/watch': return urllib.parse.parse_qs(parsed_url.query)['v'][0]
    except: return None
    return None

# --- 2. 介面與設定 ---
st.set_page_config(page_title="TSOU財經資訊中心", page_icon="📈", layout="wide")
st.title("📈 TSOU財經資訊中心")

st.sidebar.header("⚙️ 系統設定")
api_key = st.sidebar.text_input("輸入 Gemini API Key (啟動 AI):", type="password").strip()

# --- 3. 建立 5 大分頁 ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📖 SA 助理", "🎧 KOL 提煉", "🪙 全市場儀表板", "💾 記憶體產業", "⭐ 投資與試算"
])

# 【分頁 1】Seeking Alpha AI 專業助理
with tab1:
    st.subheader("📖 Seeking Alpha AI 專業閱讀助理")
    st.markdown("將冗長的英文分析報告，瞬間轉換為結構化的中文多空決策指南。")
    
    col_sa1, col_sa2 = st.columns([2, 1])
    with col_sa2:
        st.info("💡 **優化指南**\n\n1. 複製 SA 文章全文\n2. 選擇分析側重點\n3. 點擊生成報告")
        focus_area = st.selectbox("🎯 選擇分析側重點：", ["全面平衡分析 (預設)", "偏重看多與護城河分析", "偏重看空與財報風險預警"])
    with col_sa1:
        sa_article = st.text_area("📝 請在此貼上 Seeking Alpha 文章內容：", height=250)
    
    if st.button("🚀 AI 深度解析 SA 文章", use_container_width=True):
        if not api_key: st.warning("⚠️ 請先在左側輸入 API Key！")
        elif not sa_article.strip(): st.warning("⚠️ 請貼上文章內容！")
        else:
            with st.spinner("🤖 華爾街 AI 助教正在深度解析文章，請稍候..."):
                try:
                    genai.configure(api_key=api_key)
                    focus_prompt = ""
                    if focus_area == "偏重看多與護城河分析": focus_prompt = "請特別深度挖掘文章中看好該公司的理由、競爭優勢（護城河）以及未來的潛在催化劑。"
                    elif focus_area == "偏重看空與財報風險預警": focus_prompt = "請特別深度挖掘文章中提到的潛在風險、財報隱憂、總體經濟的不利因素或競爭劣勢。"
                    else: focus_prompt = "請客觀平衡地呈現文章的多空觀點。"

                    sa_prompt = f"""
                    你現在是一位專業的華爾街首席分析師。請幫我閱讀以下這篇 Seeking Alpha 的分析文章，
                    並以「繁體中文」輸出以下結構化的重點整理，幫助我大幅提升閱讀速度與決策效率：
                    {focus_prompt}
                    1. 🎯 【核心觀點】：一句話總結作者對這檔標的的主要看法（強烈買進、持有、還是賣出？原因為何？）。
                    2. 🐂 【看多論點與護城河】：條列式列出作者認為會上漲的理由或優勢。
                    3. 🐻 【看空論點與風險】：條列式列出作者提到的隱憂或財報弱點。
                    4. 💡 【關鍵數據與催化劑】：列出文章中提到的重要財報數據或即將發生的關鍵事件。
                    文章內容如下：
                    {sa_article}
                    """
                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(sa_prompt)
                    st.success(f"✅ 解析完成！(模式：{focus_area})")
                    st.markdown("---")
                    st.write(res.text)
                except Exception as e:
                    st.error(f"❌ AI 解析失敗：{e}")

# 【分頁 2】財經 KOL 影音/貼文提煉引擎 (加入強制翻譯與抓蟲雷達)
with tab2:
    st.subheader("🎧 財經 KOL 重點提煉引擎")
    st.info("支援名單：股癌、財女珍妮、游庭皓、宏爺講股、各大 FB 財經粉專等。")
    
    source_type = st.radio("請選擇您要提煉的資訊來源：", ["🎥 YouTube 影片網址 (自動擷取字幕)", "📝 Facebook 貼文 (手動複製貼上)"])
    
    if "YouTube" in source_type:
        yt_url = st.text_input("🔗 請貼上 YouTube 影片網址 (例如股癌最新一集)：")
        if st.button("🎯 擷取字幕並整理重點"):
            if not api_key: st.warning("請先輸入 API Key！")
            elif not yt_url: st.warning("請貼上網址！")
            else:
                video_id = get_yt_video_id(yt_url)
                if video_id:
                    with st.spinner("🕵️‍♂️ 正在突破 YouTube 限制，掃描所有可用字幕..."):
                        try:
                            # 1. 取得這部影片所有的字幕清單
                            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                            transcript = None
                            
                            try:
                                # 策略 A：先找標準的繁中或簡中
                                transcript = transcript_list.find_transcript(['zh-TW', 'zh-Hant', 'zh', 'zh-Hans']).fetch()
                            except:
                                # 策略 B：找不到中文，就隨便抓一個語言（比如自動生成的英文/印尼文等），然後「強制翻譯」成繁體中文！
                                for t in transcript_list:
                                    transcript = t.translate('zh-Hant').fetch()
                                    break
                            
                            if transcript:
                                full_text = " ".join([t['text'] for t in transcript])
                                with st.spinner("🤖 字幕擷取成功！AI 正在為您提煉總結..."):
                                    genai.configure(api_key=api_key)
                                    prompt = f"""這是一段財經 YouTube 節目的完整字幕。請幫我過濾閒聊，用專業的「繁體中文」條列整理：
                                    1. 🌍 宏觀經濟與大盤觀點 
                                    2. 🎯 點名的產業與個股 
                                    3. ⚠️ 潛在風險與操作建議 \n\n字幕內容：{full_text}"""
                                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
                                    st.success("✅ 重點提煉完成！")
                                    st.write(res.text)
                            else: 
                                st.error("❌ 找不到任何語言的字幕。")
                        except Exception as e: 
                            # 把真實的 YouTube 阻擋原因印出來
                            st.error(f"❌ 抓取失敗！YouTube 伺服器阻擋或發生錯誤。\n\n**詳細技術原因：** `{str(e)}`")
                            st.info("💡 提示：Streamlit 雲端主機有時會被 YouTube 暫時封鎖 IP。如果持續發生，建議先改用下方的「Facebook 貼文提煉」功能，把 KOL 的節目筆記貼上來分析！")
                else: 
                    st.error("❌ 網址格式錯誤。")
    else:
        fb_post = st.text_area("📝 請貼上 Facebook 長篇貼文內容：", height=200)
        if st.button("🎯 分析貼文重點"):
            if api_key and fb_post:
                with st.spinner("🤖 AI 正在解構大神邏輯..."):
                    genai.configure(api_key=api_key)
                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(f"請精煉貼文投資價值：1.核心觀點 2.數據支持與邏輯 3.提到的標的 4.結論\n\n{fb_post}")
                    st.write(res.text)

# 【分頁 3】全市場即時儀表板
with tab3:
    st.subheader("🪙 全市場即時儀表板 (Crypto & 美股)")
    st.caption("⏱️ 雙引擎運作中：系統將每 30 秒自動為您抓取最新報價...")
    pionex_tokens = {"Bitcoin (BTC)": "BTC_USDT", "Ethereum (ETH)": "ETH_USDT", "Cardano (ADA)": "ADA_USDT"}
    yahoo_groups = {
        "💻 科技巨頭與半導體 (真實美股)": {"英偉達 (NVDA)": "NVDA", "特斯拉 (TSLA)": "TSLA", "蘋果 (AAPL)": "AAPL", "微軟 (MSFT)": "MSFT", "美光 (MU)": "MU", "超微 (AMD)": "AMD", "台積電 (TSM)": "TSM"},
        "🥇 貴金屬與能源期貨": {"黃金期貨 (GC=F)": "GC=F", "白銀期貨 (SI=F)": "SI=F", "原油ETF (USO)": "USO"},
        "📈 指數與 ETF": {"納斯達克 (QQQ)": "QQQ", "標普500 (SPY)": "SPY", "半導體ETF (SOXX)": "SOXX"},
        "🚀 其他熱門話題美股": {"Coinbase (COIN)": "COIN", "微策略 (MSTR)": "MSTR", "Palantir (PLTR)": "PLTR"}
    }
    @st.fragment(run_every="30s")
    def auto_refresh_dual_engine():
        pionex_data = {}
        try:
            res = requests.get("https://api.pionex.com/api/v1/market/tickers", timeout=5)
            for t in res.json().get('data', {}).get('tickers', []): pionex_data[t['symbol']] = t
        except: pass
        with st.expander("🌟 主流加密貨幣 (來源：Pionex)", expanded=True):
            cols = st.columns(3)
            for idx, (label, symbol) in enumerate(pionex_tokens.items()):
                crypto = pionex_data.get(symbol)
                if crypto: cols[idx % 3].metric(label, f"${float(crypto.get('close', 0)):,.2f}", f"{float(crypto.get('change24h', 0))*100:.2f}%")
        
        all_yahoo = [sym for group in yahoo_groups.values() for sym in group.values()]
        yahoo_data = get_yahoo_bulk_threaded(all_yahoo)
        for group_name, tokens in yahoo_groups.items():
            with st.expander(f"{group_name} (來源：Yahoo實時)"):
                cols = st.columns(4)
                for idx, (label, symbol) in enumerate(tokens.items()):
                    stock = yahoo_data.get(symbol)
                    if stock and stock['price'] > 0:
                        fmt_price = f"${stock['price']:,.4f}" if stock['price'] < 1 else f"${stock['price']:,.2f}"
                        cols[idx % 4].metric(label, fmt_price, f"{stock['change']:.2f}%")
    auto_refresh_dual_engine()

# 【分頁 4】記憶體產業
with tab4:
    st.subheader("💾 記憶體大廠指標股")
    memory_tickers = {"美光 Micron": "MU", "南亞科": "2408.TW", "華邦電": "2344.TW", "威騰 WD": "WDC"}
    selected_memory = st.selectbox("選擇記憶體指標：", list(memory_tickers.keys()))
    if st.button("取得報價"):
        res_dict = {}
        fetch_yahoo_single(memory_tickers[selected_memory], res_dict)
        if memory_tickers[selected_memory] in res_dict:
            st.metric(label=f"{selected_memory} 最新報價", value=f"{res_dict[memory_tickers[selected_memory]]['price']:.2f}")

# 【分頁 5】投資計畫與超級複利試算機
with tab5:
    st.subheader("⭐ 長期投資計畫與超級複利試算機")
    
    live_qqqm = 0.0
    live_tw = 0.0
    with st.spinner("正在抓取最新市場價格..."):
        try:
            res_dict = {}
            fetch_yahoo_single("QQQM", res_dict)
            fetch_yahoo_single("009816.TW", res_dict)
            live_qqqm = res_dict.get("QQQM", {}).get("price", 0.0)
            live_tw = res_dict.get("009816.TW", {}).get("price", 0.0)
        except: pass

    if live_qqqm and live_tw:
        st.markdown("### 1️⃣ 目前資產現值")
        col_inv1, col_inv2 = st.columns(2)
        with col_inv1:
            qqqm_shares = st.number_input("目前持有 QQQM 股數：", min_value=0.0, value=0.0, step=0.1)
            qqqm_current_usd = qqqm_shares * live_qqqm
            st.write(f"現值：**${qqqm_current_usd:,.2f}** USD")
        with col_inv2:
            tw_shares = st.number_input("目前持有 009816 股數：", min_value=0.0, value=0.0, step=1.0)
            tw_current_twd = tw_shares * live_tw
            st.write(f"現值：**NT$ {tw_current_twd:,.0f}**")
            
        exchange_rate = st.number_input("預估美金匯率：", min_value=28.0, value=32.5, step=0.1)
        total_current_twd = (qqqm_current_usd * exchange_rate) + tw_current_twd
        st.success(f"**當前總資產估值：NT$ {total_current_twd:,.0f}**")

        st.divider()

        st.markdown("### 2️⃣ 🚀 未來複利推算 (定期定額)")
        invest_years = st.slider("預計投資年限 (年)：", min_value=1, max_value=40, value=20)
        
        col_calc1, col_calc2 = st.columns(2)
        with col_calc1:
            st.markdown("#### 🇺🇸 QQQM 計畫")
            qqqm_monthly = st.number_input("每月投入 (USD)：", min_value=0, value=40, step=10)
            qqqm_rate = st.number_input("QQQM 預估年化報酬率 (%)：", min_value=1.0, value=10.0, step=0.5)
        with col_calc2:
            st.markdown("#### 🇹🇼 009816 計畫")
            tw_monthly = st.number_input("每月投入 (TWD)：", min_value=0, value=24375, step=1000)
            tw_rate = st.number_input("009816 預估年化報酬率 (%)：", min_value=1.0, value=8.0, step=0.5)

        months = invest_years * 12
        qqqm_m_rate = (qqqm_rate / 100) / 12
        qqqm_fv_present = qqqm_current_usd * ((1 + qqqm_m_rate) ** months)
        qqqm_fv_future = qqqm_monthly * (((1 + qqqm_m_rate) ** months - 1) / qqqm_m_rate) if qqqm_m_rate > 0 else qqqm_monthly * months
        qqqm_total_fv_usd = qqqm_fv_present + qqqm_fv_future

        tw_m_rate = (tw_rate / 100) / 12
        tw_fv_present = tw_current_twd * ((1 + tw_m_rate) ** months)
        tw_fv_future = tw_monthly * (((1 + tw_m_rate) ** months - 1) / tw_m_rate) if tw_m_rate > 0 else tw_monthly * months
        tw_total_fv_twd = tw_fv_present + tw_fv_future

        total_future_twd = (qqqm_total_fv_usd * exchange_rate) + tw_total_fv_twd
        total_invested_twd = total_current_twd + (qqqm_monthly * exchange_rate * months) + (tw_monthly * months)

        st.info(f"💡 {invest_years} 年後，您的累積投入總本金約為：**NT$ {total_invested_twd:,.0f}**")
        st.error(f"🎉 **{invest_years} 年後總資產預估達：NT$ {total_future_twd:,.0f}**")

        with st.expander("📊 查看詳細試算結果"):
            st.write(f"- **QQQM 未來總價值**：${qqqm_total_fv_usd:,.2f} USD (折合台幣約 NT$ {qqqm_total_fv_usd*exchange_rate:,.0f})")
            st.write(f"- **009816 未來總價值**：NT$ {tw_total_fv_twd:,.0f}")
            profit = total_future_twd - total_invested_twd
            st.write(f"- **時間創造的複利淨收益**：NT$ {profit:,.0f}")