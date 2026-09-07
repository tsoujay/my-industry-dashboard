import streamlit as st
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import google.generativeai as genai
import threading 
import pandas as pd
import email.utils
from datetime import timezone, timedelta
import datetime

# --- 🌟 1. 系統安全與密碼設定 🌟 ---
APP_PASSWORD = "tsou888" 

st.set_page_config(page_title="TSOU財經資訊中心", page_icon="📈", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🔐 TSOU 私人財富與知識管理中心</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>系統已啟動安全防護，請輸入專屬授權密碼以進入系統。</p>", unsafe_allow_html=True)
    
    col_pwd1, col_pwd2, col_pwd3 = st.columns([1, 2, 1])
    with col_pwd2:
        with st.container(border=True):
            pwd_input = st.text_input("🔑 輸入存取密碼：", type="password")
            if st.button("🚀 解鎖登入系統", use_container_width=True, type="primary"):
                if pwd_input == APP_PASSWORD:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("❌ 密碼錯誤，存取被拒絕！")
    st.stop()

# ==========================================
# 👇 登入成功後執行的主系統程式碼 👇
# ==========================================

current_year = datetime.datetime.now().year 

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

def get_twse_institutional_data():
    url = "https://openapi.twse.com.tw/v1/fund/BFI82U"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200: return res.json()
    except: pass
    return None

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

st.title("📈 TSOU財經資訊中心")

st.sidebar.header("⚙️ 系統設定")
api_key = st.sidebar.text_input("輸入 Gemini API Key (啟動 AI):", type="password").strip()

st.sidebar.markdown("---")
if st.sidebar.button("🚪 登出系統", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()

# 🗑️ 精簡版分頁設定
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💼 個人資產總覽",     
    "🪙 籌碼與大盤儀表板", 
    "🏢 個股深度健檢",     
    "📖 SA 助理",         
    "📰 產業新聞",         
    "⭐ 投資與試算"       
])

