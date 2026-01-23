import streamlit as st
import pandas as pd
import datetime
import calendar
import time
import gspread
import extra_streamlit_components as stx
from oauth2client.service_account import ServiceAccountCredentials
# import re  <-- 이 부분을 삭제했습니다 (오류 원인 제거)
from korean_lunar_calendar import KoreanLunarCalendar

# --- [설정] 구글 시트 파일 이름 ---
SHEET_NAME = "교회출석데이터"

# --- [설정] 부서별 표시할 모임 정의 ---
COLS_ADULT = ["주일 1부", "주일 2부", "주일 오후", "소그룹 모임"]
COLS_YOUTH = ["중고등부", "주일 1부", "주일 2부", "주일 오후"]
COLS_YOUNG = ["청년부", "주일 1부", "주일 2부", "주일 오후"]
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
st.set_page_config(page_title="회정교회 출석부 v2.2.1", layout="wide", initial_sidebar_state="collapsed")

# --- [스타일] CSS 적용 ---
st.markdown("""
    <style>
    html, body, p, li, .stMarkdown { font-size: 18px !important; }
    h1 { 
        font-size: 46px !important; text-align: center; word-break: keep-all; 
        margin-bottom: 30px !important; font-weight: 800 !important;
    }
    .stButton button { font-size: 20px !important; font-weight: bold; width: 100%; }
    
    /* 공지사항 박스 */
    .notice-box {
        background-color: #fff3cd; border: 2px solid #ffeeba; color: #856404;
        padding: 15px; border-radius: 10px; margin-bottom: 20px;
        text-align: center; font-size: 20px; font-weight: bold; line-height: 1.5; word-break: keep-all;
    }
    
    /* 사역보고 카드 스타일 */
    .report-card {
        background-color: #f8f9fa; border: 1px solid #dee2e6; 
        border-radius: 10px; padding: 20px; margin-bottom: 15px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .report-header { font-size: 16px; color: #6c757d; margin-bottom: 10px; font-weight: bold;}
    .report-content { font-size: 18px; color: #212529; white-space: pre-wrap; line-height: 1.6;}
    .reply-box {
        background-color: #e8f5e9; border-left: 5px solid #4caf50;
        padding: 15px; margin-top: 15px; border-radius: 5px;
    }
    .reply-title { color: #2e7d32; font-weight: bold; font-size: 16px; margin-bottom: 5px; }

    /* 달력 스타일 */
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
    /* 탭 메뉴 설명 박스 */
    .info-tip {
        background-color: #e3f2fd; border-left: 5px solid #2196f3;
        padding: 15px; margin-bottom: 20px; border-radius: 5px; color: #0d47a1;
        font-size: 16px;
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
            return pd.DataFrame(columns=["이름", "성별", "생일", "음력", "전화번호", "주소", "가족ID", "소그룹", "비고"])
        elif sheet_name == "attendance_log":
            return pd.DataFrame(columns=["날짜", "모임명", "이름", "소그룹", "출석여부"])
        elif sheet_name == "users":
            return pd.DataFrame(columns=["아이디", "비밀번호", "이름", "역할", "담당소그룹"])
        elif sheet_name == "prayer_log":
            return pd.DataFrame(columns=["날짜", "이름", "소그룹", "내용", "작성자"])
        elif sheet_name == "notices":
            return pd.DataFrame(columns=["날짜", "내용", "작성자"])
        elif sheet_name == "reports":
            return pd.DataFrame(columns=["날짜", "작성자", "내용", "답변"])
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

# [수정] 안전한 날짜 파싱 함수 (정규표현식 제거)
def extract_date_numbers(date_str):
    # 숫자만 추출해서 리스트로 반환하는 안전한 함수
    nums = []
    current_num = ""
    for char in str(date_str):
        if char.isdigit():
            current_num += char
        else:
            if current_num:
                nums.append(int(current_num))
                current_num = ""
    if current_num:
        nums.append(int(current_num))
    return nums

def draw_birthday_calendar(df_members):
    real_today = datetime.date.today()
    
    if "cal_year" not in st.session_state:
        st.session_state["cal_year"] = real_today.year
    if "cal_month" not in st.session_state:
        st.session_state["cal_month"] = real_today.month

    c_prev, c_title, c_next = st.columns([1, 4, 1])
    
    with c_prev:
        if st.button("◀ 이전"):
            st.session_state["cal_month"] -= 1
            if st.session_state["cal_month"] == 0:
                st.session_state["cal_month"] = 12
                st.session_state["cal_year"] -= 1
            st.rerun()
            
    with c_title:
        st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state['cal_year']}년 {st.session_state['cal_month']}월</h3>", unsafe_allow_html=True)
        
    with c_next:
        if st.button("다음 ▶"):
            st.session_state["cal_month"] += 1
            if st.session_state["cal_month"] == 13:
                st.session_state["cal_month"] = 1
                st.session_state["cal_year"] += 1
            st.rerun()

    year = st.session_state["cal_year"]
    month = st.session_state["cal_month"]
    
    birthdays = {}
    calendar_converter = KoreanLunarCalendar()

    if not df_members.empty:
        cols_cleaned = [str(c).strip() for c in df_members.columns]
        lunar_col_name = None
        if "음력" in cols_cleaned:
            lunar_col_name = df_members.columns[cols_cleaned.index("음력")]

        for _, row in df_members.iterrows():
            try:
                # [수정] 정규표현식 대신 안전한 함수 사용
                parts = extract_date_numbers(row["생일"])
                
                b_month_origin = 0
                b_day_origin = 0

                if len(parts) >= 3:
                    b_month_origin = parts[1]
                    b_day_origin = parts[2]
                elif len(parts) == 2:
                    b_month_origin = parts[0]
                    b_day_origin = parts[1]
                
                if b_month_origin == 0 or b_day_origin == 0: continue

                group_name = str(row.get("소그룹", "")).strip()

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
                                display_name = f"{row['이름']}({group_name})(음)"
                                if str(s_day) not in birthdays: birthdays[str(s_day)] = []
                                if not any(p['name'] == display_name for p in birthdays[str(s_day)]):
                                    birthdays[str(s_day)].append({"name": display_name, "style": "lunar-badge"})
                        except: continue 
                else:
                    if b_month_origin == month:
                        display_name = f"{row['이름']}({group_name})"
                        if str(b_day_origin) not in birthdays: birthdays[str(b_day_origin)] = []
                        birthdays[str(b_day_origin)].append({"name": display_name, "style": "b-badge"})

            except: continue

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
                is_today = "today" if (day == real_today.day and month == real_today.month and year == real_today.year) else ""
                style = "color: red;" if (day == real_today.day and month == real_today.month and year == real_today.year) else ""
                html_code += f'<div class="cal-cell {is_today}"><div style="{style} font-weight:bold;">{day}</div>'
                if str(day) in birthdays:
                    for person in birthdays[str(day)]:
                        html_code += f'<span class="{person["style"]}">🎂{person["name"]}</span>'
                html_code += '</div>'
    html_code += '</div>'
    st.markdown(html_code, unsafe_allow_html=True)

def draw_manual_tab():
    st.markdown("""
    ## 📘 회정교회 출석체크 시스템 사용법 (v2.2.1)
    
    환영합니다! 이 시스템은 소그룹 리더님들이 스마트폰으로 간편하게 사역을 관리하실 수 있도록 만들어졌습니다.
    처음 사용하셔도 괜찮아요. 아래 설명대로 천천히 따라해보세요. 😊
    
    ---
    """)
    
    with st.expander("✅ 1. 출석체크 하는 법 (가장 중요!)", expanded=True):
        st.markdown("""
        1. **메뉴 선택:** 상단 메뉴에서 **[📋 출석체크]**를 눌러주세요.
        2. **날짜 선택:** 오늘 날짜가 자동으로 선택되어 있습니다. (지난 날짜도 선택 가능)
        3. **소그룹 확인:** 본인이 담당한 소그룹 명단이 자동으로 나옵니다.
        4. **체크하기:** * 표의 오른쪽 **체크박스(ㅁ)**를 눌러 출석한 분들을 체크해주세요.
           * 화면을 오른쪽으로 밀어도 **이름은 왼쪽에 고정**되어 있어 헷갈리지 않아요!
        5. **저장 필수:** 체크를 다 하셨다면 표 아래에 있는 **[✅ 출석 저장하기]** 버튼을 꼭! 눌러주세요.
           * *"저장 완료!"* 메시지가 뜨면 성공입니다.
        """)

    with st.expander("📊 2. 지난 출석 확인 및 수정하기"):
        st.markdown("""
        1. **메뉴 선택:** 상단 메뉴에서 **[📊 통계]**를 눌러주세요.
        2. **기간 조회:** 원하는 기간을 설정하면 누가 얼마나 왔는지 한눈에 표로 보여줍니다.
        3. **수정 기능:**
           * 만약 지난주에 실수로 체크를 못 했다면?
           * 표 아래에 있는 **[수정할 이름 선택]** 상자에서 성도님 이름을 찾으세요.
           * 그분의 출석 기록이 나오면 체크박스를 수정하고 **[💾 수정사항 저장하기]**를 누르면 끝!
        """)

    with st.expander("📨 3. 사역 보고서 작성하기"):
        st.markdown("""
        1. **메뉴 선택:** 상단 메뉴에서 **[📨 사역 보고]**를 눌러주세요.
        2. **보고서 쓰기:**
           * **[📝 새 보고서 작성하기]**를 누르면 입력창이 열립니다.
           * 이번 주 모임 내용, 심방 내용, 특이사항 등을 편하게 적어주세요.
           * **[제출]** 버튼을 누르면 목사님께 전달됩니다.
        3. **피드백 확인:**
           * 목사님이 보고서를 읽고 답글을 남기시면, 내 보고서 아래에 **초록색 상자(💌 목회자 피드백)**로 표시됩니다.
        """)

    with st.expander("🎂 4. 생일 및 명단 관리"):
        st.markdown("""
        * **생일 달력:** **[🏠 홈]** 화면에서 이번 달 생일자를 확인하세요. 
           * **[◀ 이전] [다음 ▶]** 버튼을 눌러 지난달이나 다음 달 생일자도 미리 볼 수 있습니다.
        * **명단 수정:** **[👥 명단 관리]** 메뉴에서 전화번호나 주소가 바뀌었을 때 직접 수정하고 저장할 수 있습니다.
        * **음력 생일 등록:** 명단 관리에서 **'음력'** 칸에 알파벳 **O**를 입력하면, 자동으로 양력으로 변환되어 달력에 표시됩니다.
        """)
        
    st.info("💡 사용하시다가 안 되는 부분이 있거나 건의사항이 있으면 언제든 말씀해주세요!")

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

# [수정] 로그아웃 로직: 쿠키 삭제 시간을 벌어주기 위해 대기 시간 추가
def process_logout(cookie_manager):
    # 1. 세션 상태 초기화
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None
    
    # 2. 쿠키 삭제 명령
    try:
        cookie_manager.delete("church_user_id")
    except:
        pass
    
    # 3. [핵심] 브라우저가 쿠키를 지울 시간을 줌 (1초 대기)
    with st.spinner("로그아웃 중입니다..."):
        time.sleep(1)
        
    # 4. 새로고침
    st.rerun()

# --- 4. 메인 앱 ---
def main():
    cookie_manager = stx.CookieManager(key="church_cookies")
    
    st.title("⛪ 회정교회 출석체크 시스템 v2.2.1")

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
        st.markdown('<div class="info-tip">👋 환영합니다! 공지사항과 생일자를 확인해보세요.</div>', unsafe_allow_html=True)
        draw_notice_section(is_admin, current_user_name)
        st.subheader("생일 캘린더")
        draw_birthday_calendar(df_members)

    # --- 2. 사용설명서 ---
    elif sel_menu == "📖 사용설명서":
        draw_manual_tab()

    # --- 3. 출석체크 ---
    elif sel_menu == "📋 출석체크":
        st.subheader("📋 요일별 맞춤 출석체크")
        st.markdown('<div class="info-tip">💡 <b>Tip:</b> 날짜를 선택하면 해당 요일의 모임이 자동으로 뜹니다. 체크 후 반드시 하단 <b>[저장하기]</b>를 눌러주세요.</div>', unsafe_allow_html=True)
        
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
        st.markdown('<div class="info-tip">💡 <b>Tip:</b> 기간을 설정하여 출석 현황을 한눈에 보세요. 지난주 출석을 수정하려면 <b>하단 수정 메뉴</b>를 이용하세요.</div>', unsafe_allow_html=True)

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
        st.markdown('<div class="info-tip">💡 <b>Tip:</b> 소그룹원들의 기도제목을 기록하고 히스토리를 관리해보세요.</div>', unsafe_allow_html=True)
        
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

    # --- 6. 사역 보고 ---
    elif sel_menu == "📨 사역 보고":
        st.subheader("📨 소그룹 사역 보고")
        st.markdown('<div class="info-tip">💡 <b>Tip:</b> 매주 소그룹 사역 내용을 적어주세요. 목사님의 답변도 여기서 확인할 수 있습니다.</div>', unsafe_allow_html=True)
        
        if "답변" not in df_reports.columns: df_reports["답변"] = ""

        if is_admin:
            st.markdown("### 📥 관리자 모드: 보고서 확인 및 답변 작성")
            c1, c2 = st.columns([1, 2])
            r_date_adm = c1.date_input("조회 기준 날짜", datetime.date.today(), key="r_date_adm")
            sun, sat = get_week_range(r_date_adm)
            c2.caption(f"📅 조회 기간: {sun.strftime('%Y-%m-%d')} ~ {sat.strftime('%Y-%m-%d')}")
            
            df_rep_stat = df_reports.copy()
            df_rep_stat["날짜"] = pd.to_datetime(df_rep_stat["날짜"], errors='coerce')
            mask = (df_rep_stat["날짜"] >= pd.Timestamp(sun)) & (df_rep_stat["날짜"] <= pd.Timestamp(sat))
            weekly_reports = df_reports[mask].sort_values(by="날짜", ascending=False)
            
            if weekly_reports.empty:
                st.info("해당 주간에 제출된 보고서가 없습니다.")
            else:
                for i, row in weekly_reports.iterrows():
                    with st.container():
                        st.markdown(f"""
                        <div class="report-card">
                            <div class="report-header">🗓️ {row['날짜']} | 👤 {row['작성자']}</div>
                            <div class="report-content">{row['내용']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        new_ans = st.text_area(f"💬 {row['작성자']}님 보고에 대한 피드백 작성", value=row['답변'], key=f"ans_{i}", height=70)
                        
                        if st.button("답변 저장", key=f"btn_{i}"):
                            original_idx = row.name 
                            df_reports.at[original_idx, "답변"] = new_ans
                            save_data("reports", df_reports)
                            st.success(f"✅ {row['작성자']}님에게 답변을 저장했습니다!"); time.sleep(1); st.rerun()
                        st.divider()

        else:
            st.markdown(f"### 📂 {current_user_name}님의 보고서")
            
            with st.expander("📝 새 보고서 작성하기"):
                with st.form("report_form"):
                    r_date = st.date_input("작성일", datetime.date.today())
                    r_content = st.text_area("내용", height=150, placeholder="이번 주 모임 내용과 특이사항을 기록해주세요.")
                    if st.form_submit_button("제출"):
                        new_r = pd.DataFrame([{
                            "날짜": str(r_date), 
                            "작성자": current_user_name, 
                            "내용": r_content, 
                            "답변": ""
                        }])
                        save_data("reports", pd.concat([df_reports, new_r], ignore_index=True))
                        st.success("제출 완료"); st.rerun()
            
            st.divider()
            
            my_reports = df_reports[df_reports["작성자"] == current_user_name].copy()
            if my_reports.empty:
                st.info("제출한 보고서가 없습니다.")
            else:
                my_reports["날짜_dt"] = pd.to_datetime(my_reports["날짜"], errors='coerce')
                my_reports = my_reports.sort_values(by="날짜_dt", ascending=False).drop(columns=["날짜_dt"])
                
                for i, row in my_reports.iterrows():
                    html_content = f"""
                    <div class="report-card">
                        <div class="report-header">🗓️ {row['날짜']} 제출</div>
                        <div class="report-content">{row['내용']}</div>
                    """
                    if row['답변'] and str(row['답변']).strip() != "":
                        html_content += f"""
                        <div class="reply-box">
                            <div class="reply-title">💌 목회자 피드백</div>
                            <div>{row['답변']}</div>
                        </div>
                        """
                    html_content += "</div>"
                    st.markdown(html_content, unsafe_allow_html=True)

    # --- 7. 명단 관리 ---
    elif sel_menu == "👥 명단 관리":
        st.subheader("명단 관리")
        st.markdown('<div class="info-tip">💡 <b>Tip:</b> 연락처, 주소 등이 바뀌었을 때 직접 수정할 수 있습니다. <b>음력 생일</b>인 경우, 음력 칸에 <b>O</b>를 적어주세요.</div>', unsafe_allow_html=True)

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

