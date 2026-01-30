import streamlit as st
import pandas as pd
import datetime
import calendar
import time
import gspread
import extra_streamlit_components as stx
from oauth2client.service_account import ServiceAccountCredentials
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
st.set_page_config(page_title="회정교회 출석부 v3.1", layout="wide", initial_sidebar_state="collapsed")

# --- [스타일] CSS 적용 ---
st.markdown("""
    <style>
    html, body, p, li, .stMarkdown { font-size: 18px !important; }
    h1 { 
        font-size: 46px !important; text-align: center; word-break: keep-all; 
        margin-bottom: 30px !important; font-weight: 800 !important;
    }
    .stButton button { font-size: 18px !important; font-weight: bold; width: 100%; }
    
    .notice-box {
        background-color: #fff3cd; border: 2px solid #ffeeba; color: #856404;
        padding: 15px; border-radius: 10px; margin-bottom: 20px;
        text-align: center; font-size: 20px; font-weight: bold; line-height: 1.5; word-break: keep-all;
    }
    
    .report-card {
        background-color: #f8f9fa; border: 1px solid #dee2e6; 
        border-radius: 10px; padding: 20px; margin-bottom: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .report-header { font-size: 16px; color: #6c757d; margin-bottom: 10px; font-weight: bold;}
    .report-content { font-size: 18px; color: #212529; white-space: pre-wrap; line-height: 1.6;}
    .reply-box {
        background-color: #e8f5e9; border-left: 5px solid #4caf50;
        padding: 15px; margin-top: 15px; border-radius: 5px;
    }
    .reply-title { color: #2e7d32; font-weight: bold; font-size: 16px; margin-bottom: 5px; }

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
    .info-tip {
        background-color: #e3f2fd; border-left: 5px solid #2196f3;
        padding: 15px; margin-bottom: 20px; border-radius: 5px; color: #0d47a1;
        font-size: 16px;
    }
    .log-entry {
        border-left: 3px solid #ccc; padding-left: 15px; margin-bottom: 20px;
    }
    .log-ver { font-weight: bold; font-size: 1.1em; color: #333; }
    .log-date { color: #888; font-size: 0.9em; margin-left: 10px; }
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

def extract_date_numbers(date_str):
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
                parts = extract_date_numbers(row["생일"])
                if len(parts) >= 3:
                    b_month_origin, b_day_origin = parts[1], parts[2]
                elif len(parts) == 2:
                    b_month_origin, b_day_origin = parts[0], parts[1]
                else: continue
                
                if b_month_origin == 0 or b_day_origin == 0: continue
                group_name = str(row.get("소그룹", "")).strip()

                is_lunar = False
                if lunar_col_name:
                    val = str(row[lunar_col_name]).strip().upper()
                    if val in ["O", "0", "ㅇ", "YES", "TRUE", "Y"]: is_lunar = True

                if is_lunar:
                    check_years = [year - 1, year, year + 1]
                    for check_year in check_years:
                        try:
                            calendar_converter.setLunarDate(check_year, b_month_origin, b_day_origin, False)
                            if calendar_converter.solarYear == year and calendar_converter.solarMonth == month:
                                s_day = calendar_converter.solarDay
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

# [수정] 개발 로그 (26일 내용은 이전과 동일)
def draw_changelog():
    st.subheader("🛠️ 개발 및 업데이트 로그")
    st.info("이 시스템이 발전해 온 기록입니다.")

    logs = [
        ("v3.1", "2026-01-30", "뷰어(Viewer) 권한 수정", 
         "- 뷰어 계정(viewer)이 '명단 관리' 탭에서 전체 명단을 볼 수 있도록 권한 확대\n- 뷰어의 '담당소그룹'이 '전체'일 경우 발생하는 조회 오류 수정"),
        ("v3.0", "2026-01-30", "권한 체계 개편 및 뷰어(Viewer) 모드 도입", 
         "- **제2의 관리자(viewer) 추가:** 출석/통계 확인은 전체 가능하되, 개인적인 기도제목/보고서는 볼 수 없는 안전한 관리자 모드 신설\n- **공동 리더 프라이버시 보호:** 같은 소그룹이라도 '내가 쓴 글'만 보이도록 변경"),
        ("v2.9", "2026-01-26", "관리자 기능 강화 및 UX 개선", 
         "- [관리자] 통계 탭에 '날짜별/모임별 출석 인원' 현황표 추가\n- [관리자] 사역 보고 및 기도제목에 대한 '삭제 권한' 부여\n- 입력창 자동 초기화 및 버튼 UI 개선 (✏️수정, 🗑️삭제)"),
        ("v2.8", "2026-01-26", "기도제목 수정/삭제 기능 추가", 
         "- 기도제목도 오타 수정이나 삭제가 가능하도록 기능 개선\n- 소그룹 리더가 자신이 작성한 내역 관리 가능"),
        ("v2.7", "2026-01-26", "사역 보고 수정/삭제 기능 추가", 
         "- 본인이 작성한 보고서를 수정하거나 삭제하는 기능 추가\n- 오타 수정 및 중복 게시물 정리 가능"),
        ("v2.6.1", "2026-01-24", "출석체크 정렬 순서 최적화", 
         "- '출석유무순' 정렬 시, 활동 성도(🟢)가 위쪽, 장기 결석(⚪)이 아래쪽으로 오도록 순서 변경"),
        ("v2.6", "2026-01-24", "출석체크 스마트 정렬 & 개발 로그 추가", 
         "- 출석 기록이 있는 '활동 성도'와 없는 '장기 결석'을 자동 분류하여 정렬\n- 이름 옆에 상태 아이콘(🟢 활동 / ⚪ 장기결석) 추가\n- 업데이트 내역을 확인하는 '개발 로그' 탭 신설"),
        ("v2.5", "2026-01-24", "명단 관리 편의성 개선", 
         "- 새 가족 등록 시, '다음 추천 가족ID' 자동 계산 및 안내 기능 추가\n- 불필요한 입력 혼선 방지를 위한 안내 문구 강화"),
        ("v2.4", "2026-01-24", "정렬 기능 고도화", 
         "- 명단 관리에서 '생일순(월일)'과 '연령순(나이)' 정렬을 명확히 분리\n- 다가오는 생일자를 더 쉽게 찾을 수 있도록 개선"),
        ("v2.3", "2026-01-24", "셀프 회원가입 도입", 
         "- 관리자가 이름만 등록해두면, 소그룹장이 직접 아이디/비번 생성 가능\n- 중복 가입 방지 및 계정 분실 시 재설정 프로세스 정립"),
        ("v2.2.1", "2026-01-24", "아이폰/사파리 호환성 해결", 
         "- 구형 모바일 브라우저 정규표현식 오류 수정 및 안전한 날짜 파싱 로직 적용"),
        ("v2.2", "2026-01-24", "생일 달력 네비게이션", 
         "- 이번 달뿐만 아니라 이전 달, 다음 달 생일자도 확인 가능하도록 이동 버튼 추가"),
        ("v2.1", "2026-01-24", "사용자 친화적 가이드(Onboarding)", 
         "- 각 메뉴마다 '친절한 팁(Tip Box)' 추가\n- 상세 사용설명서 탭 디자인 개선"),
        ("v2.0", "2026-01-24", "음력 생일 완벽 지원", 
         "- 한국형 음력 캘린더 라이브러리 탑재\n- 'O' 표시만으로 매년 달라지는 음력 생일을 자동 계산하여 양력 달력에 표시"),
    ]

    for ver, date, title, desc in logs:
        st.markdown(f"""
        <div class="log-entry">
            <span class="log-ver">{ver}</span> <span class="log-date">{date}</span>
            <div style="font-weight: bold; margin-top: 5px;">{title}</div>
            <div style="white-space: pre-wrap; font-size: 0.95em; color: #555; margin-top: 5px;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

def draw_manual_tab():
    st.markdown("## 📘 회정교회 출석체크 시스템 사용법 (v3.1)")
    with st.expander("✅ 1. 출석체크 하는 법"):
        st.markdown("1. **[📋 출석체크]** 메뉴 선택.\n2. 상단 정렬 옵션에서 **'🌱 출석유무순'**을 쓰면 활동 성도가 위로 올라와 편합니다.\n3. 체크 후 **[✅ 출석 저장하기]** 필수.")
    with st.expander("📊 2. 통계 및 보고서"):
        st.markdown("1. **[📊 통계]**에서 기간별 출석 현황 확인.\n2. **[📨 사역 보고]**에서 보고서 작성 (본인 작성 내용만 보임).")
    with st.expander("🙏 3. 기도제목 관리"):
        st.markdown("1. **[🙏 기도제목]**에서 멤버별 기도제목 기록.\n2. 공동 리더가 있어도 **내가 쓴 기록만** 보입니다. (프라이버시 보호)")
    with st.expander("🎂 4. 생일 및 명단"):
        st.markdown("1. **[🏠 홈]**에서 생일 달력 확인 (음력 자동 변환).\n2. **[👥 명단 관리]**에서 정보 수정 및 가족ID 확인.")

def draw_notice_section(is_admin, current_user_name):
    df_notices = load_data("notices")
    if not df_notices.empty:
        latest = df_notices.sort_values(by="날짜", ascending=False).iloc[0]
        st.markdown(f"""<div class="notice-box">📢 <b>공지사항 ({latest['날짜']})</b><br><br>{latest['내용']}</div>""", unsafe_allow_html=True)
    if is_admin:
        with st.expander("📢 공지사항 등록 (관리자)"):
            with st.form("notice_form"):
                n_date = st.date_input("날짜", datetime.date.today())
                n_content = st.text_area("내용", height=100)
                if st.form_submit_button("등록"):
                    new_n = pd.DataFrame([{"날짜": str(n_date), "내용": n_content, "작성자": current_user_name}])
                    save_data("notices", pd.concat([df_notices, new_n], ignore_index=True))
                    st.success("등록됨"); st.rerun()

# --- 로그인 & 회원가입 로직 ---
def process_login(username, password, cookie_manager):
    df_users = load_data("users")
    matched = df_users[(df_users["아이디"].astype(str) == str(username)) & (df_users["비밀번호"].astype(str) == str(password))]
    if not matched.empty:
        st.session_state["logged_in"] = True
        st.session_state["user_info"] = matched.iloc[0].to_dict()
        exp = datetime.datetime.now() + datetime.timedelta(days=30)
        cookie_manager.set("church_user_id", username, expires_at=exp)
        st.rerun()
    else: st.error("아이디 또는 비밀번호가 일치하지 않습니다.")

def process_signup(reg_name, reg_id, reg_pw):
    ws = get_worksheet("users")
    if not ws: return
    try: cell = ws.find(reg_name) 
    except gspread.exceptions.CellNotFound:
        st.error(f"❌ '{reg_name}'님은 명단에 없습니다. 관리자에게 문의해주세요."); return
    row_num = cell.row
    existing_id = ws.cell(row_num, 1).value 
    if existing_id and str(existing_id).strip() != "":
        st.error("❌ 이미 등록된 계정이 있습니다. 분실 시 관리자에게 초기화를 요청하세요."); return
    ws.update_cell(row_num, 1, reg_id); ws.update_cell(row_num, 2, reg_pw) 
    load_data.clear()
    st.success(f"✅ 환영합니다, {reg_name}님! 계정이 생성되었습니다."); st.info("이제 [🔑 로그인] 메뉴로 이동하여 로그인해주세요.")

def process_logout(cookie_manager):
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None
    try: cookie_manager.delete("church_user_id")
    except: pass
    with st.spinner("로그아웃 중입니다..."): time.sleep(1)
    st.rerun()

# --- 4. 메인 앱 ---
def main():
    cookie_manager = stx.CookieManager(key="church_cookies")
    st.title("⛪ 회정교회 출석체크 시스템 v3.1")

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user_info"] = None

    if not st.session_state["logged_in"]:
        time.sleep(0.5)
        cookie_id = cookie_manager.get(cookie="church_user_id")
        if cookie_id:
            df_users = load_data("users")
            match = df_users[df_users["아이디"].astype(str) == str(cookie_id)]
            if not match.empty:
                st.session_state["logged_in"] = True
                st.session_state["user_info"] = match.iloc[0].to_dict()
                st.rerun()

    with st.sidebar:
        if not st.session_state["logged_in"]:
            mode = st.radio("접속 모드", ["🔑 로그인", "✨ 계정 생성"], index=0)
            st.divider()
            if mode == "🔑 로그인":
                st.header("로그인")
                uid = st.text_input("아이디", key="lid")
                upw = st.text_input("비밀번호", type="password", key="lpw")
                if st.button("로그인", use_container_width=True): process_login(uid, upw, cookie_manager)
            else:
                st.header("계정 생성 (최초 1회)")
                st.caption("관리자가 등록한 이름이 있어야 가입 가능합니다.")
                reg_name = st.text_input("이름 (실명)", placeholder="예: 홍길동")
                reg_id = st.text_input("사용할 아이디")
                reg_pw = st.text_input("사용할 비밀번호", type="password")
                reg_pw_chk = st.text_input("비밀번호 확인", type="password")
                if st.button("가입하기", use_container_width=True):
                    if not reg_name or not reg_id or not reg_pw: st.warning("모든 정보를 입력해주세요.")
                    elif reg_pw != reg_pw_chk: st.error("비밀번호가 일치하지 않습니다.")
                    else: process_signup(reg_name, reg_id, reg_pw)
        else:
            u = st.session_state["user_info"]
            st.success(f"👤 {u['이름']}님 환영합니다")
            st.caption(f"권한: {u['역할']}")
            if st.button("로그아웃", use_container_width=True): process_logout(cookie_manager)

    if not st.session_state["logged_in"]:
        st.info("👈 왼쪽 사이드바에서 로그인하거나 계정을 생성해주세요.")
        st.stop()

    current_user = st.session_state["user_info"]
    current_user_name = current_user["이름"]
    
    # [v3.0] 권한 구분 로직
    user_role = str(current_user.get("역할", "")).lower().strip()
    is_admin = (user_role == "admin")
    is_viewer = (user_role == "viewer") # 제2의 관리자
    
    df_members = load_data("members")
    df_att = load_data("attendance_log")
    df_prayer = load_data("prayer_log")
    df_reports = load_data("reports")

    menu = ["🏠 홈", "📖 사용설명서", "📋 출석체크", "📊 통계", "🙏 기도제목", "📨 사역 보고", "👥 명단 관리", "🛠️ 개발 로그"]
    if is_admin: menu.insert(7, "🔐 계정 관리")
    
    sel_menu = st.radio("메뉴", menu, horizontal=True, label_visibility="collapsed")
    st.divider()

    # --- 각 메뉴 연결 ---
    if sel_menu == "🏠 홈":
        st.markdown('<div class="info-tip">👋 환영합니다! 공지사항과 생일자를 확인해보세요.</div>', unsafe_allow_html=True)
        draw_notice_section(is_admin, current_user_name)
        st.subheader("생일 캘린더")
        draw_birthday_calendar(df_members)

    elif sel_menu == "📖 사용설명서":
        draw_manual_tab()

    elif sel_menu == "📋 출석체크":
        st.subheader("📋 요일별 맞춤 출석체크")
        
        c1, c2 = st.columns(2)
        chk_date = c1.date_input("날짜 선택", datetime.date.today())
        weekday_idx = chk_date.weekday()
        days_kor = ["월", "화", "수", "목", "금", "토", "일"]
        day_str = days_kor[weekday_idx]
        c1.info(f"선택일: {chk_date.strftime('%Y-%m-%d')} ({day_str})")

        all_grps = sorted(df_members["소그룹"].unique())
        
        # [v3.0] 뷰어(viewer)도 전체 소그룹을 볼 수 있음
        if is_admin or is_viewer: 
            grp = c2.selectbox("소그룹(관리자/뷰어)", ["전체 보기"] + all_grps)
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
                active_members = set(df_att["이름"].unique())
                targets = targets.copy()
                targets["상태"] = targets["이름"].apply(lambda x: "🟢 활동" if x in active_members else "⚪ 장기결석")
                
                st.markdown('<div class="info-tip">💡 <b>Tip:</b> <b>\'🌱 출석유무순\'</b>을 선택하면 자주 오는 성도님이 위쪽에 표시되어 찾기 쉽습니다.</div>', unsafe_allow_html=True)
                sort_chk = st.radio("명단 정렬 기준:", ["🌱 출석유무순 (추천)", "👨‍👩‍👧‍👦 가족순", "🔤 이름순"], horizontal=True)
                
                if sort_chk == "🌱 출석유무순 (추천)":
                    targets = targets.sort_values(by=["상태", "이름"], ascending=[False, True]) 
                elif sort_chk == "👨‍👩‍👧‍👦 가족순":
                    targets["가족ID_정렬"] = pd.to_numeric(targets["가족ID"], errors='coerce').fillna(99999)
                    targets = targets.sort_values(by=["가족ID_정렬", "이름"])
                elif sort_chk == "🔤 이름순":
                    targets = targets.sort_values(by="이름")

                current_log = df_att[df_att["날짜"] == str(chk_date)]
                grid_data = []
                for _, member in targets.iterrows():
                    row = {
                        "이름": member["이름"], 
                        "소그룹": member["소그룹"], 
                        "상태": member["상태"]
                    } 
                    member_log = current_log[current_log["이름"] == member["이름"]]
                    for col in target_meetings:
                        row[col] = not member_log[member_log["모임명"] == col].empty
                    grid_data.append(row)
                
                df_grid = pd.DataFrame(grid_data)
                
                col_conf = {
                    "이름": st.column_config.TextColumn("이름", disabled=True, pinned=True),
                    "상태": st.column_config.TextColumn("상태", disabled=True, width="small"),
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

    elif sel_menu == "📊 통계":
        st.subheader("📊 출석 누적 현황 및 상세 조회")
        st.markdown('<div class="info-tip">💡 <b>Tip:</b> 기간을 설정하여 출석 현황을 한눈에 보세요. 지난주 출석을 수정하려면 <b>하단 수정 메뉴</b>를 이용하세요.</div>', unsafe_allow_html=True)

        if df_att.empty: st.info("데이터가 없습니다.")
        else:
            if "날짜" not in df_att.columns: df_att["날짜"] = ""
            df_stat = df_att.copy()
            df_stat["날짜"] = pd.to_datetime(df_stat["날짜"], errors='coerce')
            
            c1, c2 = st.columns([2, 1])
            today = datetime.date.today()
            start_of_year = datetime.date(today.year, 1, 1)
            date_range = c1.date_input("📅 조회 기간", (start_of_year, today), format="YYYY/MM/DD")
            
            if len(date_range) == 2:
                start_d, end_d = date_range
                
                if is_admin or is_viewer:
                    st.markdown("### 📅 [관리자/뷰어] 날짜별/모임별 출석 인원")
                    mask_adm = (df_stat["날짜"] >= pd.Timestamp(start_d)) & (df_stat["날짜"] <= pd.Timestamp(end_d))
                    df_stat_filtered = df_stat[mask_adm]
                    
                    if not df_stat_filtered.empty:
                        daily_counts = df_stat_filtered.groupby(['날짜', '모임명']).size().unstack(fill_value=0)
                        daily_counts.sort_index(ascending=False, inplace=True)
                        new_index = [f"{d.strftime('%Y-%m-%d')} {get_day_name(d)}" for d in daily_counts.index]
                        daily_counts.index = new_index
                        st.dataframe(daily_counts, use_container_width=True)
                        st.divider()

                if is_admin or is_viewer:
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

    elif sel_menu == "🙏 기도제목":
        st.subheader("기도제목 관리")
        st.markdown('<div class="info-tip">💡 <b>Tip:</b> 소그룹원들의 기도제목을 기록하고 히스토리를 관리해보세요.</div>', unsafe_allow_html=True)
        
        if is_admin:
            st.markdown("### 🗓️ [관리자] 주간 전체 기도제목")
            c1, c2 = st.columns([1, 2])
            p_date = c1.date_input("조회 기준 날짜", datetime.date.today(), key="p_date_adm")
            sun, sat = get_week_range(p_date)
            c2.caption(f"📅 조회 기간: {sun.strftime('%Y-%m-%d')} ~ {sat.strftime('%Y-%m-%d')}")
            
            df_prayer_stat = df_prayer.copy()
            df_prayer_stat["날짜"] = pd.to_datetime(df_prayer_stat["날짜"], errors='coerce')
            mask = (df_prayer_stat["날짜"] >= pd.Timestamp(sun)) & (df_prayer_stat["날짜"] <= pd.Timestamp(sat))
            weekly_prayers = df_prayer[mask].sort_values(by=["소그룹", "이름"])
            
            if weekly_prayers.empty: st.info("해당 주간에 등록된 기도제목이 없습니다.")
            else:
                for i, r in weekly_prayers.iterrows():
                    with st.container():
                        col_info, col_act = st.columns([8, 1])
                        with col_info:
                            st.markdown(f"**{r['이름']} ({r['소그룹']})** | {r['날짜']}")
                            st.info(r['내용'])
                        with col_act:
                            if st.button("🗑️", key=f"adm_p_del_{i}"):
                                df_prayer = df_prayer.drop(i)
                                save_data("prayer_log", df_prayer)
                                st.success("삭제됨"); time.sleep(0.5); st.rerun()
                        st.divider()

        else:
            all_g = sorted(df_members["소그룹"].unique())
            my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
            if len(my_gs)>1: p_grp = st.selectbox("그룹", my_gs)
            elif len(my_gs)==1: p_grp = my_gs[0]
            else: p_grp = None
            if p_grp:
                mems = df_members[df_members["소그룹"]==p_grp]["이름"].tolist()
                p_who = st.selectbox("이름", mems)
                
                with st.expander("새 기도제목 입력", expanded=True):
                    with st.form("p_form"):
                        pd_in = st.date_input("날짜", datetime.date.today())
                        pc_in = st.text_area("내용", key="p_content_input")
                        if st.form_submit_button("저장"):
                            new_p = pd.DataFrame([{"날짜":str(pd_in), "이름":p_who, "소그룹":p_grp, "내용":pc_in, "작성자":current_user_name}])
                            save_data("prayer_log", pd.concat([df_prayer, new_p], ignore_index=True))
                            st.session_state["p_content_input"] = ""
                            st.success("저장됨"); time.sleep(0.5); st.rerun()
                            
                st.divider()
                st.caption(f"{p_who}님의 히스토리")
                
                if is_viewer: 
                    my_prayers = df_prayer[(df_prayer["이름"] == p_who) & (df_prayer["작성자"] == current_user_name)]
                else: 
                    my_prayers = df_prayer[(df_prayer["이름"] == p_who) & (df_prayer["작성자"] == current_user_name)]
                
                hist = my_prayers.sort_values("날짜", ascending=False)
                
                for i, r in hist.iterrows():
                    if st.session_state.get(f"pray_edit_{i}", False):
                        with st.form(f"pray_form_{i}"):
                            st.caption(f"📝 기도제목 수정 (No.{i})")
                            edit_p_date = st.date_input("날짜", pd.to_datetime(r['날짜']))
                            edit_p_content = st.text_area("내용", r['내용'])
                            c_save, c_cancel = st.columns(2)
                            if c_save.form_submit_button("💾 수정 저장"):
                                df_prayer.at[i, '날짜'] = str(edit_p_date)
                                df_prayer.at[i, '내용'] = edit_p_content
                                save_data("prayer_log", df_prayer)
                                st.session_state[f"pray_edit_{i}"] = False
                                st.success("수정되었습니다."); time.sleep(0.5); st.rerun()
                            if c_cancel.form_submit_button("취소"):
                                st.session_state[f"pray_edit_{i}"] = False
                                st.rerun()
                    else:
                        col_content, col_btns = st.columns([8, 3]) 
                        with col_content:
                            st.info(f"**{r['날짜']}**: {r['내용']}")
                        with col_btns:
                            b1, b2 = st.columns(2)
                            with b1:
                                if st.button("✏️ 수정", key=f"p_edit_{i}"):
                                    st.session_state[f"pray_edit_{i}"] = True
                                    st.rerun()
                            with b2:
                                if st.button("🗑️ 삭제", key=f"p_del_{i}"):
                                    df_prayer = df_prayer.drop(i)
                                    save_data("prayer_log", df_prayer)
                                    st.success("삭제됨"); time.sleep(0.5); st.rerun()

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
            
            if weekly_reports.empty: st.info("해당 주간에 제출된 보고서가 없습니다.")
            else:
                for i, row in weekly_reports.iterrows():
                    with st.container():
                        st.markdown(f"""<div class="report-card"><div class="report-header">🗓️ {row['날짜']} | 👤 {row['작성자']}</div><div class="report-content">{row['내용']}</div></div>""", unsafe_allow_html=True)
                        new_ans = st.text_area(f"💬 {row['작성자']}님 보고에 대한 피드백 작성", value=row['답변'], key=f"ans_{i}", height=70)
                        
                        c_save, c_del = st.columns([1, 1])
                        with c_save:
                            if st.button("답변 저장", key=f"btn_{i}"):
                                original_idx = row.name 
                                df_reports.at[original_idx, "답변"] = new_ans
                                save_data("reports", df_reports)
                                st.success(f"✅ {row['작성자']}님에게 답변을 저장했습니다!"); time.sleep(1); st.rerun()
                        with c_del:
                            if st.button("🗑️ 보고서 삭제", key=f"adm_del_{i}"):
                                df_reports = df_reports.drop(row.name)
                                save_data("reports", df_reports)
                                st.success("삭제되었습니다."); time.sleep(0.5); st.rerun()
                        st.divider()
        else:
            st.markdown(f"### 📂 {current_user_name}님의 보고서")
            with st.expander("📝 새 보고서 작성하기", expanded=True):
                with st.form("report_form"):
                    r_date = st.date_input("작성일", datetime.date.today())
                    r_content = st.text_area("내용", height=150, placeholder="이번 주 모임 내용과 특이사항을 기록해주세요.", key="r_content_input")
                    
                    if st.form_submit_button("제출"):
                        new_r = pd.DataFrame([{"날짜": str(r_date), "작성자": current_user_name, "내용": r_content, "답변": ""}])
                        save_data("reports", pd.concat([df_reports, new_r], ignore_index=True))
                        st.session_state["r_content_input"] = ""
                        st.success("제출 완료"); time.sleep(0.5); st.rerun()
            st.divider()
            
            my_reports = df_reports[df_reports["작성자"] == current_user_name].copy()
            
            if my_reports.empty: st.info("제출한 보고서가 없습니다.")
            else:
                my_reports["날짜_dt"] = pd.to_datetime(my_reports["날짜"], errors='coerce')
                my_reports_sorted = my_reports.sort_values(by="날짜_dt", ascending=False)
                
                for i, row in my_reports_sorted.iterrows():
                    if st.session_state.get(f"edit_mode_{i}", False):
                        with st.form(f"edit_form_{i}"):
                            st.caption(f"📝 보고서 수정 (No.{i})")
                            edit_date = st.date_input("날짜", pd.to_datetime(row['날짜']))
                            edit_content = st.text_area("내용", row['내용'], height=150)
                            c_save, c_cancel = st.columns(2)
                            if c_save.form_submit_button("💾 수정 완료"):
                                df_reports.at[i, '날짜'] = str(edit_date)
                                df_reports.at[i, '내용'] = edit_content
                                save_data("reports", df_reports)
                                st.session_state[f"edit_mode_{i}"] = False
                                st.success("수정되었습니다!"); time.sleep(0.5); st.rerun()
                            if c_cancel.form_submit_button("취소"):
                                st.session_state[f"edit_mode_{i}"] = False
                                st.rerun()
                    else:
                        html_content = f"""<div class="report-card"><div class="report-header">🗓️ {row['날짜']} 제출</div><div class="report-content">{row['내용']}</div>"""
                        if row['답변'] and str(row['답변']).strip() != "":
                            html_content += f"""<div class="reply-box"><div class="reply-title">💌 목회자 피드백</div><div>{row['답변']}</div></div>"""
                        html_content += "</div>"
                        st.markdown(html_content, unsafe_allow_html=True)
                        
                        c_edit, c_del = st.columns([1, 4]) 
                        with c_edit:
                            if st.button("✏️ 수정", key=f"btn_edit_{i}"):
                                st.session_state[f"edit_mode_{i}"] = True
                                st.rerun()
                        with c_del:
                            if st.button("🗑️ 삭제", key=f"btn_del_{i}"):
                                df_reports = df_reports.drop(i)
                                save_data("reports", df_reports)
                                st.success("삭제되었습니다."); time.sleep(0.5); st.rerun()

    elif sel_menu == "👥 명단 관리":
        st.subheader("명단 관리")
        try:
            fam_ids = pd.to_numeric(df_members["가족ID"], errors='coerce').fillna(0)
            next_fam_id = int(fam_ids.max()) + 1
        except: next_fam_id = 1
        c1, c2 = st.columns(2)
        c1.metric("총 인원", f"{len(df_members)}명"); c2.metric("새 가족 등록 시 추천 ID", f"{next_fam_id}번")
        st.caption("※ 맨 앞의 숫자는 '행 번호'로 자동 생성됩니다. 기존 가족은 해당 ID를 확인하여 동일하게 입력하세요.")
        
        # [v3.1 수정] 뷰어도 명단 전체 보기 및 저장 가능 (관리자와 동일 권한)
        if is_admin or is_viewer: 
            target = df_members
        else:
            my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
            target = df_members[df_members["소그룹"].isin(my_gs)]
            st.info(f"담당: {', '.join(my_gs)}")
        
        sort_option = st.radio("정렬 기준 선택", ["👨‍👩‍👧‍👦 가족끼리(기본)", "🔤 이름순", "🏘️ 소그룹순", "🎂 생일순(월일)", "👵 연령순(나이)"], horizontal=True)
        if not target.empty:
            target = target.copy()
            if sort_option == "👨‍👩‍👧‍👦 가족끼리(기본)":
                target["가족ID_정렬"] = pd.to_numeric(target["가족ID"], errors='coerce').fillna(99999)
                target = target.sort_values(by=["가족ID_정렬", "이름"])
                del target["가족ID_정렬"]
            elif sort_option == "🔤 이름순": target = target.sort_values(by="이름")
            elif sort_option == "🏘️ 소그룹순": target = target.sort_values(by=["소그룹", "이름"])
            elif sort_option == "🎂 생일순(월일)":
                def get_mmdd(date_str):
                    nums = extract_date_numbers(date_str)
                    if len(nums) >= 3: return nums[1] * 100 + nums[2]
                    elif len(nums) == 2: return nums[0] * 100 + nums[1]
                    return 9999 
                target["temp_sort"] = target["생일"].apply(get_mmdd)
                target = target.sort_values(by="temp_sort")
                del target["temp_sort"]
            elif sort_option == "👵 연령순(나이)": target = target.sort_values(by="생일")

        col_conf_mem = {"이름": st.column_config.TextColumn(pinned=True)}
        edited = st.data_editor(target, num_rows="dynamic", use_container_width=True, column_config=col_conf_mem)
        if st.button("저장"):
            # [v3.1 수정] 뷰어도 관리자와 동일하게 전체 저장 권한 부여
            if is_admin or is_viewer: 
                save_data("members", edited)
            else:
                my_gs = [g.strip() for g in str(current_user["담당소그룹"]).split(",") if g.strip()]
                mask = df_members["소그룹"].isin(my_gs)
                others = df_members[~mask]
                save_data("members", pd.concat([others, edited], ignore_index=True))
            st.success("저장 완료!"); st.rerun()

    # [NEW] 개발 로그 탭
    elif sel_menu == "🛠️ 개발 로그":
        draw_changelog()

    elif sel_menu == "🔐 계정 관리" and is_admin:
        st.subheader("계정 관리")
        e_users = st.data_editor(load_data("users"), num_rows="dynamic", use_container_width=True)
        if st.button("저장"): save_data("users", e_users); st.success("완료"); st.rerun()

if __name__ == "__main__":
    main()