# 【分頁 1】💼 個人資產動態管理中心
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
    if 'history_df_v1' not in st.session_state:
        st.session_state.history_df_v1 = pd.DataFrame({
            '日期': [datetime.datetime.now().strftime("%Y-%m-%d")],
            '總資產 (TWD)': [0.0],
            '總未實現損益 (TWD)': [0.0]
        })

    with st.expander("✏️ 點此展開修改持股資料 (編輯完可於下方存檔)", expanded=False):
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.markdown("#### 🇺🇸 美股資產")
            us_edited = st.data_editor(st.session_state.us_df_v2, num_rows="dynamic", use_container_width=True, key="us_editor")
        with col_t2:
            st.markdown("#### 🇹🇼 台股資產")
            tw_edited = st.data_editor(st.session_state.tw_df_v2, num_rows="dynamic", use_container_width=True, key="tw_editor")
        with col_t3:
            st.markdown("#### 🪙 加密貨幣")
            crypto_edited = st.data_editor(st.session_state.crypto_df_v2, num_rows="dynamic", use_container_width=True, key="crypto_editor")

    with st.expander("💾 持股存檔與讀檔 (防網頁重置備份區)", expanded=False):
        col_save, col_load = st.columns(2)
        with col_save:
            us_dl = us_edited.copy(); us_dl['市場分類'] = '美股'
            tw_dl = tw_edited.copy(); tw_dl['市場分類'] = '台股'
            cr_dl = crypto_edited.copy(); cr_dl['市場分類'] = '加密貨幣'
            master_dl = pd.concat([us_dl, tw_dl, cr_dl], ignore_index=True)
            csv_data = master_dl.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="⬇️ 下載最新持股存檔 (CSV)", data=csv_data, file_name="my_portfolio_save.csv", mime="text/csv", use_container_width=True)
        with col_load:
            uploaded_file = st.file_uploader("📂 上傳持股存檔以覆蓋還原：", type="csv", label_visibility="collapsed")
            if uploaded_file is not None:
                if st.button("確認讀取並還原資料", use_container_width=True):
                    loaded_df = pd.read_csv(uploaded_file)
                    st.session_state.us_df_v2 = loaded_df[loaded_df['市場分類'] == '美股'].drop(columns=['市場分類']).reset_index(drop=True)
                    st.session_state.tw_df_v2 = loaded_df[loaded_df['市場分類'] == '台股'].drop(columns=['市場分類']).reset_index(drop=True)
                    st.session_state.crypto_df_v2 = loaded_df[loaded_df['市場分類'] == '加密貨幣'].drop(columns=['市場分類']).reset_index(drop=True)
                    for k in ['us_editor', 'tw_editor', 'crypto_editor']:
                        if k in st.session_state: del st.session_state[k]
                    st.rerun()

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
            
            yahoo_symbols = []
            yahoo_crypto_map = {}
            for idx, row in edited_df.iterrows():
                sym = row['標的代號']
                if row['市場分類'] == '加密貨幣':
                    y_sym = sym.replace('_USDT', '-USD').replace('USDT', '-USD')
                    yahoo_crypto_map[sym] = y_sym
                    yahoo_symbols.append(y_sym)
                else:
                    yahoo_symbols.append(sym)
            
            yahoo_prices = get_yahoo_bulk_threaded(list(set(yahoo_symbols)))

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
                
                if market == '加密貨幣':
                    y_sym = yahoo_crypto_map.get(sym, sym)
                    market_data = yahoo_prices.get(y_sym, {'price':0, 'change_amt':0, 'change_pct':0})
                else:
                    market_data = yahoo_prices.get(sym, {'price':0, 'change_amt':0, 'change_pct':0})
                
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
                
                st.session_state.current_total_value = total_value_twd
                st.session_state.current_total_change = total_change_twd
                
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

    st.markdown("---")
    st.markdown("### 📈 每日資 अलं動追蹤")
    st.caption("請先點擊上方的「🔄 產生專業持股報表」後，再點擊下方按鈕將今日數據儲存到您的歷史曲線中。")
    
    col_snap, col_empty = st.columns([1, 2])
    with col_snap:
        if st.button("📸 紀錄今日總資產與損益", type="primary", use_container_width=True):
            if 'current_total_value' in st.session_state and 'current_total_change' in st.session_state:
                today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                val = round(st.session_state.current_total_value, 2)
                chg = round(st.session_state.current_total_change, 2)
                
                idx = st.session_state.history_df_v1.index[st.session_state.history_df_v1['日期'] == today_str].tolist()
                if idx:
                    st.session_state.history_df_v1.loc[idx[0], '總資產 (TWD)'] = val
                    st.session_state.history_df_v1.loc[idx[0], '總未實現損益 (TWD)'] = chg
                else:
                    if len(st.session_state.history_df_v1) == 1 and st.session_state.history_df_v1.iloc[0]['總資產 (TWD)'] == 0.0:
                        st.session_state.history_df_v1 = pd.DataFrame({'日期': [today_str], '總資產 (TWD)': [val], '總未實現損益 (TWD)': [chg]})
                    else:
                        new_row = pd.DataFrame({'日期': [today_str], '總資產 (TWD)': [val], '總未實現損益 (TWD)': [chg]})
                        st.session_state.history_df_v1 = pd.concat([st.session_state.history_df_v1, new_row], ignore_index=True)
                st.success("✅ 已成功紀錄今日資產！")
            else:
                st.warning("⚠️ 請先點擊上方的「產生專業持股報表」產生最新數據！")

    if not st.session_state.history_df_v1.empty and len(st.session_state.history_df_v1) > 0 and st.session_state.history_df_v1.iloc[0]['總資產 (TWD)'] > 0:
        tab_chart1, tab_chart2 = st.tabs(["💰 總未實現損益曲線", "🏦 總資產規模曲線"])
        plot_df = st.session_state.history_df_v1.set_index('日期')
        with tab_chart1: st.line_chart(plot_df['總未實現損益 (TWD)'], color="#00d26a")
        with tab_chart2: st.line_chart(plot_df['總資產 (TWD)'], color="#4a90e2")

    with st.expander("💾 管理歷史波動紀錄 (備份與還原)", expanded=False):
        edited_hist = st.data_editor(st.session_state.history_df_v1, num_rows="dynamic", use_container_width=True, key="hist_editor")
        if st.button("✅ 儲存歷史表修改", type="secondary"):
            st.session_state.history_df_v1 = edited_hist.copy()
            del st.session_state['hist_editor']
            st.success("✅ 儲存成功！圖表已更新。")
            st.rerun()

        col_hsave, col_hload = st.columns(2)
        with col_hsave:
            csv_hist = edited_hist.to_csv(index=False).encode('utf-8-sig')
            st.download_button("⬇️ 下載歷史紀錄存檔", csv_hist, "my_portfolio_history.csv", "text/csv", use_container_width=True)
        with col_hload:
            uploaded_hist = st.file_uploader("📂 上傳歷史紀錄還原：", type="csv", label_visibility="collapsed")
            if uploaded_hist is not None:
                if st.button("確認還原歷史", use_container_width=True):
                    st.session_state.history_df_v1 = pd.read_csv(uploaded_hist)
                    if 'hist_editor' in st.session_state: del st.session_state['hist_editor']
                    st.rerun()

