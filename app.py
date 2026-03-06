import streamlit as st
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import google.generativeai as genai
import threading 
from youtube_transcript_api import YouTubeTranscriptApi
import pandas as pd
import email.utils
from datetime import timezone, timedelta

# --- 1. 新聞抓取模組 (包含時間解析) ---
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
            
            pub_date_str = "未知日期"
            pub_date_tag = item.find('pubDate')
            if pub_date_tag is not None:
                try:
                    parsed_date = email.utils.parsedate_to_datetime(pub_date_tag.text)
                    tw_tz = timezone(timedelta(hours=8))
                    tw_time = parsed_date.astimezone(tw_tz)
                    pub_date_str = tw_time.strftime("%Y-%m-%d %H:%M")
                except:
                    pub_date_str = pub_date_tag.text

            news_list.append({'title': title, 'link': link, 'date': pub_date_str})
            if len(news_list) >= 10: break
        return news_list
    except: return None

# --- Yahoo 抓取神技 ---
def fetch_yahoo_single(sym, result_dict):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        valid = [p for p in closes if p is not None]
        if len(valid) >= 2:
            price = valid[-1]
            prev = valid[-2]
            change_amt = price - prev
            change_pct = (change_amt / prev) * 100
            result_dict[sym] = {'price': price, 'change_amt': change_amt, 'change_pct': change_pct}
        elif len(valid) == 1:
            result_dict[sym] = {'price': valid[0], 'change_amt': 0.0, 'change_pct': 0.0}
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

# --- 3. 建立 7 大分頁 (全新加入 個股深度健檢) ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "💼 個人資產總覽", "🏢 個股深度健檢", "📖 SA 助理", "📰 產業新聞", "🎧 KOL 提煉", "🪙 全市場儀表板", "⭐ 投資與試算"
])

