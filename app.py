import streamlit as st
import pandas as pd
import datetime
import calendar
import time
import gspread
import extra_streamlit_components as stx
from oauth2client.service_account import ServiceAccountCredentials

# --- [설정] 구글 시트 파일 이름 ---
SHEET_NAME = "교회출석데이터"

# 페이지 기본 설정
st.set_page_config(page_title="회정교회", layout="wide", initial_sidebar_state="collapsed")

# --- [스타일] CSS Grid 적용 (달력 강제 고정) ---
st.markdown("""
    <style>
    /* 기본 폰트 설정 */
    html, body, p, li, .stMarkdown { font-size: 18px !important; }
    
    /* 제목 스타일: 단어 단위 줄바꿈 + 중앙 정렬 */
    h1 { 
        font-size: 32px !important; 
        text-align: center; 
        word-break: keep-all; /* 단어 중간에 잘리지 않음 */
        margin-bottom: 20px !important;
    }
    
    /* 체크박스, 버튼 등 UI 크기 조절 */
    .stCheckbox label p { font-size: 20px !important; font-weight: bold; }
    .stButton button { font-size: 20px !important; font-weight: bold; width: 100%; }
    
    /* === [핵심] 달력 전용 CSS Grid 스타일 === */
    .calendar-container {
        display: grid;
        grid-template-columns: repeat(7, 1fr); /* 무조건 7등분 (반응형) */
        gap: 2px; /* 칸 사이 간격 */
        margin-top: 10px;
        width: 100%;
    }
    
    /* 요일 헤더 */
    .cal-header {
        text-align: center;
        font-weight: bold;
        padding: 5px 0;
        font-size: 16px;
    }
    
    /* 날짜 칸 */
    .cal-cell {
        background-color: #f9f9f9;
        border: 1px solid #eee;
        min-height: 60px; /* 최소 높이 확보 */
        padding: 2px;
        text-align: center;
        font-size: 14px;
        border-radius: 5px;
    }
    
    /* 오늘 날짜 강조 */
    .today {
        border: 2px solid #ff4b4b !important;
        background-color: #fff0f0 !important;
    }
    
    /* 생일 뱃지 */
    .b-badge {
        display: block;
        background-color: #e6f3ff;
        color: #0068c9;
        font-size: 11px;
        border-radius: 4px;
        padding: 2px;
        margin-top: 2px;
        word-break: keep-all;
        line-height: 1.1;
    }

    /* 모바일 미디어 쿼리 (화면이 좁을 때 미세 조정) */
    @media only screen and (max-width: 600px) {
        .cal-header { font-size: 14px; }
        .cal-cell { min-height: 50px; font-size: 12px; }
        .b-badge { font-size: 10px; }
        h1 { font-size: 26px !important; } /* 제목 더 작게 */
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. 구글 시트 연결 함수 ---
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

# --- 2. 데이터 읽기/쓰기 함수 ---
@st.cache_data(ttl=60)
def load_data(sheet_name):
    ws = get_worksheet(sheet_name)
    if not ws: return pd.DataFrame()
    data = ws.get_all_records()
    if not data:
        if sheet_name == "members":
            return pd.DataFrame(columns=["이름", "성별", "생일", "전화번호", "주소", "가족ID", "소그룹", "비고"])
        elif sheet_name == "attendance_log":
            return pd.DataFrame(columns=["날짜", "모임명", "이름", "소그룹", "출석여부"])
        elif sheet_name == "users":
            return pd.DataFrame(columns=["아이디", "비밀번호", "이름", "역할", "담당소그룹"])
        elif sheet_name == "prayer_log":
            return pd.DataFrame(columns=["날짜", "이름", "소그룹", "내용", "작성자"])
    return pd.DataFrame(data).astype(str)

def save_data(sheet_name, df):
    ws = get_worksheet(sheet_name)
    if ws:
        ws.clear()
        ws.append_row(df.columns.tolist())
        ws.update(range_name='A2', values=df.values.tolist())
        load_data.clear()

# --- 3. 헬퍼 함수들 ---
def get_week_range(date_obj):
    idx = (date_obj.weekday() + 1) % 7
    start_sunday = date_obj - datetime.timedelta(days=idx)
    end_saturday = start_sunday + datetime.timedelta(days=6)
    return start_sunday, end_saturday

# [핵심 수정] HTML/CSS Grid로 달력 그리기 (절대 깨지지 않음)
def draw_birthday_calendar(df_members):
    today = datetime.date.today()
    month = today.month
    year = today.year
    
    # 생일 데이터 가공
    birthdays = {}
    if not df_members.empty:
        for _, row in df_members.iterrows():
            try:
                raw_birth = str(row["생일"]).replace(".", "-").replace("/", "-")
                parts = raw_birth.split("-")
                if len(parts) >= 2:
                    b_month = int(parts[-2])
                    b_day = int(parts[-1])
                    if b_month == month:
                        if str(b_day) not in birthdays: birthdays[str(b_day)] = []
                        birthdays[str(b_day)].append(f"{row['이름']}")
            except: continue

    st.markdown(f"### 📅 {month}월 생일 달력")

    # HTML 문자열 생성 시작
    html_code = '<div class="calendar-container">'
    
    # 1. 요일 헤더
    weeks = ["일", "월", "화", "수", "목", "금", "토"]
    for i, w in enumerate(weeks):
        color = "red" if i==0 else "blue" if i==6 else "#333"
        html_code += f'<div class="cal-header" style="color: {color};">{w}</div>'

    # 2. 날짜 채우기
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        for day in week:
            if day == 0:
                html_code += '<div class="cal-cell" style="background:transparent; border:none;"></div>'
            else:
                is_today = "today" if day == today.day else ""
                day_style = "color: red;" if day == today.day else ""
                
                html_code += f'<div class="cal-cell {is_today}">'
                html_code += f'<div style="{day_style} font-weight:bold;">{day}</div>'
                
                # 생일자 뱃지 추가
                if str(day) in birthdays:
                    for p in birthdays[str(day)]:
                        html_code += f'<span class="b-badge">🎂{p}</span>'
                
                html_code += '</div>'

    html_code += '</div>' # 컨테이너 닫기
    
    # Streamlit에 HTML 렌더링
    st.markdown(html_code, unsafe_allow_html=True)

# 로그인 함수
def process_login(username, password, cookie_manager):
    df_users = load_data("users")
    matched = df_users[(df_users["아이디"] == username) & (df_users["비밀번호"] == password)]
    
    if not matched.empty:
        st.session_state["logged_in"] = True
        st.session_state["user_info"] = matched.iloc[0].to_dict()
        expires = datetime.datetime.now() + datetime.timedelta(days=30)
        cookie_manager.set("church_user_id", username, expires_at=expires)
        st.rerun()
    else:
        st.error("아이디 또는 비밀번호가 잘못되었습니다.")

def process_logout(cookie_manager):
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None
    cookie_manager.delete("church_user_id")
    st.rerun()

# --- 4. 메인 앱 실행 ---
def main():
    cookie_manager = stx.CookieManager(key="church_cookies")
    
    # 안전장치 초기화
    df_stat = pd.DataFrame()
    target = pd.DataFrame()
    t_list = pd.DataFrame()
    w_df = pd.DataFrame()

    st.title("회정교회 출석체크 시스템")

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user_info"] = None

    # 자동 로그인
    if not st.session_state["logged_in"]:
        time.sleep(0.5)
        cookie_id = cookie_manager.get(cookie="church_user_id")
        if cookie_id:
            df_users = load_data("users")
            user_match = df_users[df_users["아이디"] == cookie_id]
            if not user_match.empty:
                st.session_state["logged_in"] = True
                st.session_state["user_info"] = user_match.iloc[0].to_dict()
                st.rerun()

    # 사이드바
    with st.sidebar:
        st.header("로그인")
        if not st.session_state["logged_in"]:
            input_id = st.text_input("아이디", key="login_id")
            input_pw = st.text_input("비밀번호", type="password", key="login_pw")
            if st.button("로그인", key="login_btn"):
                process_login(input_id, input_pw, cookie_manager)
            st.caption("초기: admin / 1234")
        else:
            u_info = st.session_state["user_info"]
            st.success(f"환영합니다! {u_info['이름']}님")
            st.caption(f"권한: {u_info['역할']}")
            if st.button("로그아웃", key="logout_btn"):
                process_logout(cookie_manager)

    if not st.session_state["logged_in"]:
        st.warning("👈 왼쪽 사이드바에서 로그인해주세요.")
        st.stop()

    # 데이터 로드
    current_user = st.session_state["user_info"]
    is_admin = (current_user["역할"] == "admin")
    
    df_members = load_data("members")
    df_att = load_data("attendance_log")
    df_prayer = load_data("prayer_log")

    menu_list = ["🏠 홈", "📋 출석체크", "📊 통계", "🙏 기도제목", "👥 명단 관리"]
    if is_admin: menu_list.append("🔐 계정 관리")
    
    selected_menu = st.radio("메뉴 이동", menu_list, horizontal=True, label_visibility="collapsed", key="main_nav")
    st.divider()

    # --- 탭별 기능 ---

    # 1. 홈
    if selected_menu == "🏠 홈":
        st.subheader("이번 달 주요 일정")
        draw_birthday_calendar(df_members)

    # 2. 출석체크
    elif selected_menu == "📋 출석체크":
        st.subheader("모임 출석 확인")
        c1, c2 = st.columns(2)
        check_date = c1.date_input("날짜", datetime.date.today(), key="att_date")
        
        d_names = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
        day_str = d_names[check_date.weekday()]
        if day_str == "(일)": c1.markdown(f":red[**오늘은 {day_str}요일**]")
        else: c1.caption(f"**{day_str}요일**")

        meetings = ["주일 1부", "주일 2부", "주일 오후", "소그룹 모임", "수요예배", "금요철야", "새벽기도"]
        meeting_name = c2.selectbox("모임", meetings, key="att_meet")

        all_grps = sorted(df_members["소그룹"].unique())
        if is_admin:
            grp = st.selectbox("소그룹(관리자)", ["전체 보기"] + all_grps, key="att_grp_admin")
        else:
            my_grps = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
            if len(my_grps) > 1: grp = st.selectbox("소그룹 선택", my_grps, key="att_grp_ldr")
            elif len(my_grps) == 1: grp = my_grps[0]; st.info(f"담당: {grp}")
            else: grp = None

        if grp:
            targets = df_members if grp == "전체 보기" else df_members[df_members["소그룹"] == grp]
        else: targets = pd.DataFrame()

        if not targets.empty:
            log = df_att[(df_att["날짜"]==str(check_date)) & (df_att["모임명"]==meeting_name)]
            att_ids = log["이름"].tolist()

            with st.form("att_form"):
                st.write(f"**{grp}** 명단 ({len(targets)}명)")
                cols = st.columns(3)
                status = {}
                for i, row in targets.iterrows():
                    name = row["이름"]
                    is_checked = name in att_ids
                    ukey = f"chk_{check_date}_{meeting_name}_{grp}_{name}"
                    status[name] = cols[i%3].checkbox(name, value=is_checked, key=ukey)
                
                if st.form_submit_button("저장하기", use_container_width=True):
                    mask = (df_att["날짜"]==str(check_date)) & (df_att["모임명"]==meeting_name) & (df_att["소그룹"]==grp)
                    df_clean = df_att[~mask]
                    new_rows = []
                    for n, is_on in status.items():
                        if is_on:
                            new_rows.append({"날짜":str(check_date), "모임명":meeting_name, "이름":n, "소그룹":grp, "출석여부":"출석"})
                    final = pd.concat([df_clean, pd.DataFrame(new_rows)], ignore_index=True)
                    save_data("attendance_log", final)
                    st.success("저장 완료!")
                    st.rerun()

    # 3. 통계
    elif selected_menu == "📊 통계":
        st.subheader("📊 주간 사역 통계")
        if df_att.empty: st.info("데이터가 없습니다.")
        else:
            df_stat = df_att.copy()
            df_stat["날짜"] = pd.to_datetime(df_stat["날짜"], errors='coerce')
            
            c1, c2 = st.columns(2)
            s_date = c1.date_input("기준 날짜", datetime.date.today(), key="stat_date")
            sun, sat = get_week_range(s_date)
            c1.caption(f"기간: {sun.strftime('%m/%d')} ~ {sat.strftime('%m/%d')}")

            if is_admin:
                all_g = sorted(df_att["소그룹"].unique())
                s_grp = c2.selectbox("그룹", ["전체 합계"]+all_g, key="stat_grp_adm")
            else:
                my_grps = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
                if len(my_grps) > 1: s_grp = c2.selectbox("그룹", my_grps, key="stat_grp_ldr")
                else: s_grp = my_grps[0]; c2.info(f"담당: {s_grp}")

            mask = (df_stat["날짜"] >= pd.Timestamp(sun)) & (df_stat["날짜"] <= pd.Timestamp(sat))
            w_df = df_stat[mask]
            if s_grp != "전체 합계": w_df = w_df[w_df["소그룹"] == s_grp]

            if w_df.empty: st.warning("해당 기간 기록 없음")
            else:
                cnts = w_df["모임명"].value_counts().reset_index()
                cnts.columns = ["모임명", "인원"]
                st.bar_chart(cnts.set_index("모임명"))
                
                st.divider()
                st.markdown(f"**📋 {s_grp} 명단 현황**")
                
                if s_grp == "전체 합계":
                    if is_admin: t_list = df_members.copy()
                    else:
                        my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
                        t_list = df_members[df_members["소그룹"].isin(my_gs)].copy()
                else:
                    t_list = df_members[df_members["소그룹"] == s_grp].copy()

                if not t_list.empty:
                    view_by_family = st.checkbox("👨‍👩‍👧‍👦 가족별로 묶어보기", key="stat_fam_view")
                    
                    att_names = w_df["이름"].unique()
                    # 정렬: 출석(0)이 위로
                    t_list["정렬키"] = t_list["이름"].apply(lambda x: 0 if x in att_names else 1)
                    t_list["상태"] = t_list["정렬키"].apply(lambda x: "✅ 출석" if x == 0 else "❌ 결석")
                    
                    if view_by_family:
                        t_list = t_list.copy()
                        t_list["가족ID_정렬"] = pd.to_numeric(t_list["가족ID"], errors='coerce').fillna(99999)
                        t_list = t_list.sort_values(by=["가족ID_정렬", "이름"])
                        disp_cols = ["가족ID", "이름", "상태", "소그룹", "전화번호"]
                    else:
                        t_list = t_list.sort_values(by=["정렬키", "이름"], ascending=[True, True])
                        disp_cols = ["이름", "상태", "소그룹", "전화번호"]
                    
                    final_cols = [c for c in disp_cols if c in t_list.columns]
                    
                    def highlight(row):
                        return ['background-color: #ffe6e6' if row['상태']=='❌ 결석' else '' for _ in row]
                    
                    st.dataframe(t_list[final_cols].style.apply(highlight, axis=1), use_container_width=True)

    # 4. 기도제목
    elif selected_menu == "🙏 기도제목":
        st.subheader("기도제목 관리")
        all_g = sorted(df_members["소그룹"].unique())
        if is_admin: p_grp = st.selectbox("그룹", all_g, key="p_g_adm")
        else:
            my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
            if len(my_gs)>1: p_grp = st.selectbox("그룹", my_gs, key="p_g_ldr")
            elif len(my_gs)==1: p_grp = my_gs[0]
            else: p_grp = None
        
        if p_grp:
            mems = df_members[df_members["소그룹"]==p_grp]["이름"].tolist()
            if mems:
                p_who = st.selectbox("이름", mems, key="p_who")
                with st.expander("새 기도제목 입력"):
                    with st.form("p_form"):
                        pd_in = st.date_input("날짜", datetime.date.today(), key="p_d")
                        pc_in = st.text_area("내용", key="p_c")
                        if st.form_submit_button("저장"):
                            new_p = pd.DataFrame([{"날짜":str(pd_in), "이름":p_who, "소그룹":p_grp, "내용":pc_in, "작성자":current_user["이름"]}])
                            save_data("prayer_log", pd.concat([df_prayer, new_p], ignore_index=True))
                            st.success("저장됨")
                            st.rerun()
                
                st.divider()
                st.caption(f"{p_who}님의 히스토리")
                hist = df_prayer[df_prayer["이름"]==p_who].sort_values("날짜", ascending=False)
                for i, r in hist.iterrows():
                    st.info(f"**{r['날짜']}**: {r['내용']}")

    # 5. 명단 관리
    elif selected_menu == "👥 명단 관리":
        st.subheader("명단 관리")
        if is_admin: target = df_members
        else:
            my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
            target = df_members[df_members["소그룹"].isin(my_gs)]
            st.info(f"담당: {', '.join(my_gs)}")

        col_opt1, col_opt2 = st.columns([1, 3])
        use_fam_view = col_opt1.checkbox("👨‍👩‍👧‍👦 가족끼리 묶어보기", value=True, key="mem_fam_chk")
        
        if use_fam_view and not target.empty:
            target = target.copy()
            target["가족ID_정렬"] = pd.to_numeric(target["가족ID"], errors='coerce').fillna(99999)
            target = target.sort_values(by=["가족ID_정렬", "이름"])
            del target["가족ID_정렬"]
            st.caption("💡 '가족ID'가 같으면 묶입니다.")

        edited = st.data_editor(target, num_rows="dynamic", use_container_width=True, key="mem_edit")
        if st.button("저장", key="mem_save"):
            if is_admin: save_data("members", edited)
            else:
                my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
                mask = df_members["소그룹"].isin(my_gs)
                others = df_members[~mask]
                final = pd.concat([others, edited], ignore_index=True)
                save_data("members", final)
            st.success("저장 완료!")
            st.rerun()

    # 6. 계정 관리
    elif selected_menu == "🔐 계정 관리" and is_admin:
        st.subheader("계정 관리")
        u_df = load_data("users")
        e_users = st.data_editor(u_df, num_rows="dynamic", use_container_width=True, key="user_edit")
        if st.button("저장", key="user_save"):
            save_data("users", e_users)
            st.success("완료")
            st.rerun()

if __name__ == "__main__":
    main()
