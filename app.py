import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- 1. 系統安全性設定 ---
ADMIN_PASSWORD = st.secrets.get("password", "admin123")

# --- 2. 初始化 Session State ---
if 'db_students' not in st.session_state:
    st.session_state.db_students = pd.DataFrame(columns=['班級', '班號', '姓名', '學號', '上課日'])
if 'db_attendance' not in st.session_state:
    st.session_state.db_attendance = pd.DataFrame(columns=['日期', '班號', '狀態', '點名時間'])
if 'daily_logs' not in st.session_state:
    st.session_state.daily_logs = {} 
if 'user_pws' not in st.session_state:
    st.session_state.user_pws = {}
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False

# --- 3. 輔助函數 ---
def get_weekday():
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    return weekdays[datetime.now().weekday()]

# --- 4. 網頁 UI ---
st.set_page_config(page_title="校園點名管理系統", layout="wide")
st.sidebar.title("🏫 點名管理系統")
role = st.sidebar.radio("登入身分", ["家長查詢", "教師點名", "管理者後台"])

# --- A. 家長端 (邏輯同前，簡略顯示) ---
if role == "家長查詢":
    st.header("👨‍👩‍👧 家長查詢中心")
    p_id = st.text_input("學生班號")
    p_pw = st.text_input("密碼", type="password")
    if st.button("登入查詢", use_container_width=True):
        student = st.session_state.db_students[st.session_state.db_students['班號'].astype(str) == p_id]
        if not student.empty:
            correct_pw = st.session_state.user_pws.get(p_id, str(student.iloc[0]['學號']))
            if p_pw == correct_pw:
                st.success(f"歡迎 {student.iloc[0]['姓名']} 家長")
                # 顯示點名紀錄邏輯...
                today_str = datetime.now().strftime("%Y-%m-%d")
                record = st.session_state.db_attendance[(st.session_state.db_attendance['日期'] == today_str) & (st.session_state.db_attendance['班號'].astype(str) == p_id)]
                if not record.empty:
                    st.metric("今日狀態", record.iloc[0]['狀態'])
                    st.caption(f"點名時間：{record.iloc[0]['點名時間']}")
                else: st.info("今日尚未點名")
            else: st.error("密碼錯誤")
        else: st.error("查無此班號")

# --- B. 教師端 ---
elif role == "教師點名":
    st.header("👩‍🏫 教師點名工作區")
    today_str = datetime.now().strftime("%Y-%m-%d")
    weekday = get_weekday()
    classes = st.session_state.db_students['班級'].unique()
    
    if len(classes) == 0:
        st.info("請聯絡管理員匯入名單")
    else:
        target_class = st.selectbox("請選擇班別", classes)
        class_list = st.session_state.db_students[(st.session_state.db_students['班級'] == target_class) & (st.session_state.db_students['上課日'].str.contains(weekday))]
        
        log_key = f"{today_str}_{target_class}"
        submit_count = st.session_state.daily_logs.get(log_key, 0)
        
        if submit_count >= 2:
            st.error("今日點名次數已達上限 (2次)")
        else:
            # 點名表單生成...
            new_data = []
            for i, row in class_list.iterrows():
                c1, c2 = st.columns([1, 2])
                c1.write(f"**{row['班號']}** {row['姓名']}")
                status = c2.radio(f"狀態_{row['班號']}", ["出席", "缺席", "遲到"], horizontal=True, key=f"t_{row['班號']}", label_visibility="collapsed")
                new_data.append({"班號": row['班號'], "狀態": status})
            
            if st.button("送出點名單", use_container_width=True):
                now_time = datetime.now().strftime("%H:%M:%S")
                st.session_state.db_attendance = st.session_state.db_attendance[~((st.session_state.db_attendance['日期'] == today_str) & (st.session_state.db_attendance['班號'].isin(class_list['班號'])))]
                for item in new_data:
                    new_row = pd.DataFrame([{"日期": today_str, "班號": item['班號'], "狀態": item['狀態'], "點名時間": now_time}])
                    st.session_state.db_attendance = pd.concat([st.session_state.db_attendance, new_row], ignore_index=True)
                st.session_state.daily_logs[log_key] = submit_count + 1
                st.success("點名成功")
                st.rerun()