# 【分頁 1】💼 個人資產動態管理中心 (保留存檔讀檔系統)
with tab1:
    st.subheader("💼 個人資產動態管理中心")
    
    if 'us_df_v2' not in st.session_state:
        st.session_state.us_df_v2 = pd.DataFrame({
            '標的名稱': ['NVIDIA', 'Tesla', 'Alphabet', 'Kratos Defense', 'Circle', 'Cloudflare', 'Energy Fuels', 'Planet Labs', 'AST SpaceMobile', 'Rezolve AI', 'Palantir', 'Constellation', 'Invesco QQQM', 'Iris Energy', 'Circle'],
            '標的代號': ['NVDA', 'TSLA', 'GOOGL', 'KTOS', 'CRCL', 'NET', 'UUUU', 'PL', 'ASTS', 'RZLV', 'PLTR', 'CEG', 'QQQM', 'IREN', 'CRCL'],
            '持有股數': [35.0, 27.0, 14.0, 15.0, 123.0, 17.6, 60.0, 15.0, 5.0, 100.0, 5.0, 5.0, 2.48, 43.0, 14.0],
            '平均成本': [114.50, 298.91, 215.18, 90.52, 98.84, 186.07, 16.77, 25.42, 92.04, 5.60, 141.83, 315.02, 251.41, 53.57, 112.94]
        })
    if 'tw_df_v2' not in st.session_state:
        st.session_state.tw_df_v2 = pd.DataFrame({
            '標的名稱': ['凱基台灣TOP50', '旺宏', '新光美國電力', '牧德', '群聯', '新光美國電力', '台積電', '佳能', '聯發科', '創威', '凱基台灣TOP50', '鈊象', '佐茂', '勤誠'],
            '標的代號': ['009816.TW', '2337.TW', '009805.TW', '3563.TW', '8299.TWO', '009805.TW', '2330.TW', '2374.TW', '2454.TW', '6530.TWO', '009816.TW', '3293.TWO', '7854.TWO', '8210.TW'],
            '持有股數': [1087.0, 170.0, 2194.0, 22.0, 13.0, 3134.0, 450.0, 472.0, 34.0, 250.0, 3250.0, 164.0, 630.0, 60.0],
            '平均成本': [10.31, 30.00, 13.77, 594.63, 1880.53, 13.50, 529.81, 89.35, 1331.29, 80.31, 10.31, 801.78, 73.74, 966.86]
        })
    if 'crypto_df_v2' not in st.session_state:
        st.session_state.crypto_df_v2 = pd.DataFrame({
            '標的名稱': ['比特幣'],
            '標的代號': ['BTC_USDT'],
            '持有股數': [0.0616],
            '平均成本': [94780.0]
        })
    
    with st.expander("💾 存檔與讀檔 (防網頁重置備份區)", expanded=False):
        col_save, col_load = st.columns(2)
        with col_save:
            us_dl = st.session_state.us_df_v2.copy(); us_dl['市場分類'] = '美股'
            tw_dl = st.session_state.tw_df_v2.copy(); tw_dl['市場分類'] = '台股'
            cr_dl = st.session_state.crypto_df_v2.copy(); cr_dl['市場分類'] = '加密貨幣'
            master_dl = pd.concat([us_dl, tw_dl, cr_dl], ignore_index=True)
            csv_data = master_dl.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="⬇️ 下載最新資產存檔 (CSV)", data=csv_data, file_name="my_portfolio_save.csv", mime="text/csv", use_container_width=True)
            
        with col_load:
            uploaded_file = st.file_uploader("📂 上傳資產存檔以覆蓋還原：", type="csv", label_visibility="collapsed")
            if uploaded_file is not None:
                if st.button("確認讀取並還原資料", use_container_width=True):
                    loaded_df = pd.read_csv(uploaded_file)
                    st.session_state.us_df_v2 = loaded_df[loaded_df['市場分類'] == '美股'].drop(columns=['市場分類']).reset_index(drop=True)
                    st.session_state.tw_df_v2 = loaded_df[loaded_df['市場分類'] == '台股'].drop(columns=['市場分類']).reset_index(drop=True)
                    st.session_state.crypto_df_v2 = loaded_df[loaded_df['市場分類'] == '加密貨幣'].drop(columns=['市場分類']).reset_index(drop=True)
                    st.rerun()

    with st.expander("✏️ 點此展開修改持股資料 (修改後記得去上方存檔喔)", expanded=False):
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.markdown("#### 🇺🇸 美股資產")
            us_edited = st.data_editor(st.session_state.us_df_v2, num_rows="dynamic", use_container_width=True)
            st.session_state.us_df_v2 = us_edited
        with col_t2:
            st.markdown("#### 🇹🇼 台股資產")
            tw_edited = st.data_editor(st.session_state.tw_df_v2, num_rows="dynamic", use_container_width=True)
            st.session_state.tw_df_v2 = tw_edited
        with col_t3:
            st.markdown("#### 🪙 加密貨幣")
            crypto_edited = st.data_editor(st.session_state.crypto_df_v2, num_rows="dynamic", use_container_width=True)
            st.session_state.crypto_df_v2 = crypto_edited

    st.markdown("---")
    
    live_usd_twd = 32.50 
    try:
        usd_res = {}
        fetch_yahoo_single("USDTWD=X", usd_res)
        if "USDTWD=X" in usd_res and usd_res["USDTWD=X"]['price'] > 0:
            live_usd_twd = usd_res["USDTWD=X"]['price']
    except: pass
    
    col_rate, col_btn, col_empty = st.columns([1, 1, 2])
    with col_rate:
        usd_to_twd = st.number_input("💵 目前美金兌台幣即時匯率：", value=float(live_usd_twd), step=0.1)
    with col_btn:
        st.write("")
        st.write("")
        calculate_btn = st.button("🔄 產生專業持股報表", type="primary", use_container_width=True)

    if calculate_btn:
        with st.spinner("🌍 正在全網抓取最新報價，生成分析報表中..."):
            us_copy = us_edited.copy(); us_copy['市場分類'] = '美股'
            tw_copy = tw_edited.copy(); tw_copy['市場分類'] = '台股'
            crypto_copy = crypto_edited.copy(); crypto_copy['市場分類'] = '加密貨幣'
            edited_df = pd.concat([us_copy, tw_copy, crypto_copy], ignore_index=True)
            
            yahoo_symbols = edited_df[edited_df['市場分類'].isin(['美股', '台股'])]['標的代號'].tolist()
            yahoo_prices = get_yahoo_bulk_threaded(yahoo_symbols)
            
            pionex_prices = {}
            try:
                res = requests.get("https://api.pionex.com/api/v1/market/tickers", timeout=8)
                for t in res.json().get('data', {}).get('tickers', []):
                    close_px = float(t['close'])
                    chg_pct = float(t['change24h'])
                    prev_px = close_px / (1 + chg_pct) if (1 + chg_pct) != 0 else close_px
                    pionex_prices[t['symbol']] = {'price': close_px, 'change_amt': close_px - prev_px, 'change_pct': chg_pct * 100}
            except: pass

            portfolio_data = []
            total_invested_twd = 0.0
            total_value_twd = 0.0
            total_today_gain_twd = 0.0
            
            for index, row in edited_df.iterrows():
                market = row['市場分類']
                sym = row['標的代號']
                name = row['標的名稱'] if '標的名稱' in row and pd.notna(row['標的名稱']) else ""
                shares = float(row['持有股數']) if pd.notna(row['持有股數']) else 0.0
                cost = float(row['平均成本']) if pd.notna(row['平均成本']) else 0.0
                
                if not sym or shares == 0: continue
                
                market_data = pionex_prices.get(sym, {'price':0, 'change_amt':0, 'change_pct':0}) if market == '加密貨幣' else yahoo_prices.get(sym, {'price':0, 'change_amt':0, 'change_pct':0})
                
                live_price = market_data['price']
                change_amt = market_data['change_amt']
                change_pct = market_data['change_pct']
                
                if live_price == 0.0 and cost > 0:
                    live_price = cost
                    change_amt = 0.0
                    change_pct = 0.0
                
                invested = shares * cost
                current_val = shares * live_price
                today_gain = shares * change_amt
                total_gain = current_val - invested
                total_gain_pct = (total_gain / invested * 100) if invested > 0 else 0.0
                multiplier = usd_to_twd if market in ['美股', '加密貨幣'] else 1.0
                
                total_invested_twd += (invested * multiplier)
                total_value_twd += (current_val * multiplier)
                total_today_gain_twd += (today_gain * multiplier)
                
                portfolio_data.append({
                    "Market": market, "Name": name, "Symbol": sym, "Price": live_price,
                    "Change": change_amt, "Change %": change_pct, "Shares": shares, "Cost": cost,
                    "Today's Gain": today_gain, "Today's % Gain": change_pct, 
                    "Total Change": total_gain, "Total % Change": total_gain_pct,
                    "Value": current_val, "_multiplier": multiplier 
                })

            if portfolio_data:
                total_change_twd = total_value_twd - total_invested_twd
                total_change_pct = (total_change_twd / total_invested_twd * 100) if total_invested_twd > 0 else 0.0
                
                st.markdown(f"### 👁 NT$ {total_value_twd:,.0f} &nbsp;&nbsp; <span style='color:{'#00d26a' if total_change_twd >= 0 else '#f6465d'}; font-size:24px;'>{'↗' if total_change_twd >= 0 else '↘'} {total_change_twd:+,.0f} ({total_change_pct:+.2f}%) 總未實現</span>", unsafe_allow_html=True)
                
                display_list = []
                for item in portfolio_data:
                    w = ((item['Value'] * item['_multiplier']) / total_value_twd * 100) if total_value_twd > 0 else 0.0
                    currency_unit = " USD" if item['Market'] in ['美股', '加密貨幣'] else " TWD"
                    display_list.append({
                        "市場": item['Market'], "名稱": item['Name'], "Symbol": item['Symbol'],
                        "Price": f"{item['Price']:,.2f}", "Change": f"{item['Change']:+.2f}", "Change %": f"{item['Change %']:+.2f}%",
                        "Weight": f"{w:.1f}%", "Shares": f"{item['Shares']:,.4f}", "Cost": f"{item['Cost']:,.2f}",
                        "Today's Gain": f"{item['Today\'s Gain']:+.2f}", "Today's % Gain": f"{item['Today\'s % Gain']:+.2f}%",
                        "Total Change": f"{item['Total Change']:+.2f}", "Total % Change": f"{item['Total % Change']:+.2f}%",
                        "Value": f"{item['Value']:,.2f}{currency_unit}"
                    })
                df_display = pd.DataFrame(display_list)
                
                def color_positive_negative(val):
                    if isinstance(val, str):
                        if val.startswith('+'): return 'color: #00d26a; font-weight: bold;'
                        if val.startswith('-'): return 'color: #f6465d; font-weight: bold;'
                    return ''
                
                styled_df = df_display.style.map(color_positive_negative, subset=["Change", "Change %", "Today's Gain", "Today's % Gain", "Total Change", "Total % Change"])
                st.dataframe(styled_df, use_container_width=True, hide_index=True)

