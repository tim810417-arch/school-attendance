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

        # 將後台分成三個清楚的分頁
        t1, t2, t3 = st.tabs(["👥 學生名單管理", "👩‍🏫 教師帳號管理", "📊 數據與調課"])
        
        with t1:
            st.subheader("學生名單管理")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("➕ **單筆新增學生**")
                n_class = st.text_input("班級 (如: 1A)")
                n_no = st.text_input("班號 (家長登入帳號用)")
                n_name = st.text_input("學生姓名")
                n_sid = st.text_input("學號 (預設密碼)")
                n_days = st.text_input("上課日 (如: 一,三,五)")
                
                if st.button("新增單筆學生", use_container_width=True):
                    if n_class and n_no and n_name:
                        with st.spinner("正在將學生寫入雲端..."):
                            df_s = load_data("Students")
                            new_s = pd.DataFrame([{"班級": n_class, "班號": n_no, "姓名": n_name, "學號": n_sid, "上課日": n_days}])
                            # 將新學生加入舊名單
                            df_s = pd.concat([df_s, new_s], ignore_index=True) if not df_s.empty else new_s
                            if save_data("Students", df_s):
                                st.success(f"✅ 已成功新增學生: {n_name}")
                            else:
                                st.error("寫入失敗，請稍後再試。")
                    else:
                        st.warning("⚠️ 請至少填寫班級、班號與姓名")
                        
            with col2:
                st.write("📂 **批次匯入學生 (Excel)**")
                st.info("⚠️ 注意：批次匯入會【覆蓋】目前的雲端名單")
                up_s = st.file_uploader("上傳學生名單 Excel", type="xlsx")
                if up_s:
                    sheets = pd.read_excel(up_s, sheet_name=None, dtype=str)
                    all_s = pd.concat([df.assign(班級=n) for n, df in sheets.items()], ignore_index=True)
                    
                    if st.button("確認覆蓋寫入雲端 (學生)", use_container_width=True):
                        with st.spinner("正在寫入 Students 分頁..."):
                            save_data("Students", all_s)
                        st.success("🎉 學生批次名單已更新！")

        with t2:
            st.subheader("教師名單管理")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("➕ **單筆新增教師**")
                n_t_acc = st.text_input("教師帳號")
                n_t_name = st.text_input("教師姓名")
                n_t_pw = st.text_input("教師密碼")
                
                if st.button("新增單筆教師", use_container_width=True):
                    if n_t_acc and n_t_name and n_t_pw:
                        with st.spinner("正在將教師寫入雲端..."):
                            df_t = load_data("Teachers")
                            new_t = pd.DataFrame([{"教師帳號": n_t_acc, "姓名": n_t_name, "密碼": n_t_pw}])
                            # 將新教師加入舊名單
                            df_t = pd.concat([df_t, new_t], ignore_index=True) if not df_t.empty else new_t
                            if save_data("Teachers", df_t):
                                st.success(f"✅ 已成功新增教師: {n_t_name}")
                            else:
                                st.error("寫入失敗，請稍後再試。")
                    else:
                        st.warning("⚠️ 請填寫完整教師資訊")
                        
            with col2:
                st.write("📂 **批次匯入教師 (Excel)**")
                st.info("⚠️ 注意：批次匯入會【覆蓋】目前的雲端名單")
                up_t = st.file_uploader("上傳教師名單 Excel", type="xlsx")
                if up_t:
                    df_t_excel = pd.read_excel(up_t, dtype=str)
                    
                    if st.button("確認覆蓋寫入雲端 (教師)", use_container_width=True):
                        with st.spinner("正在寫入 Teachers 分頁..."):
                            save_data("Teachers", df_t_excel)
                        st.success("🎉 教師批次名單已更新！")

        with t3:
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
