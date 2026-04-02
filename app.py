import streamlit as st
import pandas as pd
from datetime import datetime
import io

# --- 1. 系統安全性設定 ---
# 優先從 Streamlit Secrets 讀取密碼，若未設定則預設為 "admin123"
ADMIN_PASSWORD = st.secrets.get("password", "admin123")

# --- 2. 初始化 Session State (模擬資料庫) ---
if 'db_students' not in st.session_state:
    st.session_state.db_students = pd.DataFrame(columns=['班級', '班號', '姓名', '學號', '上課日'])
if 'db_attendance' not in st.session_state:
    st.session_state.db_attendance = pd.DataFrame(columns=['日期', '班號', '狀態', '點名時間'])
if 'daily_logs' not in st.session_state:
    st.session_state.daily_logs = {} # 格式: { "日期_班級": 點名次數 }
if 'user_pws' not in st.session_state:
    st.session_state.user_pws = {} # 格式: { "班號": "自訂密碼" }
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False

# --- 3. 輔助工具函數 ---
def get_weekday():
    # 轉換 Python 星期數字到中文
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    return weekdays[datetime.now().weekday()]

# --- 4. 網頁佈局 ---
st.set_page_config(page_title="校園雲端點名系統", layout="wide")
st.sidebar.title("🏫 點名管理系統")
role = st.sidebar.radio("請選擇登入身分", ["家長查詢", "教師點名", "管理者後台"])

# --- A. 家長查詢端 ---
if role == "家長查詢":
    st.header("👨‍👩‍👧 家長查詢中心")
    c1, c2 = st.columns(2)
    with c1:
        p_id = st.text_input("學生班號 (帳號)")
    with c2:
        p_pw = st.text_input("密碼 (預設為學號)", type="password")

    if st.button("登入並查看狀態", use_container_width=True):
        student = st.session_state.db_students[st.session_state.db_students['班號'].astype(str) == p_id]
        if not student.empty:
            # 檢查密碼
            default_pw = str(student.iloc[0]['學號'])
            correct_pw = st.session_state.user_pws.get(p_id, default_pw)
            
            if p_pw == correct_pw:
                st.success(f"✅ 登入成功！學生姓名：{student.iloc[0]['姓名']}")
                
                # 修改密碼功能
                with st.expander("🔐 首次登入？點此修改密碼"):
                    new_pw = st.text_input("設定新密碼", type="password")
                    if st.button("確認更新"):
                        st.session_state.user_pws[p_id] = new_pw
                        st.toast("密碼已更新！下次請使用新密碼。")

                st.divider()
                # 顯示點名資訊
                today_str = datetime.now().strftime("%Y-%m-%d")
                weekday = get_weekday()
                st.subheader(f"📅 今日狀態：{today_str} (週{weekday})")
                
                if weekday not in str(student.iloc[0]['上課日']):
                    st.info("ℹ️ 今日該生不需參加課輔。")
                else:
                    record = st.session_state.db_attendance[
                        (st.session_state.db_attendance['日期'] == today_str) & 
                        (st.session_state.db_attendance['班號'].astype(str) == p_id)
                    ]
                    if record.empty:
                        st.warning("⏳ 老師尚未點名，請稍後再試。")
                    else:
                        st.metric(label="出缺席結果", value=record.iloc[0]['狀態'])
                        st.caption(f"老師最後點名時間：{record.iloc[0]['點名時間']}")
            else:
                st.error("❌ 密碼錯誤！")
        else:
            st.error("❌ 查無此班號，請確認輸入是否正確。")