# 【分頁 2】🌟 全新：個股深度健檢與產業鏈分析 🌟
with tab2:
    st.subheader("🏢 個股深度健檢與產業鏈分析")
    st.markdown("輸入公司名稱或代號，AI 將自動抓取最新新聞，並為您一鍵生成法規級的深度基本面報告！")
    
    col_c1, col_c2 = st.columns([3, 1])
    with col_c1:
        target_stock = st.text_input("🔍 請輸入想健檢的股票代號或公司名稱：", "例如：NVDA 或 台積電")
    with col_c2:
        st.write("")
        st.write("")
        analyze_btn = st.button("🚀 生成深度健檢報告", type="primary", use_container_width=True)

    if analyze_btn:
        if not api_key:
            st.warning("⚠️ 請先在左側輸入 API Key！")
        elif not target_stock or target_stock == "例如：NVDA 或 台積電":
            st.warning("⚠️ 請輸入有效的公司名稱！")
        else:
            # 1. 先去 Google 抓取近幾天的最新財報與政策新聞 (RAG 檢索增強)
            with st.spinner(f"📡 正在為您搜集全網關於 {target_stock} 的最新財報與政策情報..."):
                stock_news = get_google_news(f"{target_stock} 財報 OR 政策 OR 供應鏈")
                news_context = ""
                if stock_news:
                    for n in stock_news[:6]: # 取前6條最相關的
                        news_context += f"- {n['title']} (時間: {n['date']})\n"
                else:
                    news_context = "無近期重大新聞"

            # 2. 呼叫 Gemini 進行結構化深度分析
            with st.spinner("🤖 華爾街 AI 首席分析師正在彙整數據並撰寫報告，請稍候..."):
                try:
                    genai.configure(api_key=api_key)
                    prompt = f"""
                    你現在是一位頂尖的華爾街與台股資深分析師。請針對「{target_stock}」這家公司，提供一份結構化的深度健檢報告。
                    
                    【最新市場情報參考】(這是剛剛為您抓取的最新新聞，請將其融入分析中)：
                    {news_context}

                    請使用專業的「繁體中文」，並嚴格按照以下 5 大區塊進行條列式深度分析：
                    
                    1. 🏭 【公司業務與核心護城河】：他們主要靠什麼賺錢？營收佔比最高的是什麼？最大的競爭優勢(護城河)在哪？
                    2. 🔗 【上下游產業鏈與主力客戶】：他們上游原物料/設備跟哪家公司拿貨？下游主力客戶有哪些大廠？(請具體列出關聯公司名稱)
                    3. 📊 【近期財報表現分析】：根據最新數據或市場預期，近一季營收與毛利率表現如何？盈餘是否有超乎預期？
                    4. 📈 【估值位階 (PE/PEG 分析)】：評估其目前的歷史本益比(PE)河流圖位階是偏高、合理還是偏低？若考慮其成長性，PEG (本益成長比) 表現如何？
                    5. 📢 【政策影響與最新催化劑】：近期是否有國內外政府政策(如關稅、補貼、禁令)影響該公司？未來一季有什麼即將發生的重要事件或催化劑？
                    """
                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
                    
                    st.success(f"✅ {target_stock} 深度報告生成完畢！")
                    
                    # 使用 expander 顯示 AI 看的新聞參考來源
                    with st.expander("📰 點此查看 AI 參考的即時新聞來源"):
                        st.markdown(news_context)
                        
                    st.divider()
                    st.markdown(res.text)
                    
                except Exception as e:
                    st.error(f"❌ 報告生成失敗：{e}")