# 【分頁 2】🪙 籌碼與大盤儀表板 (🌟 已將美債/日債拆分為獨立區塊)
with tab2:
    st.subheader("🪙 全市場即時大盤與台股籌碼戰報")
    st.markdown("### 🇹🇼 今日台股籌碼戰報 (三大法人/期貨/融資)")
    st.caption("透過 AI 閱讀全網最新財經新聞，一鍵萃取今日所有籌碼數據！(建議下午 3:30 以後使用)")
    
    if st.button("🔄 啟動 AI 戰情室：一鍵生成今日籌碼總結", type="primary"):
        if not api_key: st.warning("⚠️ 請先輸入 API Key！")
        else:
            with st.spinner("📡 正在全網抓取今日下午最新公布的法人與融資數據..."):
                news_1 = get_google_news("台股 三大法人 買賣超 最新")
                news_2 = get_google_news("台股 外資 期貨 未平倉 融資 最新")
                all_news = []
                if news_1: all_news.extend(news_1)
                if news_2: all_news.extend(news_2)
                
                chips_context = ""
                if all_news:
                    seen = set()
                    for n in all_news:
                        if n['title'] not in seen:
                            seen.add(n['title'])
                            chips_context += f"- {n['title']} (發布時間: {n['date']})\n"
                
                with st.spinner("🤖 AI 正在繪製法人買賣超表格與籌碼解析..."):
                    try:
                        genai.configure(api_key=api_key)
                        chips_prompt = f"""你現在是一位專精台股籌碼面的分析師。以下是今日最新新聞標題：\n{chips_context}\n請幫我精準萃取出數據，並嚴格按照以下格式輸出（包含 Markdown 表格）：\n### 📊 一、三大法人買賣超金額 (單位：億元)\n(略...請自行畫出外資、投信、自營商表格)\n### 🐻 二、外資期權動向\n### 💰 三、大盤融資狀況\n### 💡 四、盤勢綜合判定"""
                        res = genai.GenerativeModel('gemini-2.5-flash').generate_content(chips_prompt)
                        st.success("✅ 今日籌碼解析完成！")
                        st.markdown(res.text)
                        with st.expander("📰 點此查看 AI 參考的新聞原始資料"): st.markdown(chips_context)
                    except Exception as e: st.error(f"❌ 解析失敗：{e}")

    st.markdown("---")
    pionex_tokens = {"Bitcoin (BTC)": "BTC_USDT", "Ethereum (ETH)": "ETH_USDT", "Cardano (ADA)": "ADA_USDT"}
    
    # 🌟 拆分美債與日債群組
    yahoo_groups = {
        "💻 科技與半導體 (Tech)": {"輝達 (NVDA)": "NVDA", "特斯拉 (TSLA)": "TSLA", "蘋果 (AAPL)": "AAPL", "微軟 (MSFT)": "MSFT", "台積電 (TSM)": "TSM"},
        "🦅 美國公債殖利率 (US Yields)": {"美債10年期 (^TNX)": "^TNX", "美債20年期 (^TYX)": "^TYX", "美債5年期 (^FVX)": "^FVX", "美債13週 (^IRX)": "^IRX"},
        "🌸 日本公債殖利率 (JP Yields)": {"日債10年期 (JP10Y.B)": "JP10Y.B", "日債2年期 (JP2Y.B)": "JP2Y.B"},
        "⚔️ 戰爭避險與能源 (Energy & Defense)": {"布蘭特原油 (BZ=F)": "BZ=F", "黃金期貨 (GC=F)": "GC=F", "天然氣 (NG=F)": "NG=F", "洛克希德馬丁 (LMT)": "LMT"},
        "📈 總經指數與 ETF (Index)": {"納斯達克 (QQQ)": "QQQ", "標普500 (SPY)": "SPY", "半導體 (SOXX)": "SOXX"}
    }
    
    @st.fragment(run_every="30s")
    def auto_refresh_dual_engine():
        pionex_data = {}
        try:
            res = requests.get("https://api.pionex.com/api/v1/market/tickers", timeout=5)
            for t in res.json().get('data', {}).get('tickers', []): pionex_data[t['symbol']] = t
        except: pass
        
        yahoo_fallback_symbols = ["BTC-USD", "ETH-USD", "ADA-USD"]
        all_yahoo = [sym for group in yahoo_groups.values() for sym in group.values()] + yahoo_fallback_symbols
        yahoo_data = get_yahoo_bulk_threaded(all_yahoo)
        
        with st.expander("🌟 主流加密貨幣", expanded=True):
            cols = st.columns(3)
            for idx, (label, symbol) in enumerate(pionex_tokens.items()):
                crypto = pionex_data.get(symbol)
                if crypto and float(crypto.get('close', 0)) > 0:
                    cols[idx % 3].metric(label, f"${float(crypto.get('close', 0)):,.2f}", f"{float(crypto.get('change24h', 0))*100:.2f}%")
                else:
                    y_sym = symbol.replace('_USDT', '-USD')
                    y_data = yahoo_data.get(y_sym)
                    if y_data and y_data['price'] > 0:
                        cols[idx % 3].metric(label, f"${y_data['price']:,.2f}", f"{y_data['change_pct']:.2f}%")
                    else:
                        cols[idx % 3].metric(label, "連線中...", "0.00%")
        
        for group_name, tokens in yahoo_groups.items():
            with st.expander(f"{group_name} (來源：Yahoo實時)"):
                cols = st.columns(4)
                for idx, (label, symbol) in enumerate(tokens.items()):
                    stock = yahoo_data.get(symbol)
                    if stock and stock['price'] > 0:
                        # 🌟 自動判斷是否為殖利率(含Yields關鍵字)，移除 $ 符號並改為 %
                        is_yield = "Yields" in group_name
                        prefix = "" if is_yield else "$"
                        suffix = "%" if is_yield else ""
                        fmt_price = f"{prefix}{stock['price']:,.3f}{suffix}" if stock['price'] < 1 else f"{prefix}{stock['price']:,.2f}{suffix}"
                        
                        cols[idx % 4].metric(label, fmt_price, f"{stock['change_pct']:.2f}%")
    auto_refresh_dual_engine()

