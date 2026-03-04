import streamlit as st
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import google.generativeai as genai
import threading 
from youtube_transcript_api import YouTubeTranscriptApi
import pandas as pd # 新增：強大的數據表格套件

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

# --- 3. 建立 7 大分頁 ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📖 SA 助理", "🎧 KOL 提煉", "💼 資產總覽", "🪙 全市場儀表板", "💾 記憶體產業", "⭐ 投資與試算", "📰 產業新聞"
])

# 【分頁 1】Seeking Alpha AI 專業助理
with tab1:
    st.subheader("📖 Seeking Alpha AI 專業閱讀助理")
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
                    並以「繁體中文」輸出以下結構化的重點整理：
                    {focus_prompt}
                    1. 🎯 【核心觀點】
                    2. 🐂 【看多論點與護城河】
                    3. 🐻 【看空論點與風險】
                    4. 💡 【關鍵數據與催化劑】
                    文章內容如下：\n{sa_article}
                    """
                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(sa_prompt)
                    st.success(f"✅ 解析完成！(模式：{focus_area})")
                    st.write(res.text)
                except Exception as e: st.error(f"❌ AI 解析失敗：{e}")

# 【分頁 2】財經 KOL 影音/貼文提煉引擎
with tab2:
    st.subheader("🎧 財經 KOL 重點提煉引擎")
    source_type = st.radio("請選擇您要提煉的資訊來源：", ["🎥 YouTube 影片網址 (自動擷取字幕)", "📝 Facebook 貼文 (手動複製貼上)"])
    
    if "YouTube" in source_type:
        yt_url = st.text_input("🔗 請貼上 YouTube 影片網址：")
        if st.button("🎯 擷取字幕並整理重點"):
            if not api_key: st.warning("請先輸入 API Key！")
            elif not yt_url: st.warning("請貼上網址！")
            else:
                video_id = get_yt_video_id(yt_url)
                if video_id:
                    with st.spinner("🕵️‍♂️ 正在掃描所有可用字幕..."):
                        try:
                            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                            transcript = None
                            try: transcript = transcript_list.find_transcript(['zh-TW', 'zh-Hant', 'zh', 'zh-Hans']).fetch()
                            except:
                                for t in transcript_list:
                                    transcript = t.translate('zh-Hant').fetch()
                                    break
                            if transcript:
                                full_text = " ".join([t['text'] for t in transcript])
                                with st.spinner("🤖 字幕擷取成功！AI 正在提煉總結..."):
                                    genai.configure(api_key=api_key)
                                    prompt = f"請幫我過濾閒聊，用專業的「繁體中文」條列整理：\n1. 宏觀經濟與大盤觀點\n2. 點名的產業與個股\n3. 潛在風險與操作建議\n\n字幕內容：{full_text}"
                                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
                                    st.success("✅ 重點提煉完成！")
                                    st.write(res.text)
                            else: st.error("❌ 找不到字幕。")
                        except Exception as e: st.error(f"❌ 抓取失敗！詳細原因：{str(e)}")
                else: st.error("❌ 網址格式錯誤。")
    else:
        fb_post = st.text_area("📝 請貼上 Facebook 貼文內容：", height=200)
        if st.button("🎯 分析貼文重點"):
            if api_key and fb_post:
                with st.spinner("🤖 AI 分析中..."):
                    genai.configure(api_key=api_key)
                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(f"請精煉貼文：1.核心觀點 2.數據與邏輯 3.提到標的 4.結論\n\n{fb_post}")
                    st.write(res.text)

# 【分頁 3】全新：個人資產總覽與動態管理
with tab3:
    st.subheader("💼 個人資產動態管理中心")
    st.markdown("在這裡建立你的投資組合！你可以隨時點擊表格修改「代號」、「數量」與「成本」，系統會自動為你抓取最新市價並結算總資產。")
    
    # 建立一個儲存在雲端網頁暫存中的資料表 (Session State)
    if 'portfolio_df' not in st.session_state:
        st.session_state.portfolio_df = pd.DataFrame({
            '市場分類': ['加密貨幣', '美股', '美股', '台股', '台股', '美股'],
            '標的代號': ['BTC_USDT', 'QQQ', 'QQQM', '009816.TW', '3324.TW', 'WLDN'],
            '持有數量': [0.00, 0.0, 0.0, 0.0, 0.0, 0.0],
            '平均成本': [0.00, 0.0, 0.0, 0.0, 0.0, 0.0]
        })
    
    st.info("💡 **操作提示**：點擊下方表格的數字即可直接修改。如果要新增一筆，點擊表格最下方的空白列即可輸入。")
    
    # 使用可編輯資料表
    edited_df = st.data_editor(
        st.session_state.portfolio_df, 
        num_rows="dynamic", # 允許使用者隨時新增或刪除橫列
        use_container_width=True,
        column_config={
            "市場分類": st.column_config.SelectboxColumn("市場分類", options=["美股", "台股", "加密貨幣"], required=True),
            "標的代號": st.column_config.TextColumn("標的代號 (請務必輸入正確)"),
            "持有數量": st.column_config.NumberColumn("持有數量", format="%.4f"),
            "平均成本": st.column_config.NumberColumn("平均成本", format="%.2f")
        }
    )
    # 把編輯後的資料存回系統
    st.session_state.portfolio_df = edited_df

    st.divider()
    
    col_rate, col_btn = st.columns([1, 2])
    with col_rate:
        usd_to_twd = st.number_input("💵 目前美金兌台幣匯率：", value=32.5, step=0.1)
    with col_btn:
        st.write("") # 排版用空白
        st.write("")
        calculate_btn = st.button("🔄 抓取最新市價並結算總資產", type="primary", use_container_width=True)

    if calculate_btn:
        with st.spinner("🌍 正在全網抓取您持有標的的最新報價..."):
            result_data = []
            total_invested_twd = 0.0
            total_current_twd = 0.0
            
            # 準備抓取資料
            yahoo_symbols = edited_df[edited_df['市場分類'].isin(['美股', '台股'])]['標的代號'].tolist()
            yahoo_prices = get_yahoo_bulk_threaded(yahoo_symbols)
            
            pionex_prices = {}
            try:
                res = requests.get("https://api.pionex.com/api/v1/market/tickers", timeout=5)
                for t in res.json().get('data', {}).get('tickers', []):
                    pionex_prices[t['symbol']] = float(t['close'])
            except: pass

            # 開始結算每一列
            for index, row in edited_df.iterrows():
                market = row['市場分類']
                sym = row['標的代號']
                shares = float(row['持有數量']) if pd.notna(row['持有數量']) else 0.0
                cost = float(row['平均成本']) if pd.notna(row['平均成本']) else 0.0
                
                if not sym or shares == 0: continue
                
                live_price = 0.0
                if market == '加密貨幣': live_price = pionex_prices.get(sym, 0.0)
                else: live_price = yahoo_prices.get(sym, {}).get('price', 0.0)
                
                # 計算單一標的價值
                invested = shares * cost
                current_val = shares * live_price
                roi = ((current_val - invested) / invested * 100) if invested > 0 else 0.0
                
                # 統一換算成台幣以計算總和
                multiplier = usd_to_twd if market in ['美股', '加密貨幣'] else 1.0
                total_invested_twd += (invested * multiplier)
                total_current_twd += (current_val * multiplier)
                
                result_data.append({
                    "標的": sym,
                    "市價": f"{live_price:,.2f}",
                    "總投入": f"{invested:,.2f}",
                    "目前總值": f"{current_val:,.2f}",
                    "報酬率": f"{roi:+.2f}%"
                })

            if result_data:
                st.markdown("### 📊 您的資產結算明細")
                st.table(pd.DataFrame(result_data))
                
                st.divider()
                profit_twd = total_current_twd - total_invested_twd
                st.success(f"### 💰 預估總資產淨值：NT$ {total_current_twd:,.0f}")
                
                if profit_twd >= 0: st.info(f"📈 總未實現損益：+ NT$ {profit_twd:,.0f}")
                else: st.error(f"📉 總未實現損益：- NT$ {abs(profit_twd):,.0f}")
            else:
                st.warning("您目前持有的數量皆為 0，請先在上方表格填寫資產數字！")

# 【分頁 4】全市場即時儀表板
with tab4:
    st.subheader("🪙 全市場即時儀表板 (Crypto & 美股)")
    pionex_tokens = {"Bitcoin (BTC)": "BTC_USDT", "Ethereum (ETH)": "ETH_USDT", "Cardano (ADA)": "ADA_USDT"}
    yahoo_groups = {
        "💻 科技巨頭與半導體": {"英偉達 (NVDA)": "NVDA", "特斯拉 (TSLA)": "TSLA", "蘋果 (AAPL)": "AAPL", "微軟 (MSFT)": "MSFT", "美光 (MU)": "MU", "超微 (AMD)": "AMD", "台積電 (TSM)": "TSM"},
        "🥇 貴金屬與能源": {"黃金期貨 (GC=F)": "GC=F", "白銀期貨 (SI=F)": "SI=F", "原油 (USO)": "USO"},
        "📈 指數與 ETF": {"納斯達克 (QQQ)": "QQQ", "標普500 (SPY)": "SPY", "半導體 (SOXX)": "SOXX"}
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

# 【分頁 5】記憶體產業
with tab5:
    st.subheader("💾 記憶體大廠指標股")
    memory_tickers = {"美光 Micron": "MU", "南亞科": "2408.TW", "華邦電": "2344.TW", "威騰 WD": "WDC"}
    selected_memory = st.selectbox("選擇記憶體指標：", list(memory_tickers.keys()))
    if st.button("取得報價"):
        res_dict = {}
        fetch_yahoo_single(memory_tickers[selected_memory], res_dict)
        if memory_tickers[selected_memory] in res_dict: st.metric(label=f"{selected_memory} 最新報價", value=f"{res_dict[memory_tickers[selected_memory]]['price']:.2f}")

# 【分頁 6】投資計畫與超級複利試算機
with tab6:
    st.subheader("⭐ 長期投資計畫與超級複利試算機")
    live_qqqm, live_tw = 0.0, 0.0
    with st.spinner("抓取價格中..."):
        try:
            res_dict = {}
            fetch_yahoo_single("QQQM", res_dict)
            fetch_yahoo_single("009816.TW", res_dict)
            live_qqqm = res_dict.get("QQQM", {}).get("price", 0.0)
            live_tw = res_dict.get("009816.TW", {}).get("price", 0.0)
        except: pass

    if live_qqqm and live_tw:
        col_inv1, col_inv2 = st.columns(2)
        with col_inv1:
            qqqm_shares = st.number_input("持有 QQQM 股數：", value=0.0, step=0.1)
        with col_inv2:
            tw_shares = st.number_input("持有 009816 股數：", value=0.0, step=1.0)
        exchange_rate = st.number_input("美金匯率：", value=32.5)
        
        invest_years = st.slider("預計投資年限 (年)：", 1, 40, 20)
        col_calc1, col_calc2 = st.columns(2)
        with col_calc1:
            qqqm_monthly = st.number_input("每月投入 QQQM (USD)：", value=40, step=10)
            qqqm_rate = st.number_input("QQQM 預估年化報酬率 (%)：", value=10.0)
        with col_calc2:
            tw_monthly = st.number_input("每月投入 009816 (TWD)：", value=24375, step=1000)
            tw_rate = st.number_input("009816 預估年化報酬率 (%)：", value=8.0)

        months = invest_years * 12
        qqqm_m_rate = (qqqm_rate / 100) / 12
        qqqm_fv = (qqqm_shares * live_qqqm * ((1 + qqqm_m_rate) ** months)) + (qqqm_monthly * (((1 + qqqm_m_rate) ** months - 1) / qqqm_m_rate) if qqqm_m_rate > 0 else qqqm_monthly * months)
        
        tw_m_rate = (tw_rate / 100) / 12
        tw_fv = (tw_shares * live_tw * ((1 + tw_m_rate) ** months)) + (tw_monthly * (((1 + tw_m_rate) ** months - 1) / tw_m_rate) if tw_m_rate > 0 else tw_monthly * months)

        total_future_twd = (qqqm_fv * exchange_rate) + tw_fv
        st.error(f"🎉 **{invest_years} 年後總資產預估達：NT$ {total_future_twd:,.0f}**")

# 【分頁 7】產業新聞與 AI 總結
with tab7:
    st.subheader("📰 產業新聞與 AI 總結")
    search_query = st.text_input("🔍 查詢產業或公司：", "例如：009816 凱基台灣 表現")
    if st.button("取得最新消息與 AI 總結"):
        with st.spinner("抓取新聞中..."):
            news_data = get_google_news(search_query)
            if news_data:
                news_text = ""
                for idx, news in enumerate(news_data):
                    st.markdown(f"**{idx + 1}. [{news['title']}]({news['link']})**")
                    news_text += f"- {news['title']}\n"
                if api_key:
                    with st.spinner("🤖 AI 正在提煉重點..."):
                        genai.configure(api_key=api_key)
                        res = genai.GenerativeModel('gemini-2.5-flash').generate_content(f"請總結 3 個產業重點：\n\n{news_text}")
                        st.info("### 🤖 AI 重點總結")
                        st.write(res.text)
            else: st.error("❌ 抓取失敗。")