# 【分頁 3】Seeking Alpha AI 專業助理
with tab3:
    st.subheader("📖 Seeking Alpha AI 專業閱讀助理")
    
    if "sa_text_input" not in st.session_state:
        st.session_state.sa_text_input = ""
        
    def clear_sa_text():
        st.session_state.sa_text_input = ""

    col_sa1, col_sa2 = st.columns([2, 1])
    with col_sa2:
        st.info("💡 **優化指南**\n\n1. 複製 SA 文章全文\n2. 選擇分析側重點\n3. 點擊生成報告")
        focus_area = st.selectbox("🎯 選擇分析側重點：", ["全面平衡分析 (預設)", "偏重看多與護城河分析", "偏重看空與財報風險預警"])
        st.write("")
        st.button("🗑️ 一鍵清空文章", on_click=clear_sa_text, use_container_width=True)
        
    with col_sa1:
        sa_article = st.text_area("📝 請在此貼上 Seeking Alpha 文章內容：", height=250, key="sa_text_input")
    
    if st.button("🚀 AI 深度解析 SA 文章", use_container_width=True):
        if not api_key: st.warning("⚠️ 請先在左側輸入 API Key！")
        elif not sa_article.strip(): st.warning("⚠️ 請貼上文章內容！")
        else:
            with st.spinner("🤖 華爾街 AI 助教正在深度解析文章，請稍候..."):
                try:
                    genai.configure(api_key=api_key)
                    focus_prompt = ""
                    if focus_area == "偏重看多與護城河分析": focus_prompt = "請深度挖掘看好該公司的理由、競爭優勢。"
                    elif focus_area == "偏重看空與財報風險預警": focus_prompt = "請深度挖掘潛在風險、財報隱憂或劣勢。"
                    else: focus_prompt = "請客觀平衡地呈現文章的多空觀點。"

                    sa_prompt = f"""請以「繁體中文」輸出以下結構化的重點整理：\n{focus_prompt}\n1. 🎯 【核心觀點】\n2. 🐂 【看多論點與護城河】\n3. 🐻 【看空論點與風險】\n4. 💡 【關鍵數據與催化劑】\n文章內容如下：\n{sa_article}"""
                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(sa_prompt)
                    st.success(f"✅ 解析完成！(模式：{focus_area})")
                    st.write(res.text)
                except Exception as e: st.error(f"❌ AI 解析失敗：{e}")

