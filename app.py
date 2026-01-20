import streamlit as st
import pandas as pd
import datetime
import calendar
import time
import gspread
import extra_streamlit_components as stx
from oauth2client.service_account import ServiceAccountCredentials
import re 
from korean_lunar_calendar import KoreanLunarCalendar

# --- [설정] 구글 시트 파일 이름 ---
SHEET_NAME = "교회출석데이터"

# --- [설정] 부서별 표시할 모임 정의 ---
COLS_ADULT = ["주일 1부", "주일 2부", "주일 오후", "소그룹 모임"]
COLS_YOUTH = ["주일 1부", "주일 2부", "주일 오후", "중고등부"]
COLS_YOUNG = ["주일 1부", "주일 2부", "주일 오후", "청년부"]
COLS_KIDS = ["주일학교"]

# 전체 모임 리스트
SUNDAY_ALL = list(set(COLS_ADULT + COLS_YOUTH + COLS_YOUNG + COLS_KIDS))

# 요일별 설정
MEETING_CONFIG = {
    6: SUNDAY_ALL, # 일요일
    2: ["수요예배"], # 수요일
    4: ["금요철야"]  # 금요일
}

# 통계용 전체 컬럼 순서
ALL_MEETINGS_ORDERED = ["주일 1부", "주일 2부", "주일 오후", "주일학교", "중고등부", "청년부", "소그룹 모임", "수요예배", "금요철야"]

# 페이지 기본 설정
st.set_page_config(page_title="회정교회 출석부 v9.0", layout="wide", initial_sidebar_state="collapsed")