# 【分頁 3】🏢 企業深度分析與雙股對決
with tab3:
    st.subheader("🏢 企業深度分析與雙股對決")
    analysis_mode = st.radio("請選擇分析模式：", ["🔍 單一個股深度健檢", "⚔️ 雙股競爭對決分析"], horizontal=True)
    
    if "單一" in analysis_mode:
        st.markdown("輸入公司名稱，AI 將抓取**最新情報**，為您生成法規級的深度基本面報告！")
        col_c1, col_c2 = st.columns([3, 1])
        with col_c1: target_stock = st.text_input("🔍 請輸入想健檢的股票代號或公司名稱：", "例如：NVDA 或 台積電")
        with col_c2:
            st.write("")
            st.write("")
            analyze_btn = st.button("🚀 生成深度健檢報告", type="primary", use_container_width=True)

        if analyze_btn:
            if not api_key: st.warning("⚠️ 請先輸入 API Key！")
            elif not target_stock or target_stock == "例如：NVDA 或 台積電": st.warning("⚠️ 請輸入有效的公司名稱！")
            else:
                with st.spinner(f"📡 正在全網鎖定 {target_stock} 最新情報..."):
                    news_list_1 = get_google_news(f"{target_stock} 財報 OR earnings OR 法說會")
                    news_list_2 = get_google_news(f"{target_stock} 營收 OR news OR 前景")
                    stock_news = []
                    if news_list_1: stock_news.extend(news_list_1)
                    if news_list_2: stock_news.extend(news_list_2)
                    
                    news_context = ""
                    if stock_news:
                        seen = set()
                        unique_news = []
                        for n in stock_news:
                            if n['title'] not in seen:
                                seen.add(n['title'])
                                unique_news.append(n)
                        for n in unique_news[:8]: news_context += f"- {n['title']} (發布時間: {n['date']})\n"
                    else: news_context = "近期無相關中文重大新聞"

                with st.spinner("🤖 華爾街 AI 首席分析師正在撰寫報告..."):
                    try:
                        genai.configure(api_key=api_key)
                        prompt = f"""你現在是一位頂尖的華爾街與台股資深分析師。請針對「{target_stock}」這家公司提供深度健檢報告。
                        【知識庫救援機制】：若是美股，請調用內建最新知識庫補足季報與估值位階！
                        【最新市場情報參考】：\n{news_context}\n
                        請嚴格按照以下 5 大區塊進行條列式深度分析：
                        1. 🏭 【公司業務與核心護城河】
                        2. 🔗 【上下游產業鏈與主力客戶】
                        3. 📊 【最新季報與營收表現】
                        4. 📈 【估值位階 (PE/PEG 分析)】
                        5. 📢 【政策影響與最新催化劑】"""
                        res = genai.GenerativeModel('gemini-2.5-flash').generate_content(prompt)
                        st.success(f"✅ {target_stock} 深度報告生成完畢！")
                        with st.expander("📰 點此查看 AI 參考的即時新聞來源與時間"): st.markdown(news_context)
                        st.divider()
                        st.markdown(res.text)
                    except Exception as e: st.error(f"❌ 報告生成失敗：{e}")
    else:
        st.markdown("想知道兩家公司誰比較值得投資？輸入名稱讓 AI 幫你做全面的 PK 比較！")
        col_pk1, col_pk_vs, col_pk2 = st.columns([3, 1, 3])
        with col_pk1: stock_a = st.text_input("🔵 選手 A (公司/代號)：", "例如：NVDA")
        with col_pk_vs: st.markdown("<h2 style='text-align: center; color: #ff4b4b;'>VS</h2>", unsafe_allow_html=True)
        with col_pk2: stock_b = st.text_input("🔴 選手 B (公司/代號)：", "例如：AMD")
        
        vs_btn = st.button("⚔️ 啟動雙股對決分析", type="primary", use_container_width=True)
        
        if vs_btn:
            if not api_key: st.warning("⚠️ 請先輸入 API Key！")
            elif not stock_a or not stock_b or stock_a == "例如：NVDA": st.warning("⚠️ 請輸入有效的公司名稱！")
            else:
                with st.spinner(f"📡 正在全網搜集 {stock_a} 與 {stock_b} 的情報並建構擂台..."):
                    news_a = get_google_news(f"{stock_a} 財報 OR 營收 OR 前景")
                    context_a = ""
                    if news_a:
                        for n in news_a[:5]: context_a += f"- {n['title']} ({n['date']})\n"
                    news_b = get_google_news(f"{stock_b} 財報 OR 營收 OR 前景")
                    context_b = ""
                    if news_b:
                        for n in news_b[:5]: context_b += f"- {n['title']} ({n['date']})\n"

                with st.spinner("🤖 AI 裁判正在進行多維度分析與製作比較表格..."):
                    try:
                        genai.configure(api_key=api_key)
                        vs_prompt = f"""
                        你現在是一位頂尖的華爾街與台股資深分析師。請針對「{stock_a}」與「{stock_b}」這兩家公司，進行一場深度的【雙股競爭對決分析】。
                        【知識庫救援機制】：請調用你內建的最強金融知識庫來補足兩家公司的歷史定位與財報表現。
                        【最新情報參考 - {stock_a}】：\n{context_a}
                        【最新情報參考 - {stock_b}】：\n{context_b}
                        請使用專業的「繁體中文」，並嚴格按照以下 5 大區塊進行對比分析：
                        1. ⚔️ 【核心業務與護城河對決】：兩家公司主要業務分別是什麼？誰的競爭優勢(護城河)更深？
                        2. 💰 【最新財報與營收大PK】(請畫出 Markdown 比較表格)：對比兩家近期的成長性、毛利率，並給出勝負判定。
                        3. ⚖️ 【估值位階與市場預期】：對比兩者的本益比(PE)或PEG位階，誰目前看起來更具投資CP值？
                        4. 🔗 【產業鏈位置與潛在威脅】：它們是直接競爭對手、上下游關係、還是互補？客戶重疊度高嗎？
                        5. 🏆 【終極總結與配置建議】：針對「穩健型」與「積極成長型」兩種投資人，你分別會給出什麼樣的買進建議？
                        """
                        res = genai.GenerativeModel('gemini-2.5-flash').generate_content(vs_prompt)
                        st.success(f"✅ {stock_a} vs {stock_b} 對決報告生成完畢！")
                        st.divider()
                        st.markdown(res.text)
                    except Exception as e: st.error(f"❌ 報告生成失敗：{e}")

