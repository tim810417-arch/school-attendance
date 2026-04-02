import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import requests

# --- 1. 系統與時區設定 ---
ADMIN_PASSWORD = st.secrets.get("password", "admin123")
SHEET_ID = st.secrets["SHEET_ID"]
WEB_APP_URL = st.secrets["WEB_APP_URL"]
tz = pytz.timezone('Asia/Taipei')

# --- 2. 自製 Google Sheets 讀寫引擎 ---
def load_data(sheet_name):
    # 利用 Google 官方的 CSV 匯出網址來讀取資料 (試算表必須是"知道連結者皆可編輯")
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        # 把所有缺失值填補為字串，避免顯示 NaN
        return df.fillna("")
    except Exception:
        return pd.DataFrame()

def save_data(sheet_name, df):
    # 確保沒有 NaN，轉為純文字後送到 Apps Script
    df = df.fillna("")
    # 將 DataFrame 轉成二維陣列 [ [標題1, 標題2], [資料1, 資料2] ]
    data = [df.columns.tolist()] + df.values.tolist()
    payload = {"sheet": sheet_name, "data": data}
    try:
        res = requests.post(WEB_APP_URL, json=payload)
        return "Success" in res.text
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return False

def get_weekday():
    now_tw = datetime.now(tz)
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    return weekdays[now_tw.weekday()]

# --- 3. 網頁 UI ---
st.set_page_config(page_title="雲端點名系統", layout="wide")
st.sidebar.title("🏫 校園點名管理")
role = st.sidebar.radio("請選擇登入身分", ["家長查詢", "教師點名", "管理者後台"])

# --- A. 家長端 ---
if role == "家長查詢":
    st.header("👨‍👩‍👧 家長查詢中心")
    p_id = st.text_input("學生班號")
    p_pw = st.text_input("密碼", type="password")
    
    if st.button("登入查詢", use_container_width=True):
        df_students = load_data("Students")
        if not df_students.empty:
            student = df_students[df_students['班號'].astype(str) == p_id]
            if not student.empty:
                df_pws = load_data("Passwords")
                custom_pw = df_pws[df_pws['班號'].astype(str) == p_id] if not df_pws.empty else pd.DataFrame()
                
                # 取學號的整數(若有小數點)，或自訂密碼
                original_pw = str(student.iloc[0]['學號']).replace(".0", "")
                correct_pw = str(custom_pw.iloc[0]['密碼']).replace(".0", "") if not custom_pw.empty else original_pw
                
                if p_pw == correct_pw:
                    st.success(f"歡迎 {student.iloc[0]['姓名']} 家長")
                    today_str = datetime.now(tz).strftime("%Y-%m-%d")
                    df_att = load_data("Attendance")
                    
                    if not df_att.empty:
                        record = df_att[(df_att['日期'].astype(str) == today_str) & (df_att['班號'].astype(str) == p_id)]
                        if not record.empty:
                            st.metric("今日狀態", record.iloc[0]['狀態'])
                            st.caption(f"點名時間：{record.iloc[0]['點名時間']}")
                        else: st.info("老師今日尚未點名")
                    else: st.info("老師今日尚未點名")
                else: st.error("密碼錯誤")
            else: st.error("查無此班號")