# --- B. 教師點名端 ---
elif role == "教師點名":
    st.header("👩‍🏫 教師點名工作區")
    today_str = datetime.now().strftime("%Y-%m-%d")
    weekday = get_weekday()
    
    classes = st.session_state.db_students['班級'].unique()
    if len(classes) == 0:
        st.info("目前系統尚無名單，請管理者先匯入 Excel。")
    else:
        target_class = st.selectbox("請選擇班別", classes)
        
        # 篩選今日需點名的名單
        class_list = st.session_state.db_students[
            (st.session_state.db_students['班級'] == target_class) & 
            (st.session_state.db_students['上課日'].str.contains(weekday))
        ]
        
        log_key = f"{today_str}_{target_class}"
        submit_count = st.session_state.daily_logs.get(log_key, 0)
        
        if submit_count >= 2:
            st.error(f"🛑 {target_class} 今日已完成「點名」與「重新點名」，無法再次修改。")
        else:
            st.write(f"今日日期：{today_str} (週{weekday})")
            
            # 建立互動點名表
            new_data = []
            for i, row in class_list.iterrows():
                col1, col2 = st.columns([1, 2])
                col1.write(f"**{row['班號']}** {row['姓名']}")
                status = col2.radio(f"狀態_{row['班號']}", ["出席", "缺席", "遲到"], horizontal=True, key=f"t_{row['班號']}", label_visibility="collapsed")
                new_data.append({"班號": row['班號'], "狀態": status})
            
            btn_text = "確認送出點名單" if submit_count == 0 else "重新點名 (最後一次機會)"
            if st.button(btn_text, use_container_width=True, type="primary"):
                st.session_state.temp_submit = new_data
                st.warning("⚠️ 是否確定送出點名單？送出後每天僅限修改一次。")
                if st.button("我確定，正式送出"):
                    now_time = datetime.now().strftime("%H:%M:%S")
                    
                    # 移除舊紀錄並存入新紀錄
                    st.session_state.db_attendance = st.session_state.db_attendance[
                        ~((st.session_state.db_attendance['日期'] == today_str) & 
                          (st.session_state.db_attendance['班號'].isin(class_list['班號'])))
                    ]
                    for item in st.session_state.temp_submit:
                        new_row = pd.DataFrame([{"日期": today_str, "班號": item['班號'], "狀態": item['狀態'], "點名時間": now_time}])
                        st.session_state.db_attendance = pd.concat([st.session_state.db_attendance, new_row], ignore_index=True)
                    
                    st.session_state.daily_logs[log_key] = submit_count + 1
                    st.success("✅ 點名紀錄已成功儲存！")
                    st.rerun()

# --- C. 管理者後台 ---
elif role == "管理者後台":
    st.header("⚙️ 系統管理後台")
    
    if not st.session_state.admin_auth:
        pw_input = st.text_input("請輸入管理員密碼", type="password")
        if st.button("登入驗證"):
            if pw_input == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("密碼錯誤，拒絕進入。")
    else:
        if st.sidebar.button("登出管理員身分"):
            st.session_state.admin_auth = False
            st.rerun()

        tab1, tab2 = st.tabs(["📊 數據與匯出", "📂 名單匯入與調整"])
        
        with tab1:
            st.subheader("即時點名數據監控")
            st.dataframe(st.session_state.db_attendance, use_container_width=True)
            
            if not st.session_state.db_attendance.empty:
                csv = st.session_state.db_attendance.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 匯出點名紀錄 (CSV)", data=csv, file_name=f"點名報表_{datetime.now().strftime('%Y%m%d')}.csv")

        with tab2:
            st.subheader("學生名單批次匯入")
            uploaded_file = st.file_uploader("上傳 Excel (分頁為班級名稱)", type="xlsx")
            if uploaded_file:
                sheets = pd.read_excel(uploaded_file, sheet_name=None)
                all_df = []
                for sheet_name, df in sheets.items():
                    df['班級'] = sheet_name
                    all_df.append(df)
                st.session_state.db_students = pd.concat(all_df, ignore_index=True)
                st.success("🎉 名單匯入成功！")
            
            st.divider()
            st.subheader("手動日程調整")
            if st.button("🔄 執行週一與週三對調"):
                def swap_mon_wed(val):
                    val = str(val)
                    new_val = val.replace("一", "TEMP").replace("三", "一").replace("TEMP", "三")
                    return new_val
                st.session_state.db_students['上課日'] = st.session_state.db_students['上課日'].apply(swap_mon_wed)
                st.toast("調課完成！")
            
            st.write("目前系統名單總表：")
            st.dataframe(st.session_state.db_students, use_container_width=True)