# 【分頁 4】Seeking Alpha AI 專業助理
with tab4:
    st.subheader("📖 Seeking Alpha AI 專業閱讀助理")
    if "sa_text_input" not in st.session_state: st.session_state.sa_text_input = ""
    def clear_sa_text(): st.session_state.sa_text_input = ""

    col_sa1, col_sa2 = st.columns([2, 1])
    with col_sa2:
        st.info("💡 **優化指南**\n1. 複製 SA 文章全文\n2. 選擇分析側重點\n3. 點擊生成報告")
        focus_area = st.selectbox("🎯 選擇分析側重點：", ["全面平衡分析 (預設)", "偏重看多與護城河分析", "偏重看空與財報風險預警"])
        st.write("")
        st.button("🗑️ 一鍵清空文章", on_click=clear_sa_text, use_container_width=True)
    with col_sa1:
        sa_article = st.text_area("📝 請在此貼上 Seeking Alpha 文章內容：", height=250, key="sa_text_input")
    
    if st.button("🚀 AI 深度解析 SA 文章", use_container_width=True):
        if not api_key: st.warning("⚠️ 請先輸入 API Key！")
        elif not sa_article.strip(): st.warning("⚠️ 請貼上文章內容！")
        else:
            with st.spinner("🤖 華爾街 AI 助教正在深度解析文章..."):
                try:
                    genai.configure(api_key=api_key)
                    focus_prompt = "請客觀平衡地呈現文章的多空觀點。"
                    if focus_area == "偏重看多與護城河分析": focus_prompt = "請深度挖掘看好該公司的理由、競爭優勢。"
                    elif focus_area == "偏重看空與財報風險預警": focus_prompt = "請深度挖掘潛在風險、財報隱憂或劣勢。"
                    sa_prompt = f"請以「繁體中文」輸出以下重點：\n{focus_prompt}\n1. 🎯 【核心觀點】\n2. 🐂 【看多論點與護城河】\n3. 🐻 【看空論點與風險】\n4. 💡 【關鍵數據與催化劑】\n文章內容如下：\n{sa_article}"
                    res = genai.GenerativeModel('gemini-2.5-flash').generate_content(sa_prompt)
                    st.success(f"✅ 解析完成！")
                    st.write(res.text)
                except Exception as e: st.error(f"❌ AI 解析失敗：{e}")

