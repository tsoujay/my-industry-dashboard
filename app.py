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

# --- 3. 建立 6 大分頁 (加入新聞區塊) ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📖 SA 助理", "🎧 KOL 提煉", "🪙 全市場儀表板", "💾 記憶體產業", "⭐ 投資與試算", "📰 產業新聞"
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
                    st.write(