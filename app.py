import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import io

# --- 1. 系統與時區設定 ---
ADMIN_PASSWORD = st.secrets.get("password", "admin123")
tz = pytz.timezone('Asia/Taipei')

# --- 2. 初始化 Session State ---
if 'db_students' not in st.session_state:
    st.session_state.db_students = pd.DataFrame(columns=['班級', '班號', '姓名', '學號', '上課日'])
if 'db_teachers' not in st.session_state:
    st.session_state.db_teachers = pd.DataFrame(columns=['教師編號', '姓名', '密碼', '負責班級'])
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
    now_tw = datetime.now(tz)
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    return weekdays[now_tw.weekday()]

# --- 4. 網頁 UI ---
st.set_page_config(page_title="校園雲端點名管理系統", layout="wide")
st.sidebar.title("🏫 點名管理系統")
role = st.sidebar.radio("登入身分", ["家長查詢", "教師點名", "管理者後台"])

# --- A. 家長查詢端 ---
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
                # 取得今日台灣日期
                today_str = datetime.now(tz).strftime("%Y-%m-%d")
                record = st.session_state.db_attendance[(st.session_state.db_attendance['日期'] == today_str) & (st.session_state.db_attendance['班號'].astype(str) == p_id)]
                if not record.empty:
                    st.metric("今日狀態", record.iloc[0]['狀態'])
                    st.caption(f"老師點名時間(台灣)：{record.iloc[0]['點名時間']}")
                else: st.info("今日尚未點名")
            else: st.error("密碼錯誤")
        else: st.error("查無此班號")

# --- B. 教師點名端 ---
elif role == "教師點名":
    st.header("👩‍🏫 教師點名工作區")
    if 't_auth' not in st.session_state: st.session_state.t_auth = None

    if st.session_state.t_auth is None:
        t_id = st.text_input("教師編號")
        t_pw = st.text_input("教師密碼", type="password")
        if st.button("教師登入"):
            teacher = st.session_state.db_teachers[st.session_state.db_teachers['教師編號'].astype(str) == t_id]
            if not teacher.empty and str(teacher.iloc[0]['密碼']) == t_pw:
                st.session_state.t_auth = teacher.iloc[0].to_dict()
                st.rerun()
            else: st.error("編號或密碼錯誤")
    else:
        st.sidebar.write(f"當前教師：{st.session_state.t_auth['姓名']}")
        if st.sidebar.button("教師登出"):
            st.session_state.t_auth = None
            st.rerun()

        # 使用時區修正時間與星期
        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        weekday = get_weekday()
        
        my_classes = str(st.session_state.t_auth['負責班級']).split(',')
        target_class = st.selectbox("請選擇班別", my_classes)
        
        class_list = st.session_state.db_students[(st.session_state.db_students['班級'] == target_class) & (st.session_state.db_students['上課日'].str.contains(weekday))]
        
        log_key = f"{today_str}_{target_class}"
        submit_count = st.session_state.daily_logs.get(log_key, 0)
        
        if submit_count >= 2:
            st.error("今日點名次數已達上限 (2次)")
        else:
            st.write(f"今日日期：{today_str} (週{weekday})")
            new_data = []
            for i, row in class_list.iterrows():
                c1, c2 = st.columns([1, 2])
                c1.write(f"**{row['班號']}** {row['姓名']}")
                status = c2.radio(f"狀態_{row['班號']}", ["出席", "缺席", "遲到"], horizontal=True, key=f"t_{row['班號']}")
                new_data.append({"班號": row['班號'], "狀態": status})
            
            if st.button("送出點名單", use_container_width=True):
                # 儲存點名時間為台灣時間
                now_time = datetime.now(tz).strftime("%H:%M:%S")
                st.session_state.db_attendance = st.session_state.db_attendance[~((st.session_state.db_attendance['日期'] == today_str) & (st.session_state.db_attendance['班號'].isin(class_list['班號'])))]
                for item in new_data:
                    new_row = pd.DataFrame([{"日期": today_str, "班號": item['班號'], "狀態": item['狀態'], "點名時間": now_time}])
                    st.session_state.db_attendance = pd.concat([st.session_state.db_attendance, new_row], ignore_index=True)
                st.session_state.daily_logs[log_key] = submit_count + 1
                st.success("點名成功！")
                st.rerun()