# --- B. 教師端 ---
elif role == "教師點名":
    st.header("👩‍🏫 教師點名工作區")
    
    if 't_user' not in st.session_state: st.session_state.t_user = None

    if st.session_state.t_user is None:
        t_acc = st.text_input("教師帳號")
        t_pw = st.text_input("教師密碼", type="password")
        if st.button("登入系統"):
            df_teachers = load_data("Teachers")
            if not df_teachers.empty:
                # 轉字串處理並忽略浮點數 .0
                teacher = df_teachers[(df_teachers['教師帳號'].astype(str).str.replace(".0","") == t_acc) & 
                                      (df_teachers['密碼'].astype(str).str.replace(".0","") == t_pw)]
                if not teacher.empty:
                    st.session_state.t_user = teacher.iloc[0]['姓名']
                    st.rerun()
                else: st.error("帳號或密碼錯誤")
            else: st.warning("系統內尚無教師資料，請聯絡管理員。")
    else:
        st.sidebar.write(f"登入身分：{st.session_state.t_user} 老師")
        if st.sidebar.button("登出"):
            st.session_state.t_user = None
            st.rerun()

        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        weekday = get_weekday()
        
        df_students = load_data("Students")
        if not df_students.empty:
            all_classes = [c for c in df_students['班級'].unique() if str(c).strip() != ""]
            target_class = st.selectbox("選擇要點名的班級", all_classes)
            
            class_list = df_students[(df_students['班級'] == target_class) & (df_students['上課日'].astype(str).str.contains(weekday))]
            
            st.write(f"📅 {today_str} (週{weekday}) | 班級：{target_class}")
            
            if class_list.empty:
                st.warning("此班級今日無學生需上課。")
            else:
                new_data = []
                for i, row in class_list.iterrows():
                    c1, c2 = st.columns([1, 2])
                    c1.write(f"**{row['班號']}** {row['姓名']}")
                    status = c2.radio("狀態", ["出席", "缺席", "遲到"], horizontal=True, key=f"t_{row['班號']}")
                    new_data.append({"日期": today_str, "班號": row['班號'], "狀態": status, "點名時間": datetime.now(tz).strftime("%H:%M:%S")})
                
                if st.button("送出點名紀錄", use_container_width=True):
                    with st.spinner("正在儲存至 Google Sheets..."):
                        df_att_old = load_data("Attendance")
                        
                        if not df_att_old.empty:
                            s_ids = class_list['班號'].astype(str).tolist()
                            df_att_keep = df_att_old[~((df_att_old['日期'].astype(str) == today_str) & (df_att_old['班號'].astype(str).isin(s_ids)))]
                            df_final = pd.concat([df_att_keep, pd.DataFrame(new_data)], ignore_index=True)
                        else:
                            df_final = pd.DataFrame(new_data)
                        
                        # 呼叫寫入函數
                        success = save_data("Attendance", df_final)
                        
                    if success:
                        st.success("✅ 點名資料已成功寫入！")
                    else:
                        st.error("寫入失敗，請檢查網路或網址設定。")
        else:
            st.info("尚未匯入學生名單。")

# --- C. 管理者後台 ---
elif role == "管理者後台":
    st.header("⚙️ 系統管理後台")
    if not st.session_state.get('admin_auth', False):
        pw_input = st.text_input("輸入管理員密碼", type="password")
        if st.button("進入後台"):
            if pw_input == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else: st.error("密碼錯誤")
    else:
        if st.sidebar.button("登出管理員"):
            st.session_state.admin_auth = False
            st.rerun()

        t1, t2 = st.tabs(["📝 Excel 名單匯入", "📊 數據與調課"])
        
        with t1:
            st.subheader("1. 匯入學生名單")
            up_s = st.file_uploader("上傳學生名單 Excel", type="xlsx")
            if up_s:
                sheets = pd.read_excel(up_s, sheet_name=None, dtype=str)
                all_s = pd.concat([df.assign(班級=n) for n, df in sheets.items()], ignore_index=True)
                
                if st.button("確認寫入雲端 (學生)"):
                    with st.spinner("正在寫入 Students 分頁..."):
                        save_data("Students", all_s)
                    st.success("🎉 學生名單已更新！")

            st.divider()
            
            st.subheader("2. 匯入教師名單")
            up_t = st.file_uploader("上傳教師名單 Excel", type="xlsx")
            if up_t:
                df_t = pd.read_excel(up_t, dtype=str)
                
                if st.button("確認寫入雲端 (教師)"):
                    with st.spinner("正在寫入 Teachers 分頁..."):
                        save_data("Teachers", df_t)
                    st.success("🎉 教師名單已更新！")

        with t2:
            st.subheader("點名資料預覽")
            df_att = load_data("Attendance")
            st.dataframe(df_att, use_container_width=True)
            
            st.divider()
            st.subheader("臨時調課")
            df_students = load_data("Students")
            if not df_students.empty:
                classes = ["全部班級"] + [c for c in df_students['班級'].unique() if str(c).strip() != ""]
                sel_class = st.selectbox("調整班級", classes)
                d1 = st.selectbox("原日期", ["週一", "週二", "週三", "週四", "週五"])
                d2 = st.selectbox("對調目標", ["週一", "週二", "週三", "週四", "週五"])
                
                if st.button("執行對調並寫入雲端"):
                    day_map = {"週一": "一", "週二": "二", "週三": "三", "週四": "四", "週五": "五"}
                    d1_v, d2_v = day_map[d1], day_map[d2]
                    
                    def swap_logic(row):
                        if sel_class == "全部班級" or row['班級'] == sel_class:
                            s = str(row['上課日'])
                            return s.replace(d1_v, "TEMP").replace(d2_v, d1_v).replace("TEMP", d2_v)
                        return row['上課日']
                    
                    with st.spinner("正在更新調課資料..."):
                        df_students['上課日'] = df_students.apply(swap_logic, axis=1)
                        save_data("Students", df_students)
                    st.success("對調完成！")