# --- C. 管理者後台 (強化版) ---
elif role == "管理者後台":
    st.header("⚙️ 管理者後台控制台")
    
    if not st.session_state.admin_auth:
        pw_input = st.text_input("請輸入管理員密碼", type="password")
        if st.button("登入驗證"):
            if pw_input == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else: st.error("密碼錯誤")
    else:
        if st.sidebar.button("登出管理員"):
            st.session_state.admin_auth = False
            st.rerun()

        t1, t2, t3 = st.tabs(["📊 數據監控", "📂 名單匯入", "🔄 調課模組"])
        
        with t1:
            st.subheader("今日點名概況")
            st.dataframe(st.session_state.db_attendance, use_container_width=True)
            csv = st.session_state.db_attendance.to_csv(index=False).encode('utf-8-sig')
            st.download_button("下載今日報表", data=csv, file_name="attendance.csv")

        with t2:
            st.subheader("批次名單匯入")
            with st.expander("📝 查看 Excel 格式說明 (請務必遵守)"):
                st.write("""
                1. **檔案格式**：必須為 `.xlsx` 檔案。
                2. **分頁名稱 (Sheet)**：每個分頁名稱代表一個「班級」(例如：一年甲班)。
                3. **欄位定義**：每個分頁的第一列必須包含以下四個欄位：
                   - `班號`：家長登入帳號 (例如：101)。
                   - `姓名`：學生姓名。
                   - `學號`：家長預設密碼。
                   - `上課日`：填寫『一二三四五』中的組合 (例如：`一三五` 代表週一、三、五上課)。
                """)
                # 提供範例下載
                example_df = pd.DataFrame({
                    "班號": ["A01", "A02"], "姓名": ["王小明", "李小華"],
                    "學號": ["S12345", "S67890"], "上課日": ["一三五", "二四"]
                })
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    example_df.to_excel(writer, sheet_name='範例班級', index=False)
                st.download_button("下載 Excel 範本檔案", data=output.getvalue(), file_name="template.xlsx")

            uploaded_file = st.file_uploader("上傳學生名單", type="xlsx")
            if uploaded_file:
                sheets = pd.read_excel(uploaded_file, sheet_name=None)
                all_df = []
                for s_name, df in sheets.items():
                    df['班級'] = s_name
                    all_df.append(df)
                st.session_state.db_students = pd.concat(all_df, ignore_index=True)
                st.success("名單匯入成功！")

        with t3:
            st.subheader("彈性調課模組")
            st.info("此功能會直接修改學生名單中的「上課日」設定。")
            
            classes = ["全部班級"] + list(st.session_state.db_students['班級'].unique())
            sel_class = st.selectbox("請選擇要調整的班級", classes)
            
            col_a, col_b = st.columns(2)
            day_map = {"週一": "一", "週二": "二", "週三": "三", "週四": "四", "週五": "五"}
            with col_a:
                day_1 = st.selectbox("原日期", list(day_map.keys()))
            with col_b:
                day_2 = st.selectbox("對調目標日期", list(day_map.keys()))
            
            if st.button(f"執行對調：{day_1} ↔ {day_2}"):
                d1_val = day_map[day_1]
                d2_val = day_map[day_2]
                
                def swap_logic(row):
                    # 只有選中班級或選全部才處理
                    if sel_class == "全部班級" or row['班級'] == sel_class:
                        s = str(row['上課日'])
                        # 使用暫存字元進行置換
                        s = s.replace(d1_val, "TEMP").replace(d2_val, d1_val).replace("TEMP", d2_val)
                        return s
                    return row['上課日']
                
                st.session_state.db_students['上課日'] = st.session_state.db_students.apply(swap_logic, axis=1)
                st.success(f"已完成「{sel_class}」的 {day_1} 與 {day_2} 對調！")
                st.dataframe(st.session_state.db_students)