# 【分頁 5】產業新聞與 AI 總結
with tab5:
    st.subheader("📰 產業新聞與 AI 總結")
    search_query = st.text_input("🔍 查詢產業或公司：", "例如：特斯拉 最新財報與表現")
    if st.button("取得最新消息與 AI 總結"):
        with st.spinner("抓取新聞中..."):
            news_data = get_google_news(search_query)
            if news_data:
                news_text = ""
                for idx, news in enumerate(news_data):
                    st.markdown(f"**{idx + 1}. [{news['title']}]({news['link']})** ⏱️ `{news['date']}`")
                    news_text += f"- {news['title']} (時間: {news['date']})\n"
                if api_key:
                    with st.spinner("🤖 AI 正在提煉重點..."):
                        genai.configure(api_key=api_key)
                        res = genai.GenerativeModel('gemini-2.5-flash').generate_content(f"請總結 3 個產業重點：\n\n{news_text}")
                        st.info("### 🤖 AI 重點總結")
                        st.write(res.text)
            else: st.error("❌ 抓取失敗。")

# 【分頁 6】⭐ 投資計畫與超級複利試算機 
with tab6:
    st.subheader("⭐ 長期投資計畫與超級複利試算機")
    
    live_usd_twd_calc = 32.50
    try:
        usd_res_calc = {}
        fetch_yahoo_single("USDTWD=X", usd_res_calc)
        if "USDTWD=X" in usd_res_calc and usd_res_calc["USDTWD=X"]['price'] > 0:
            live_usd_twd_calc = usd_res_calc["USDTWD=X"]['price']
    except: pass

    live_qqqm, live_voo, live_tw = 0.0, 0.0, 0.0
    with st.spinner("🌍 抓取 QQQM、VOO 與 009816 最新市價中..."):
        try:
            res_dict = {}
            fetch_yahoo_single("QQQM", res_dict)
            fetch_yahoo_single("VOO", res_dict)
            fetch_yahoo_single("009816.TW", res_dict)
            live_qqqm = res_dict.get("QQQM", {}).get("price", 0.0)
            live_voo = res_dict.get("VOO", {}).get("price", 0.0)
            live_tw = res_dict.get("009816.TW", {}).get("price", 0.0)
        except: pass

    if live_qqqm and live_tw:
        st.markdown("#### 1️⃣ 目前持有股數設定")
        col_inv1, col_inv2, col_inv3 = st.columns(3)
        with col_inv1: qqqm_shares = st.number_input("持有 QQQM 股數：", value=0.0, step=0.1)
        with col_inv2: voo_shares = st.number_input("持有 VOO 股數：", value=0.0, step=0.1)
        with col_inv3: tw_shares = st.number_input("持有 009816 股數：", value=0.0, step=1.0)
        
        st.markdown("---")
        st.markdown("#### 2️⃣ 未來定期定額計畫")
        exchange_rate = st.number_input("美金匯率 (自動更新)：", value=float(live_usd_twd_calc))
        invest_years = st.slider("預計投資年限 (年)：", 1, 40, 20)
        
        col_calc1, col_calc2, col_calc3 = st.columns(3)
        with col_calc1:
            qqqm_monthly = st.number_input("每月投入 QQQM (USD)：", value=40, step=10)
            qqqm_rate = st.number_input("QQQM 年化報酬率 (%)：", value=10.0)
        with col_calc2:
            voo_monthly = st.number_input("每月投入 VOO (USD)：", value=40, step=10)
            voo_rate = st.number_input("VOO 年化報酬率 (%)：", value=8.0)
        with col_calc3:
            tw_monthly = st.number_input("每月投入 009816 (TWD)：", value=24375, step=1000)
            tw_rate = st.number_input("009816 年化報酬率 (%)：", value=8.0)

        months = invest_years * 12
        qqqm_m_rate = (qqqm_rate / 100) / 12
        qqqm_fv = (qqqm_shares * live_qqqm * ((1 + qqqm_m_rate) ** months)) + (qqqm_monthly * (((1 + qqqm_m_rate) ** months - 1) / qqqm_m_rate) if qqqm_m_rate > 0 else qqqm_monthly * months)
        
        voo_m_rate = (voo_rate / 100) / 12
        voo_fv = (voo_shares * live_voo * ((1 + voo_m_rate) ** months)) + (voo_monthly * (((1 + voo_m_rate) ** months - 1) / voo_m_rate) if voo_m_rate > 0 else voo_monthly * months)

        tw_m_rate = (tw_rate / 100) / 12
        tw_fv = (tw_shares * live_tw * ((1 + tw_m_rate) ** months)) + (tw_monthly * (((1 + tw_m_rate) ** months - 1) / tw_m_rate) if tw_m_rate > 0 else tw_monthly * months)

        total_future_twd = ((qqqm_fv + voo_fv) * exchange_rate) + tw_fv
        st.success(f"🎉 **{invest_years} 年後，三引擎總資產預估可達：NT$ {total_future_twd:,.0f}**")