# 【分頁 4】產業新聞與 AI 總結
with tab4:
    st.subheader("📰 產業新聞與 AI 總結")
    search_query = st.text_input("🔍 查詢產業或公司：", "例如：特斯拉 最新財報與表現")
    if st.button("取得最新消息與 AI 總結"):
        with st.spinner("抓取新聞中..."):
            news_data = get_google_news(search_query)
            if news_data:
                news_text = ""
                for idx, news in enumerate(news_data):
                    st.markdown(f"**{idx + 1}. [{news['title']}]({news['link']})** ⏱️ `{news['date']}`")
                    news_text += f"- {news['title']}\n"
                if api_key:
                    with st.spinner("🤖 AI 正在提煉重點..."):
                        genai.configure(api_key=api_key)
                        res = genai.GenerativeModel('gemini-2.5-flash').generate_content(f"請總結 3 個產業重點：\n\n{news_text}")
                        st.info("### 🤖 AI 重點總結")
                        st.write(res.text)
            else: st.error("❌ 抓取失敗。")

# 【分頁 5】財經 KOL 影音/貼文提煉引擎
with tab5:
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
                    with st.spinner("🕵️‍♂️ 正在掃描可用字幕..."):
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

# 【分頁 6】全市場即時儀表板
with tab6:
    st.subheader("🪙 全市場即時儀表板 (Crypto & 美股)")
    pionex_tokens = {"Bitcoin (BTC)": "BTC_USDT", "Ethereum (ETH)": "ETH_USDT", "Cardano (ADA)": "ADA_USDT"}
    yahoo_groups = {
        "💻 科技與半導體 (Tech)": {"輝達 (NVDA)": "NVDA", "特斯拉 (TSLA)": "TSLA", "蘋果 (AAPL)": "AAPL", "微軟 (MSFT)": "MSFT", "美光 (MU)": "MU", "超微 (AMD)": "AMD", "台積電 (TSM)": "TSM"},
        "⚔️ 戰爭避險與能源 (Energy & Defense)": {"布蘭特原油 (BZ=F)": "BZ=F", "WTI原油 (CL=F)": "CL=F", "黃金期貨 (GC=F)": "GC=F", "白銀期貨 (SI=F)": "SI=F", "天然氣 (NG=F)": "NG=F", "洛克希德馬丁 (LMT)": "LMT"},
        "🚢 全球航運與散裝 (Shipping)": {"散裝BDI指數ETF (BDRY)": "BDRY", "星散海運 (SBLK)": "SBLK", "以星貨櫃 (ZIM)": "ZIM", "油輪運輸 (NAT)": "NAT"},
        "📈 總經指數與 ETF (Index)": {"納斯達克 (QQQ)": "QQQ", "標普500 (SPY)": "SPY", "半導體 (SOXX)": "SOXX"}
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
                        cols[idx % 4].metric(label, fmt_price, f"{stock['change_pct']:.2f}%")
    auto_refresh_dual_engine()

# 【分頁 7】投資計畫與超級複利試算機
with tab7:
    st.subheader("⭐ 長期投資計畫與超級複利試算機")
    
    live_usd_twd_calc = 32.50
    try:
        usd_res_calc = {}
        fetch_yahoo_single("USDTWD=X", usd_res_calc)
        if "USDTWD=X" in usd_res_calc and usd_res_calc["USDTWD=X"]['price'] > 0:
            live_usd_twd_calc = usd_res_calc["USDTWD=X"]['price']
    except: pass

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
            qqqm_shares = st.number_input("持有 QQQM 股數 (試算用)：", value=0.0, step=0.1)
        with col_inv2:
            tw_shares = st.number_input("持有 009816 股數 (試算用)：", value=0.0, step=1.0)
        
        exchange_rate = st.number_input("美金匯率 (自動更新)：", value=float(live_usd_twd_calc))
        
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