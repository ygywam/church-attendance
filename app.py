import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- [설정] 구글 시트 파일 이름 ---
# (주의: 구글 시트 파일 제목과 똑같아야 합니다!)
SHEET_NAME = "교회출석데이터"

# 페이지 기본 설정
st.set_page_config(page_title="사랑의교회", layout="wide", initial_sidebar_state="collapsed")

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_google_sheet_client():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def get_worksheet(worksheet_name):
    client = get_google_sheet_client()
    sheet = client.open(SHEET_NAME)
    try:
        return sheet.worksheet(worksheet_name)
    except:
        return sheet.add_worksheet(title=worksheet_name, rows=100, cols=20)

# --- 데이터 읽기/쓰기 함수 (기도제목 기능 추가됨) ---
def load_data(sheet_name):
    ws = get_worksheet(sheet_name)
    data = ws.get_all_records()
    
    if not data:
        # 데이터가 없을 때 기본 컬럼 틀 만들어주기
        if sheet_name == "members":
            return pd.DataFrame(columns=["이름", "성별", "생일", "전화번호", "주소", "가족ID", "소그룹", "비고"])
        elif sheet_name == "attendance_log":
            return pd.DataFrame(columns=["날짜", "모임명", "이름", "소그룹", "출석여부"])
        elif sheet_name == "users":
            return pd.DataFrame(columns=["아이디", "비밀번호", "이름", "역할", "담당소그룹"])
        elif sheet_name == "prayer_log":  # [중요] 기도제목 탭 정의 추가
            return pd.DataFrame(columns=["날짜", "이름", "소그룹", "내용", "작성자"])
    
    df = pd.DataFrame(data)
    return df.astype(str)

def save_data(sheet_name, df):
    ws = get_worksheet(sheet_name)
    ws.clear()
    ws.append_row(df.columns.tolist())
    ws.update(range_name='A2', values=df.values.tolist())

# --- 로그인 시스템 ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None

def login(username, password):
    df_users = load_data("users")
    matched = df_users[(df_users["아이디"] == username) & (df_users["비밀번호"] == password)]
    
    if not matched.empty:
        st.session_state["logged_in"] = True
        st.session_state["user_info"] = matched.iloc[0].to_dict()
        st.rerun()
    else:
        st.error("아이디 또는 비밀번호가 잘못되었습니다.")

def logout():
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None
    st.rerun()