# --- C. 管理者後台 ---
elif role == "管理者後台":
    st.header("⚙️ 管理者後台")
    if not st.session_state.admin_auth:
        pw_input = st.text_input("管理員密碼", type="password")
        if st.button("驗證進入"):
            if pw_input == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else: st.error("密碼錯誤")
    else:
        if st.sidebar.button("登出管理員"):
            st.session_state.admin_auth = False
            st.rerun()

        t1, t2, t3, t4 = st.tabs(["📊 數據監控", "👥 學生管理", "👩‍🏫 教師管理", "🔄 調課模組"])
        
        with t1:
            st.subheader("今日點名概況 (台灣時間)")
            st.dataframe(st.session_state.db_attendance, use_container_width=True)
            csv = st.session_state.db_attendance.to_csv(index=False).encode('utf-8-sig')
            st.download_button("下載今日報表", data=csv, file_name=f"點名報表_{datetime.now(tz).strftime('%Y%m%d')}.csv")
            
        with t2:
            st.subheader("批次學生名單匯入")
            uploaded_file = st.file_uploader("上傳學生 Excel", type="xlsx", key="student_up")
            if uploaded_file:
                sheets = pd.read_excel(uploaded_file, sheet_name=None)
                all_df = []
                for s_name, df in sheets.items():
                    df['班級'] = s_name
                    all_df.append(df)
                st.session_state.db_students = pd.concat(all_df, ignore_index=True)
                st.success("學生名單已更新")
            st.dataframe(st.session_state.db_students)

        with t3:
            st.subheader("教師帳號管理")
            col_t1, col_t2 = st.columns([1, 1])
            with col_t1:
                st.write("單筆新增教師")
                new_t_id = st.text_input("教師編號")
                new_t_name = st.text_input("教師姓名")
                new_t_pw = st.text_input("教師密碼")
                new_t_class = st.text_input("負責班級 (如: 101,102)")
                if st.button("新增教師"):
                    new_teacher = pd.DataFrame([{"教師編號": new_t_id, "姓名": new_t_name, "密碼": new_t_pw, "負責班級": new_t_class}])
                    st.session_state.db_teachers = pd.concat([st.session_state.db_teachers, new_teacher], ignore_index=True)
                    st.success(f"教師 {new_t_name} 已新增")
            
            with col_t2:
                st.write("批次匯入教師 (Excel)")
                t_file = st.file_uploader("上傳教師名單 Excel", type="xlsx", key="teacher_up")
                if t_file:
                    st.session_state.db_teachers = pd.read_excel(t_file)
                    st.success("教師名單已更新")
            st.dataframe(st.session_state.db_teachers)

        with t4:
            st.subheader("調課模組")
            # 保留調課邏輯...
            classes = ["全部班級"] + list(st.session_state.db_students['班級'].unique())
            sel_class = st.selectbox("調整班級", classes)
            d1 = st.selectbox("原日期", ["週一", "週二", "週三", "週四", "週五"])
            d2 = st.selectbox("對調目標", ["週一", "週二", "週三", "週四", "週五"])
            if st.button("執行對調"):
                day_map = {"週一": "一", "週二": "二", "週三": "三", "週四": "四", "週五": "五"}
                d1_v, d2_v = day_map[d1], day_map[d2]
                def swap_logic(row):
                    if sel_class == "全部班級" or row['班級'] == sel_class:
                        s = str(row['上課日'])
                        s = s.replace(d1_v, "TEMP").replace(d2_v, d1_v).replace("TEMP", d2_v)
                        return s
                    return row['上課日']
                st.session_state.db_students['上課日'] = st.session_state.db_students.apply(swap_logic, axis=1)
                st.success("對調完成")
                st.dataframe(st.session_state.db_students)
