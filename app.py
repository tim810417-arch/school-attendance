import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- 1. 初始化模擬資料庫 (存於 session_state) ---
if 'db_students' not in st.session_state:
    # 預設範例資料，實際使用請透過管理員後台匯入
    st.session_state.db_students = pd.DataFrame(columns=['班級', '班號', '姓名', '學號', '上課日'])
if 'db_attendance' not in st.session_state:
    st.session_state.db_attendance = pd.DataFrame(columns=['日期', '班號', '狀態', '點名時間'])
if 'daily_logs' not in st.session_state:
    st.session_state.daily_logs = {} # 格式: { "2024-05-20_班別": 點名次數 }
if 'user_pws' not in st.session_state:
    st.session_state.user_pws = {} # 格式: { "班號": "新密碼" }

# --- 2. 輔助函數 ---
def get_today_weekday():
    days = ["一", "二", "三", "四", "五", "六", "日"]
    return days[datetime.now().weekday()]

# --- 3. 網頁 UI 設計 ---
st.set_page_config(page_title="雲端點名管理系統", layout="wide")

st.sidebar.title("🏫 校園點名網頁版")
role = st.sidebar.radio("切換登入身分", ["家長端", "老師端", "管理者後台"])

# --- 家長端頁面 ---
if role == "家長端":
    st.header("👨‍👩‍👧 家長查詢中心")
    col1, col2 = st.columns(2)
    with col1:
        parent_user = st.text_input("帳號 (學生班號)")
    with col2:
        parent_pw = st.text_input("密碼 (預設學號)", type="password")

    if st.button("登入"):
        student = st.session_state.db_students[st.session_state.db_students['班號'] == parent_user]
        if not student.empty:
            # 檢查密碼 (優先檢查是否有改過新密碼)
            default_pw = str(student.iloc[0]['學號'])
            stored_pw = st.session_state.user_pws.get(parent_user, default_pw)
            
            if parent_pw == stored_pw:
                st.success(f"歡迎 {student.iloc[0]['姓名']} 家長！")
                
                # 修改密碼區塊
                with st.expander("🔐 第一次登入？點此修改密碼"):
                    new_pw = st.text_input("輸入新密碼", type="password")
                    if st.button("確認修改"):
                        st.session_state.user_pws[parent_user] = new_pw
                        st.toast("密碼修改成功！")

                st.divider()
                # 點名狀況顯示
                today_str = datetime.now().strftime("%Y-%m-%d")
                weekday = get_today_weekday()
                st.subheader(f"📅 今日狀態 ({today_str})")
                
                if weekday not in str(student.iloc[0]['上課日']):
                    st.info("今日無課程，無需參加課輔")
                else:
                    record = st.session_state.db_attendance[
                        (st.session_state.db_attendance['日期'] == today_str) & 
                        (st.session_state.db_attendance['班號'] == parent_user)
                    ]
                    if record.empty:
                        st.warning("⏳ 老師尚未進行點名")
                    else:
                        status = record.iloc[0]['狀態']
                        time_tag = record.iloc[0]['點名時間']
                        st.metric(label="出缺席結果", value=status)
                        st.caption(f"老師最後點名時間：{time_tag}")
            else:
                st.error("密碼錯誤，請重新輸入")
        else:
            st.error("查無此帳號")

# --- 老師端頁面 ---
elif role == "老師端":
    st.header("👩‍🏫 老師點名工作區")
    today_str = datetime.now().strftime("%Y-%m-%d")
    weekday = get_today_weekday()
    
    classes = st.session_state.db_students['班級'].unique()
    if len(classes) == 0:
        st.info("目前系統內無班級資料，請管理員先匯入 Excel")
    else:
        target_class = st.selectbox("請選擇班別", classes)
        
        # 篩選今天該上課的人
        class_list = st.session_state.db_students[
            (st.session_state.db_students['班級'] == target_class) & 
            (st.session_state.db_students['上課日'].str.contains(weekday))
        ]
        
        log_key = f"{today_str}_{target_class}"
        submit_count = st.session_state.daily_logs.get(log_key, 0)
        
        if submit_count >= 2:
            st.error(f"⚠️ {target_class} 今日已點名並重新點名過，無法再修改。")
        else:
            st.write(f"正在進行 **{target_class}** 點名 (今天週{weekday})")
            
            # 建立點名表
            new_attendance = []
            for i, row in class_list.iterrows():
                col1, col2 = st.columns([1, 3])
                col1.write(f"{row['班號']} - {row['姓名']}")
                status = col2.radio(f"狀態_{row['班號']}", ["出席", "缺席", "遲到"], horizontal=True, key=f"att_{row['班號']}", label_visibility="collapsed")
                new_attendance.append({"班號": row['班號'], "狀態": status})
            
            label = "送出點名單" if submit_count == 0 else "重新點名 (最後一次機會)"
            if st.button(label, use_container_width=True):
                # 這裡使用 Session State 暫存，模擬提醒彈窗
                st.session_state.confirm_submit = True
            
            if st.session_state.get('confirm_submit', False):
                st.warning(f"是否確定送出 {target_class} 的點名單？")
                if st.button("確認送出"):
                    now_t = datetime.now().strftime("%H:%M:%S")
                    # 刪除該班舊點名紀錄 (針對重新點名)
                    st.session_state.db_attendance = st.session_state.db_attendance[
                        ~((st.session_state.db_attendance['日期'] == today_str) & 
                          (st.session_state.db_attendance['班號'].isin(class_list['班號'])))
                    ]
                    # 寫入新紀錄
                    for item in new_attendance:
                        new_row = pd.DataFrame([{"日期": today_str, "班號": item['班號'], "狀態": item['狀態'], "點名時間": now_t}])
                        st.session_state.db_attendance = pd.concat([st.session_state.db_attendance, new_row], ignore_index=True)
                    
                    st.session_state.daily_logs[log_key] = submit_count + 1
                    st.session_state.confirm_submit = False
                    st.success("✅ 點名紀錄已成功送出！")
                    st.rerun()

# --- 管理者端頁面 ---
elif role == "管理者後台":
    st.header("⚙️ 系統管理中心")
    m_tab1, m_tab2 = st.tabs(["數據管理", "名單匯入與調整"])
    
    with m_tab1:
        st.subheader("📊 即時點名監控")
        st.dataframe(st.session_state.db_attendance, use_container_width=True)
        
        # 匯出 Excel
        if not st.session_state.db_attendance.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state.db_attendance.to_excel(writer, index=False)
            st.download_button("📥 匯出今日點名 Excel", data=output.getvalue(), file_name="attendance_report.xlsx")

    with m_tab2:
        st.subheader("📂 批量匯入學生名單")
        up_file = st.file_uploader("選擇 Excel 檔案 (分頁請設為班級名稱)", type="xlsx")
        if up_file:
            sheets = pd.read_excel(up_file, sheet_name=None)
            full_data = []
            for s_name, df in sheets.items():
                df['班級'] = s_name
                full_data.append(df)
            st.session_state.db_students = pd.concat(full_data, ignore_index=True)
            st.success("名單匯入成功！")
        
        st.divider()
        st.subheader("🔄 手動調整 (如：週一與週三對調)")
        if st.button("執行：週一與週三上課名單對調"):
            def swap_days(day_str):
                day_str = str(day_str)
                res = ""
                for char in day_str:
                    if char == "一": res += "三"
                    elif char == "三": res += "一"
                    else: res += char
                return res
            st.session_state.db_students['上課日'] = st.session_state.db_students['上課日'].apply(swap_days)
            st.toast("調課完成！")
        
        st.dataframe(st.session_state.db_students)