# --- 메인 앱 ---
def main():
    # [수정] 화면 상단 제목
    st.title("⛪ 사랑의교회 출석체크 시스템")

    # 사이드바 로그인
    with st.sidebar:
        st.header("로그인")
        if not st.session_state["logged_in"]:
            input_id = st.text_input("아이디")
            input_pw = st.text_input("비밀번호", type="password")
            if st.button("로그인"):
                login(input_id, input_pw)
            st.caption("※ 초기 설정: admin / 1234")
        else:
            user = st.session_state["user_info"]
            st.success(f"환영합니다! {user['이름']}님")
            st.caption(f"권한: {user['역할']}")
            if st.button("로그아웃"):
                logout()

    if not st.session_state["logged_in"]:
        st.warning("👈 사이드바에서 로그인해주세요.")
        st.stop()

    # 데이터 로드
    current_user = st.session_state["user_info"]
    is_admin = (current_user["역할"] == "admin")
    
    df_members = load_data("members")
    df_att = load_data("attendance_log")
    df_prayer = load_data("prayer_log") # 기도제목 로드

    # 탭 구성
    tabs_list = ["📋 출석체크", "📊 통계", "🙏 기도제목", "👥 명단 관리"]
    if is_admin:
        tabs_list.append("🔐 계정 관리")
    
    tabs = st.tabs(tabs_list)

    # --- TAB 1: 출석체크 ---
    with tabs[0]:
        st.subheader("모임 출석 확인")
        c1, c2 = st.columns(2)
        
        check_date = c1.date_input("날짜 선택", datetime.date.today())
        weekdays = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
        korean_day = weekdays[check_date.weekday()]
        
        if korean_day == "(일)":
            c1.markdown(f":red[**오늘은 {korean_day}요일 입니다.**]") 
        else:
            c1.caption(f"선택한 날짜는 **{korean_day}요일** 입니다.")

        meeting_name = c2.selectbox("모임", ["주일 1부", "주일 2부", "주일 오후", "수요예배", "금요철야", "새벽예배"])

        # 다중 소그룹 선택 로직
        all_groups = sorted(df_members["소그룹"].unique()) if not df_members.empty else []
        
        if is_admin:
            selected_group = st.selectbox("소그룹 (관리자)", ["전체 보기"] + list(all_groups))
        else:
            raw_groups = str(current_user["담당소그룹"])
            my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
            
            if len(my_groups) > 1:
                selected_group = st.selectbox("📌 관리할 소그룹을 선택하세요", my_groups)
            elif len(my_groups) == 1:
                selected_group = my_groups[0]
                st.info(f"📌 담당: {selected_group}")
            else:
                selected_group = None

        if selected_group and selected_group != "전체 보기":
            target_members = df_members[df_members["소그룹"] == selected_group]
        elif selected_group == "전체 보기":
            target_members = df_members
        else:
            target_members = pd.DataFrame()

        if not target_members.empty:
            current_log = df_att[
                (df_att["날짜"] == str(check_date)) & 
                (df_att["모임명"] == meeting_name)
            ]
            attended_names = current_log["이름"].tolist()

            with st.form("att_form"):
                st.write(f"**{selected_group}** 명단 ({len(target_members)}명)")
                cols = st.columns(3)
                status_dict = {}
                
                for idx, row in target_members.iterrows():
                    name = row["이름"]
                    is_checked = name in attended_names
                    status_dict[name] = cols[idx % 3].checkbox(name, value=is_checked)
                
                if st.form_submit_button("저장하기", use_container_width=True):
                    # 해당 그룹/날짜 데이터만 갱신
                    mask = (
                        (df_att["날짜"] == str(check_date)) & 
                        (df_att["모임명"] == meeting_name) & 
                        (df_att["소그룹"] == selected_group)
                    )
                    df_clean = df_att[~mask]

                    new_records = []
                    for name, checked in status_dict.items():
                        if checked:
                            new_records.append({
                                "날짜": str(check_date), "모임명": meeting_name,
                                "이름": name, "소그룹": selected_group, "출석여부": "출석"
                            })
                    
                    df_final = pd.concat([df_clean, pd.DataFrame(new_records)], ignore_index=True)
                    save_data("attendance_log", df_final)
                    st.success(f"{selected_group} 출석이 저장되었습니다!")
                    st.rerun()

    # --- TAB 2: 통계 ---
    with tabs[1]:
        st.subheader("통계 및 히스토리")
        if df_att.empty:
            st.info("데이터 없음")
        else:
            df_att["날짜"] = pd.to_datetime(df_att["날짜"], errors='coerce')
            df_att["연도"] = df_att["날짜"].dt.year
            df_att["월"] = df_att["날짜"].dt.strftime("%Y-%m")

            st.markdown("### 📊 전체 현황")
            stat_mode = st.radio("보기 방식", ["월별 추세", "소그룹별 출석왕"], horizontal=True)
            
            if stat_mode == "월별 추세":
                daily_counts = df_att.groupby("월")["이름"].count()
                st.line_chart(daily_counts)
            else:
                if is_admin:
                    group_stat = df_att.groupby("소그룹")["이름"].count().reset_index(name="총 출석수")
                    st.bar_chart(group_stat.set_index("소그룹"))
                else:
                    my_group_att = df_att[df_att["소그룹"] == current_user["담당소그룹"]]
                    member_counts = my_group_att["이름"].value_counts().reset_index()
                    member_counts.columns = ["이름", "출석횟수"]
                    st.dataframe(member_counts, use_container_width=True)
            
            st.divider()

            if is_admin:
                st.markdown("### 👤 개인별 히스토리 (관리자용)")
                search_person = st.selectbox("성도 이름 선택", ["선택해주세요"] + sorted(df_att["이름"].unique()))
                if search_person != "선택해주세요":
                    person_history = df_att[df_att["이름"] == search_person]
                    history_summary = person_history.groupby(["연도", "소그룹"])["출석여부"].count().reset_index()
                    history_summary.columns = ["연도", "당시 소그룹", "출석 횟수"]
                    st.table(history_summary)
                    
                    with st.expander("상세 기록 보기"):
                         st.dataframe(person_history[["날짜", "모임명", "소그룹"]].sort_values("날짜", ascending=False), use_container_width=True)

    # --- TAB 3: 기도제목 ---
    with tabs[2]:
        st.subheader("🙏 소그룹원 기도제목 관리")
        
        if is_admin:
            grp_list = sorted(df_members["소그룹"].unique())
            p_group = st.selectbox("소그룹 선택 (기도제목)", grp_list)
        else:
            raw_groups = str(current_user["담당소그룹"])
            my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
            if len(my_groups) > 1:
                p_group = st.selectbox("소그룹 선택", my_groups)
            elif len(my_groups) == 1:
                p_group = my_groups[0]
            else:
                p_group = None
        
        if p_group:
            p_members = df_members[df_members["소그룹"] == p_group]["이름"].tolist()
            if not p_members:
                st.warning("등록된 멤버가 없습니다.")
            else:
                p_name = st.selectbox("이름을 선택하세요", p_members)
                
                with st.expander(f"✏️ {p_name}님 새 기도제목 입력하기", expanded=True):
                    with st.form("prayer_input"):
                        p_date = st.date_input("기도 요청 날짜", datetime.date.today())
                        p_content = st.text_area("기도제목 내용", height=100, placeholder="내용을 입력하세요...")
                        
                        if st.form_submit_button("저장하기"):
                            if p_content.