# --- [스타일] CSS 적용 ---
st.markdown("""
    <style>
    html, body, p, li, .stMarkdown { font-size: 18px !important; }
    h1 { 
        font-size: 46px !important; text-align: center; word-break: keep-all; 
        margin-bottom: 30px !important; font-weight: 800 !important;
    }
    .stButton button { font-size: 20px !important; font-weight: bold; width: 100%; }
    .notice-box {
        background-color: #fff3cd; border: 2px solid #ffeeba; color: #856404;
        padding: 15px; border-radius: 10px; margin-bottom: 20px;
        text-align: center; font-size: 20px; font-weight: bold; line-height: 1.5; word-break: keep-all;
    }
    .calendar-container { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; width: 100%; }
    .cal-header { text-align: center; font-weight: bold; padding: 5px 0; font-size: 16px; }
    .cal-cell {
        background-color: #f9f9f9; border: 1px solid #eee; min-height: 70px;
        padding: 4px; text-align: center; font-size: 15px; border-radius: 8px;
    }
    .today { border: 2px solid #ff4b4b !important; background-color: #fff0f0 !important; }
    .b-badge {
        display: block; background-color: #e6f3ff; color: #0068c9;
        font-size: 12px; border-radius: 4px; padding: 2px; margin-top: 4px;
        word-break: keep-all; line-height: 1.2; font-weight: bold;
    }
    .lunar-badge {
        display: block; background-color: #f3e5f5; color: #7b1fa2;
        font-size: 12px; border-radius: 4px; padding: 2px; margin-top: 4px;
        word-break: keep-all; line-height: 1.2; font-weight: bold;
    }
    @media only screen and (max-width: 600px) {
        h1 { font-size: 28px !important; margin-bottom: 15px !important; }
        .cal-header { font-size: 14px; }
        .cal-cell { min-height: 55px; font-size: 13px; padding: 2px; }
        .b-badge, .lunar-badge { font-size: 11px; margin-top: 2px; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. 구글 시트 연결 ---
@st.cache_resource
def get_google_sheet_client():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"구글 연결 설정 오류: Secrets를 확인해주세요. ({e})")
        return None

def get_worksheet(worksheet_name):
    client = get_google_sheet_client()
    if not client: return None
    try:
        sheet = client.open(SHEET_NAME)
        try:
            return sheet.worksheet(worksheet_name)
        except:
            return sheet.add_worksheet(title=worksheet_name, rows=100, cols=20)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"오류: 구글 시트 '{SHEET_NAME}'을 찾을 수 없습니다.")
        return None
    except gspread.exceptions.APIError:
        st.error("⚠️ 접속량이 많아 일시적으로 지연됩니다. 잠시 후 다시 시도해주세요.")
        return None

# --- 2. 데이터 관리 ---
@st.cache_data(ttl=60)
def load_data(sheet_name):
    ws = get_worksheet(sheet_name)
    if not ws: return pd.DataFrame()
    data = ws.get_all_records()
    if not data:
        if sheet_name == "members":
            return pd.DataFrame(columns=["이름", "성별", "생일", "전화번호", "주소", "가족ID", "소그룹", "비고", "음력"])
        elif sheet_name == "attendance_log":
            return pd.DataFrame(columns=["날짜", "모임명", "이름", "소그룹", "출석여부"])
        elif sheet_name == "users":
            return pd.DataFrame(columns=["아이디", "비밀번호", "이름", "역할", "담당소그룹"])
        elif sheet_name == "prayer_log":
            return pd.DataFrame(columns=["날짜", "이름", "소그룹", "내용", "작성자"])
        elif sheet_name == "notices":
            return pd.DataFrame(columns=["날짜", "내용", "작성자"])
        elif sheet_name == "reports":
            # [수정] 답변 및 추가피드백 컬럼 추가
            return pd.DataFrame(columns=["날짜", "작성자", "내용", "답변", "추가피드백"])
    return pd.DataFrame(data).astype(str)

def save_data(sheet_name, df):
    ws = get_worksheet(sheet_name)
    if ws:
        ws.clear()
        ws.append_row(df.columns.tolist())
        ws.update(range_name='A2', values=df.values.tolist())
        load_data.clear()

# --- 3. 헬퍼 함수 ---
def get_week_range(date_obj):
    idx = (date_obj.weekday() + 1) % 7 
    start_sunday = date_obj - datetime.timedelta(days=idx)
    end_saturday = start_sunday + datetime.timedelta(days=6)
    return start_sunday, end_saturday

def get_day_name(date_obj):
    days = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
    return days[date_obj.weekday()]

def get_target_columns(weekday_idx, group_name):
    if weekday_idx != 6:
        return MEETING_CONFIG.get(weekday_idx, [])
    if group_name == "전체 보기": return SUNDAY_ALL
    g_name = str(group_name)
    if "중고등" in g_name: return COLS_YOUTH
    elif "청년" in g_name: return COLS_YOUNG
    elif "주일학교" in g_name or "유초등" in g_name or "유치부" in g_name: return COLS_KIDS
    else: return COLS_ADULT

# [음력/양력 완벽 변환 생일 달력 로직 v8.2]
def draw_birthday_calendar(df_members):
    today = datetime.date.today()
    month = today.month
    year = today.year
    birthdays = {}
    
    calendar_converter = KoreanLunarCalendar()

    if not df_members.empty:
        cols_cleaned = [str(c).strip() for c in df_members.columns]
        lunar_col_name = None
        if "음력" in cols_cleaned:
            lunar_col_name = df_members.columns[cols_cleaned.index("음력")]

        for _, row in df_members.iterrows():
            try:
                raw_birth = str(row["생일"])
                parts = re.findall(r'\d+', raw_birth)
                b_month_origin = 0
                b_day_origin = 0

                if len(parts) >= 3:
                    b_month_origin = int(parts[1])
                    b_day_origin = int(parts[2])
                elif len(parts) == 2:
                    b_month_origin = int(parts[0])
                    b_day_origin = int(parts[1])
                
                if b_month_origin == 0 or b_day_origin == 0: continue

                is_lunar = False
                if lunar_col_name:
                    val = str(row[lunar_col_name]).strip().upper()
                    if val in ["O", "0", "ㅇ", "YES", "TRUE", "Y"]:
                        is_lunar = True

                if is_lunar:
                    check_years = [year - 1, year, year + 1]
                    for check_year in check_years:
                        try:
                            calendar_converter.setLunarDate(check_year, b_month_origin, b_day_origin, False)
                            s_year = calendar_converter.solarYear
                            s_month = calendar_converter.solarMonth
                            s_day = calendar_converter.solarDay
                            
                            if s_year == year and s_month == month:
                                display_name = f"{row['이름']}(음)"
                                if str(s_day) not in birthdays: birthdays[str(s_day)] = []
                                if not any(p['name'] == display_name for p in birthdays[str(s_day)]):
                                    birthdays[str(s_day)].append({"name": display_name, "style": "lunar-badge"})
                        except: continue 
                else:
                    if b_month_origin == month:
                        display_name = f"{row['이름']}"
                        if str(b_day_origin) not in birthdays: birthdays[str(b_day_origin)] = []
                        birthdays[str(b_day_origin)].append({"name": display_name, "style": "b-badge"})

            except: continue

    st.markdown(f"### 📅 {year}년 {month}월 생일 달력")
    html_code = '<div class="calendar-container">'
    weeks = ["일", "월", "화", "수", "목", "금", "토"]
    for i, w in enumerate(weeks):
        color = "red" if i==0 else "blue" if i==6 else "#333"
        html_code += f'<div class="cal-header" style="color: {color};">{w}</div>'
    
    calendar.setfirstweekday(6) 
    cal = calendar.monthcalendar(year, month)
    
    for week in cal:
        for day in week:
            if day == 0: html_code += '<div class="cal-cell" style="border:none;"></div>'
            else:
                is_today = "today" if (day == today.day and month == today.month and year == today.year) else ""
                style = "color: red;" if (day == today.day and month == today.month and year == today.year) else ""
                html_code += f'<div class="cal-cell {is_today}"><div style="{style} font-weight:bold;">{day}</div>'
                if str(day) in birthdays:
                    for person in birthdays[str(day)]:
                        html_code += f'<span class="{person["style"]}">🎂{person["name"]}</span>'
                html_code += '</div>'
    html_code += '</div>'
    st.markdown(html_code, unsafe_allow_html=True)

def draw_manual_tab():
    st.markdown("""
    ### 📘 회정교회 출석체크 시스템 가이드 v9.0
    
    **1. ⚠️ 주의사항**
    * 작업 중에 **새로고침(F5)**을 하면 로그인이 풀립니다.
    
    ---
    **2. 📨 사역 보고 (New!)**
    * **소그룹장:** 사역 내용을 작성하고, 관리자의 답변을 확인한 뒤 '추가피드백'을 남길 수 있습니다.
    * **관리자:** 올라온 보고에 대해 '답변' 칸에 피드백을 적고 저장할 수 있습니다.
    
    ---
    **3. 👥 명단 관리**
    * **음력 생일:** '음력' 칸에 **O** 입력 시 달력에 양력 변환 날짜로 표시됩니다.
    """)

def draw_notice_section(is_admin, current_user_name):
    df_notices = load_data("notices")
    if not df_notices.empty:
        latest = df_notices.sort_values(by="날짜", ascending=False).iloc[0]
        st.markdown(f"""<div class="notice-box">📢 <b>공지사항 ({latest['날짜']})</b><br><br>{latest['내용']}</div>""", unsafe_allow_html=True)
    else:
        if is_admin: st.info("등록된 공지사항이 없습니다.")

    if is_admin:
        with st.expander("📢 공지사항 등록 (관리자)"):
            with st.form("notice_form"):
                n_date = st.date_input("날짜", datetime.date.today())
                n_content = st.text_area("내용", height=100)
                if st.form_submit_button("등록"):
                    new_n = pd.DataFrame([{"날짜": str(n_date), "내용": n_content, "작성자": current_user_name}])
                    save_data("notices", pd.concat([df_notices, new_n], ignore_index=True))
                    st.success("등록됨"); st.rerun()

# 로그인 관련
def process_login(username, password, cookie_manager):
    df_users = load_data("users")
    matched = df_users[(df_users["아이디"] == username) & (df_users["비밀번호"] == password)]
    if not matched.empty:
        st.session_state["logged_in"] = True
        st.session_state["user_info"] = matched.iloc[0].to_dict()
        exp = datetime.datetime.now() + datetime.timedelta(days=30)
        cookie_manager.set("church_user_id", username, expires_at=exp)
        st.rerun()
    else: st.error("정보 불일치")

def process_logout(cookie_manager):
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None
    try: cookie_manager.delete("church_user_id")
    except: pass
    st.rerun()

# --- 4. 메인 앱 ---
def main():
    cookie_manager = stx.CookieManager(key="church_cookies")
    
    st.title("⛪ 회정교회 출석체크 시스템 v9.0")

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user_info"] = None

    if not st.session_state["logged_in"]:
        time.sleep(0.5)
        cookie_id = cookie_manager.get(cookie="church_user_id")
        if cookie_id:
            df_users = load_data("users")
            match = df_users[df_users["아이디"] == cookie_id]
            if not match.empty:
                st.session_state["logged_in"] = True
                st.session_state["user_info"] = match.iloc[0].to_dict()
                st.rerun()

    with st.sidebar:
        st.header("로그인")
        if not st.session_state["logged_in"]:
            uid = st.text_input("아이디", key="lid")
            upw = st.text_input("비밀번호", type="password", key="lpw")
            if st.button("로그인"): process_login(uid, upw, cookie_manager)
            st.caption("초기: admin / 1234")
        else:
            u = st.session_state["user_info"]
            st.success(f"{u['이름']}님 환영합니다")
            st.caption(f"권한: {u['역할']}")
            if st.button("로그아웃"): process_logout(cookie_manager)

    if not st.session_state["logged_in"]:
        st.warning("👈 로그인해주세요."); st.stop()

    current_user = st.session_state["user_info"]
    current_user_name = current_user["이름"]
    is_admin = (current_user["역할"] == "admin")
    
    df_members = load_data("members")
    df_att = load_data("attendance_log")
    df_prayer = load_data("prayer_log")
    df_reports = load_data("reports")

    menu = ["🏠 홈", "📖 사용설명서", "📋 출석체크", "📊 통계", "🙏 기도제목", "📨 사역 보고", "👥 명단 관리"]
    if is_admin: menu.append("🔐 계정 관리")
    
    sel_menu = st.radio("메뉴", menu, horizontal=True, label_visibility="collapsed")
    st.divider()

    # --- 1. 홈 ---
    if sel_menu == "🏠 홈":
        draw_notice_section(is_admin, current_user_name)
        st.subheader("이번 달 주요 일정")
        if st.button("🔄 일정 새로고침 (데이터가 안 보이면 누르세요)"):
            st.cache_data.clear()
            st.rerun()
        draw_birthday_calendar(df_members)

    # --- 2. 사용설명서 ---
    elif sel_menu == "📖 사용설명서":
        draw_manual_tab()

    # --- 3. 출석체크 ---
    elif sel_menu == "📋 출석체크":
        st.subheader("📋 요일별 맞춤 출석체크")
        
        c1, c2 = st.columns(2)
        chk_date = c1.date_input("날짜 선택", datetime.date.today())
        weekday_idx = chk_date.weekday()
        days_kor = ["월", "화", "수", "목", "금", "토", "일"]
        day_str = days_kor[weekday_idx]
        c1.info(f"선택일: {chk_date.strftime('%Y-%m-%d')} ({day_str})")

        all_grps = sorted(df_members["소그룹"].unique())
        if is_admin: grp = c2.selectbox("소그룹(관리자)", ["전체 보기"] + all_grps)
        else:
            my_grps = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
            if len(my_grps) > 1: grp = c2.selectbox("소그룹 선택", my_grps)
            elif len(my_grps) == 1: grp = my_grps[0]; c2.info(f"담당: {grp}")
            else: grp = None

        target_meetings = get_target_columns(weekday_idx, grp)

        if not target_meetings:
            st.warning(f"📌 {day_str}요일에는 예정된 정기 모임이 없습니다.")
        else:
            if grp:
                targets = df_members if grp == "전체 보기" else df_members[df_members["소그룹"] == grp]
            else: targets = pd.DataFrame()

            if not targets.empty:
                current_log = df_att[df_att["날짜"] == str(chk_date)]
                grid_data = []
                for _, member in targets.iterrows():
                    row = {"이름": member["이름"], "소그룹": member["소그룹"]}
                    member_log = current_log[current_log["이름"] == member["이름"]]
                    for col in target_meetings:
                        row[col] = not member_log[member_log["모임명"] == col].empty
                    grid_data.append(row)
                
                df_grid = pd.DataFrame(grid_data)
                
                col_conf = {
                    "이름": st.column_config.TextColumn("이름", disabled=True, pinned=True),
                    "소그룹": st.column_config.TextColumn("소그룹", disabled=True)
                }
                for col in target_meetings:
                    col_conf[col] = st.column_config.CheckboxColumn(col, default=False)

                st.success(f"📌 {grp} / {', '.join(target_meetings)} 출석을 체크합니다.")
                edited_df = st.data_editor(df_grid, column_config=col_conf, hide_index=True, use_container_width=True)

                if st.button("✅ 출석 저장하기", use_container_width=True):
                    mask_date = df_att["날짜"] == str(chk_date)
                    mask_grp = df_att["소그룹"] == grp if grp != "전체 보기" else True
                    mask_meeting = df_att["모임명"].isin(target_meetings)
                    df_clean = df_att[~(mask_date & mask_grp & mask_meeting)]
                    new_records = []
                    for _, row in edited_df.iterrows():
                        name = row["이름"]
                        u_grp = row["소그룹"]
                        for col in target_meetings:
                            if row[col]:
                                new_records.append({
                                    "날짜": str(chk_date), "모임명": col, "이름": name, "소그룹": u_grp, "출석여부": "출석"
                                })
                    final_df = pd.concat([df_clean, pd.DataFrame(new_records)], ignore_index=True)
                    save_data("attendance_log", final_df)
                    st.success(f"✅ {chk_date} ({day_str}) 출석 저장 완료!"); st.rerun()

    # --- 4. 통계 ---
    elif sel_menu == "📊 통계":
        st.subheader("📊 출석 누적 현황 및 상세 조회")
        if df_att.empty: st.info("데이터가 없습니다.")
        else:
            df_stat = df_att.copy()
            df_stat["날짜"] = pd.to_datetime(df_stat["날짜"], errors='coerce')
            
            c1, c2 = st.columns([2, 1])
            today = datetime.date.today()
            start_of_year = datetime.date(today.year, 1, 1)
            date_range = c1.date_input("📅 조회 기간", (start_of_year, today), format="YYYY/MM/DD")
            
            if len(date_range) == 2:
                start_d, end_d = date_range
                if is_admin:
                    all_g = sorted(df_att["소그룹"].unique())
                    s_grp = c2.selectbox("그룹 선택", ["전체 보기"] + all_g)
                else:
                    my_grps = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
                    if len(my_grps) > 1: s_grp = c2.selectbox("그룹 선택", my_grps)
                    else: s_grp = my_grps[0]; c2.info(f"담당: {s_grp}")

                mask = (df_stat["날짜"] >= pd.Timestamp(start_d)) & (df_stat["날짜"] <= pd.Timestamp(end_d))
                w_df = df_stat[mask]
                if s_grp != "전체 보기": w_df = w_df[w_df["소그룹"] == s_grp]

                if w_df.empty: st.warning("해당 기간에 출석 기록이 없습니다.")
                else:
                    st.divider()
                    st.markdown(f"##### 📈 {s_grp} 출석 누적 현황표")
                    pivot_table = pd.crosstab(w_df["이름"], w_df["모임명"])
                    for m_type in ALL_MEETINGS_ORDERED:
                        if m_type not in pivot_table.columns: pivot_table[m_type] = 0
                    pivot_table = pivot_table[[c for c in ALL_MEETINGS_ORDERED if c in pivot_table.columns]]
                    st.dataframe(pivot_table, use_container_width=True)
                    
                    st.divider()
                    st.markdown("##### 🔍 개인별 상세 출석 수정")
                    if not pivot_table.empty:
                        name_list = sorted(pivot_table.index.tolist())
                        selected_name = st.selectbox("수정할 이름 선택", name_list)
                        if selected_name:
                            person_log = w_df[w_df["이름"] == selected_name].sort_values(by="날짜", ascending=False)
                            person_log["날짜"] = person_log["날짜"].apply(lambda x: f"{x.strftime('%Y-%m-%d')} {get_day_name(x)}")
                            
                            st.info(f"💡 {selected_name}님의 기록을 수정/추가할 수 있습니다.")
                            edit_target = person_log[["날짜", "모임명", "소그룹"]]
                            edited_log = st.data_editor(edit_target, num_rows="dynamic", use_container_width=True, key="stat_editor")
                            
                            if st.button("💾 수정사항 저장하기", use_container_width=True):
                                df_rest = df_att[df_att["이름"] != selected_name]
                                new_person_data = []
                                for _, row in edited_log.iterrows():
                                    if row["날짜"] and row["모임명"]:
                                        clean_date = row["날짜"].split(" ")[0]
                                        new_person_data.append({
                                            "날짜": clean_date, "모임명": row["모임명"],
                                            "이름": selected_name, "소그룹": row["소그룹"],
                                            "출석여부": "출석"
                                        })
                                final_df = pd.concat([df_rest, pd.DataFrame(new_person_data)], ignore_index=True)
                                save_data("attendance_log", final_df)
                                st.success(f"✅ {selected_name}님의 기록 업데이트 완료!"); st.rerun()

    # --- 5. 기도제목 ---
    elif sel_menu == "🙏 기도제목":
        st.subheader("기도제목 관리")
        if is_admin:
            st.markdown("### 🗓️ 주간 전체 기도제목 모아보기")
            c1, c2 = st.columns([1, 2])
            p_date = c1.date_input("조회 기준 날짜", datetime.date.today(), key="p_date_adm")
            sun, sat = get_week_range(p_date)
            c2.caption(f"📅 조회 기간: {sun.strftime('%Y-%m-%d')} ~ {sat.strftime('%Y-%m-%d')}")
            
            df_prayer_stat = df_prayer.copy()
            df_prayer_stat["날짜"] = pd.to_datetime(df_prayer_stat["날짜"], errors='coerce')
            mask = (df_prayer_stat["날짜"] >= pd.Timestamp(sun)) & (df_prayer_stat["날짜"] <= pd.Timestamp(sat))
            weekly_prayers = df_prayer[mask].sort_values(by=["소그룹", "이름"])
            
            if weekly_prayers.empty: st.info("해당 주간에 등록된 기도제목이 없습니다.")
            else: st.dataframe(weekly_prayers[["날짜", "소그룹", "이름", "내용"]], use_container_width=True, hide_index=True)
        else:
            all_g = sorted(df_members["소그룹"].unique())
            my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
            if len(my_gs)>1: p_grp = st.selectbox("그룹", my_gs)
            elif len(my_gs)==1: p_grp = my_gs[0]
            else: p_grp = None
            if p_grp:
                mems = df_members[df_members["소그룹"]==p_grp]["이름"].tolist()
                p_who = st.selectbox("이름", mems)
                with st.expander("새 기도제목 입력"):
                    with st.form("p_form"):
                        pd_in = st.date_input("날짜", datetime.date.today())
                        pc_in = st.text_area("내용")
                        if st.form_submit_button("저장"):
                            new_p = pd.DataFrame([{"날짜":str(pd_in), "이름":p_who, "소그룹":p_grp, "내용":pc_in, "작성자":current_user_name}])
                            save_data("prayer_log", pd.concat([df_prayer, new_p], ignore_index=True))
                            st.success("저장됨"); st.rerun()
                st.divider()
                st.caption(f"{p_who}님의 히스토리")
                hist = df_prayer[df_prayer["이름"]==p_who].sort_values("날짜", ascending=False)
                for i, r in hist.iterrows():
                    st.info(f"**{r['날짜']}**: {r['내용']}")

    # --- 6. 사역 보고 (쌍방 소통 기능 업데이트) ---
    elif sel_menu == "📨 사역 보고":
        st.subheader("📨 소그룹 사역 보고 (쌍방 소통)")
        
        # 데이터프레임에 새 컬럼(답변, 추가피드백)이 없으면 안전하게 추가
        if "답변" not in df_reports.columns: df_reports["답변"] = ""
        if "추가피드백" not in df_reports.columns: df_reports["추가피드백"] = ""

        if is_admin:
            st.markdown("### 📥 관리자 모드: 보고서 확인 및 답변 작성")
            c1, c2 = st.columns([1, 2])
            r_date_adm = c1.date_input("조회 기준 날짜", datetime.date.today(), key="r_date_adm")
            sun, sat = get_week_range(r_date_adm)
            c2.caption(f"📅 조회 기간: {sun.strftime('%Y-%m-%d')} ~ {sat.strftime('%Y-%m-%d')}")
            
            # 날짜 필터링
            df_rep_stat = df_reports.copy()
            df_rep_stat["날짜"] = pd.to_datetime(df_rep_stat["날짜"], errors='coerce')
            mask = (df_rep_stat["날짜"] >= pd.Timestamp(sun)) & (df_rep_stat["날짜"] <= pd.Timestamp(sat))
            weekly_reports = df_reports[mask].sort_values(by="날짜", ascending=False)
            
            if weekly_reports.empty:
                st.info("해당 주간에 제출된 보고서가 없습니다.")
            else:
                st.info("💡 팁: '답변' 칸을 클릭하여 피드백을 작성한 후 하단 [저장하기] 버튼을 눌러주세요.")
                
                # 관리자용 컬럼 설정 (답변만 수정 가능)
                col_config = {
                    "날짜": st.column_config.TextColumn(disabled=True),
                    "작성자": st.column_config.TextColumn(disabled=True),
                    "내용": st.column_config.TextColumn("보고 내용", disabled=True, width="medium"),
                    "답변": st.column_config.TextColumn("관리자 답변 (작성가능)", disabled=False, width="medium"),
                    "추가피드백": st.column_config.TextColumn("소그룹장 피드백", disabled=True, width="medium")
                }
                
                # 데이터 에디터로 보여주기
                edited_reports = st.data_editor(
                    weekly_reports, 
                    column_config=col_config, 
                    use_container_width=True, 
                    hide_index=True,
                    num_rows="fixed"
                )
                
                if st.button("💾 관리자 답변 저장하기"):
                    # 전체 데이터에서 해당 주간 데이터만 교체하는 방식
                    # (간단하게 구현하기 위해: 날짜+작성자+내용이 키라고 가정하거나, 그냥 전체 덮어쓰기 로직 사용)
                    # 여기서는 안전하게: 수정된 edited_reports 내용을 원본 df_reports에 업데이트
                    
                    # 1. 수정된 내용 리스트로 변환
                    for i, row in edited_reports.iterrows():
                        # 원본 데이터프레임에서 날짜, 작성자, 내용이 일치하는 행을 찾아 답변 업데이트
                        # (단, 중복 내용이 있을 수 있으니 인덱스 매칭이 제일 정확하지만 필터링된 뷰라 인덱스가 다를 수 있음)
                        # 가장 확실한 방법: 전체 데이터를 다시 저장하되, 현재 수정된 부분만 반영
                        # 여기서는 간단히: 필터링된 것 외의 데이터 + 수정된 데이터 합치기
                        pass

                    # 필터링되지 않은 나머지 데이터
                    df_others = df_reports[~mask]
                    # 합치기
                    df_final = pd.concat([df_others, edited_reports], ignore_index=True)
                    # 날짜순 정렬
                    df_final["날짜_dt"] = pd.to_datetime(df_final["날짜"], errors='coerce')
                    df_final = df_final.sort_values(by="날짜_dt", ascending=False).drop(columns=["날짜_dt"])
                    
                    save_data("reports", df_final)
                    st.success("✅ 답변이 저장되었습니다!"); st.rerun()

        else:
            # --- 소그룹장 모드 ---
            st.markdown(f"### 📂 {current_user_name}님의 보고서 및 피드백")
            
            # 1. 새 보고서 작성
            with st.expander("📝 새 보고서 작성하기"):
                with st.form("report_form"):
                    r_date = st.date_input("작성일", datetime.date.today())
                    r_content = st.text_area("내용", height=100)
                    if st.form_submit_button("제출"):
                        new_r = pd.DataFrame([{
                            "날짜": str(r_date), 
                            "작성자": current_user_name, 
                            "내용": r_content, 
                            "답변": "", 
                            "추가피드백": ""
                        }])
                        save_data("reports", pd.concat([df_reports, new_r], ignore_index=True))
                        st.success("제출 완료"); st.rerun()
            
            st.divider()
            
            # 2. 내 보고서 목록 (답변 확인 및 추가 피드백 작성)
            my_reports = df_reports[df_reports["작성자"] == current_user_name].copy()
            if my_reports.empty:
                st.info("제출한 보고서가 없습니다.")
            else:
                st.info("💡 관리자가 답변을 달면 '추가피드백'을 작성할 수 있습니다.")
                # 최신순 정렬
                my_reports["날짜_dt"] = pd.to_datetime(my_reports["날짜"], errors='coerce')
                my_reports = my_reports.sort_values(by="날짜_dt", ascending=False).drop(columns=["날짜_dt"])
                
                # 소그룹장용 컬럼 설정 (추가피드백만 수정 가능)
                col_config_user = {
                    "날짜": st.column_config.TextColumn(disabled=True),
                    "작성자": st.column_config.TextColumn(disabled=True),
                    "내용": st.column_config.TextColumn(disabled=True, width="medium"),
                    "답변": st.column_config.TextColumn("관리자 답변", disabled=True, width="medium"),
                    "추가피드백": st.column_config.TextColumn("추가피드백 (작성가능)", disabled=False, width="medium")
                }
                
                edited_my_reports = st.data_editor(
                    my_reports,
                    column_config=col_config_user,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed"
                )
                
                if st.button("💾 추가피드백 저장"):
                    # 내 보고서가 아닌 다른 사람들의 보고서
                    others_reports = df_reports[df_reports["작성자"] != current_user_name]
                    # 합치기
                    df_final_user = pd.concat([others_reports, edited_my_reports], ignore_index=True)
                    
                    save_data("reports", df_final_user)
                    st.success("✅ 피드백이 저장되었습니다!"); st.rerun()

    # --- 7. 명단 관리 ---
    elif sel_menu == "👥 명단 관리":
        st.subheader("명단 관리")
        if is_admin: target = df_members
        else:
            my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
            target = df_members[df_members["소그룹"].isin(my_gs)]
            st.info(f"담당: {', '.join(my_gs)}")

        sort_option = st.radio(
            "정렬 기준 선택", 
            ["👨‍👩‍👧‍👦 가족끼리(기본)", "🔤 이름순", "🏘️ 소그룹순", "🎂 생일순"], 
            horizontal=True
        )

        if not target.empty:
            target = target.copy()
            if sort_option == "👨‍👩‍👧‍👦 가족끼리(기본)":
                target["가족ID_정렬"] = pd.to_numeric(target["가족ID"], errors='coerce').fillna(99999)
                target = target.sort_values(by=["가족ID_정렬", "이름"])
                del target["가족ID_정렬"]
            elif sort_option == "🔤 이름순":
                target = target.sort_values(by="이름")
            elif sort_option == "🏘️ 소그룹순":
                target = target.sort_values(by=["소그룹", "이름"])
            elif sort_option == "🎂 생일순":
                target = target.sort_values(by="생일")

        col_conf_mem = {
            "이름": st.column_config.TextColumn(pinned=True)
        }
        edited = st.data_editor(target, num_rows="dynamic", use_container_width=True, column_config=col_conf_mem)
        
        if st.button("저장"):
            if is_admin: save_data("members", edited)
            else:
                my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
                mask = df_members["소그룹"].isin(my_gs)
                others = df_members[~mask]
                save_data("members", pd.concat([others, edited], ignore_index=True))
            st.success("저장 완료!"); st.rerun()

    # --- 8. 계정 관리 ---
    elif sel_menu == "🔐 계정 관리" and is_admin:
        st.subheader("계정 관리")
        e_users = st.data_editor(load_data("users"), num_rows="dynamic", use_container_width=True)
        if st.button("저장"): save_data("users", e_users); st.success("완료"); st.rerun()

if __name__ == "__main__":
    main()
