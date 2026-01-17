import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 설정 ---
# 구글 시트 파일 이름 (2단계에서 만든 스프레드시트 제목과 똑같아야 합니다)
SHEET_NAME = "교회출석데이터"

# 페이지 설정
st.set_page_config(page_title="회정교회 출석체크", layout="wide", initial_sidebar_state="collapsed")

# --- 구글 시트 연결 함수 (캐싱 적용) ---
@st.cache_resource
def get_google_sheet_client():
    # Streamlit Secrets에서 키 정보 가져오기
    creds_dict = st.secrets["gcp_service_account"]
    
    # 권한 설정
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
        # 시트가 없으면 생성 (에러 방지)
        return sheet.add_worksheet(title=worksheet_name, rows=100, cols=20)

# --- 데이터 읽기/쓰기 함수 ---
def load_data(sheet_name):
    """구글 시트에서 데이터 읽어오기"""
    ws = get_worksheet(sheet_name)
    data = ws.get_all_records()
    if not data:
        # 데이터가 없을 때 빈 DataFrame 반환 (컬럼 구조 유지)
        if sheet_name == "members":
            return pd.DataFrame(columns=["이름", "성별", "생일", "전화번호", "주소", "가족ID", "소그룹", "비고"])
        elif sheet_name == "attendance_log":
            return pd.DataFrame(columns=["날짜", "모임명", "이름", "소그룹", "출석여부"])
        elif sheet_name == "users":
            return pd.DataFrame(columns=["아이디", "비밀번호", "이름", "역할", "담당소그룹"])
    
    # 모든 데이터를 문자열로 처리 (오류 방지)
    df = pd.DataFrame(data)
    return df.astype(str)

def save_data(sheet_name, df):
    """구글 시트에 데이터 저장하기 (덮어쓰기)"""
    ws = get_worksheet(sheet_name)
    ws.clear() # 기존 데이터 지우기
    # 컬럼 이름 추가
    ws.append_row(df.columns.tolist())
    # 데이터 추가
    ws.update(range_name='A2', values=df.values.tolist())

def append_attendance(new_records_df):
    """출석 기록만 끝에 추가하기 (속도 향상)"""
    if new_records_df.empty:
        return
    ws = get_worksheet("attendance_log")
    ws.append_rows(new_records_df.values.tolist())

# --- 로그인 세션 ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None

def login(username, password):
    df_users = load_data("users")
    # 비밀번호 매칭 확인
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
    st.title(f"⛪ 회정교회 출석체크 시스템")

    # 사이드바 로그인
    with st.sidebar:
        st.header("로그인")
        if not st.session_state["logged_in"]:
            input_id = st.text_input("아이디")
            input_pw = st.text_input("비밀번호", type="password")
            if st.button("로그인"):
                login(input_id, input_pw)
            st.caption("※ 초기 설정: admin / 1234 (구글 시트 'users' 탭에서 변경)")
        else:
            user = st.session_state["user_info"]
            st.success(f"환영합니다! {user['이름']}님")
            if st.button("로그아웃"):
                logout()

    if not st.session_state["logged_in"]:
        st.warning("👈 사이드바에서 로그인해주세요.")
        st.stop()

    # 데이터 로드
    current_user = st.session_state["user_info"]
    is_admin = (current_user["역할"] == "admin")
    
    df_members = load_data("members")
    df_att = load_data("attendance_log") # 전체 기록 로드

    # 탭 구성
    tabs_list = ["📋 출석체크", "📊 통계 확인", "👥 명단 관리"]
    if is_admin:
        tabs_list.append("🔐 계정 관리")
    
    tabs = st.tabs(tabs_list)

    # --- TAB 1: 출석체크 ---
    with tabs[0]:
        st.subheader("모임 출석 확인")
        c1, c2 = st.columns(2)
        
        # [기능 유지] 날짜 및 요일 표시
        check_date = c1.date_input("날짜 선택", datetime.date.today())
        weekdays = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
        korean_day = weekdays[check_date.weekday()]
        
        if korean_day == "(일)":
            c1.markdown(f":red[**오늘은 {korean_day}요일 입니다.**]") 
        else:
            c1.caption(f"선택한 날짜는 **{korean_day}요일** 입니다.")

        meeting_name = c2.selectbox("모임", ["주일 1부", "주일 2부", "주일 오후", "수요예배", "금요철야", "새벽예배"])

        # --- [업그레이드] 소그룹 선택 로직 (다중 소그룹 지원) ---
        all_groups = sorted(df_members["소그룹"].unique()) if not df_members.empty else []
        
        if is_admin:
            selected_group = st.selectbox("소그룹 (관리자)", ["전체 보기"] + list(all_groups))
        else:
            # 1. 쉼표(,)로 구분된 소그룹을 리스트로 분리 (예: "사랑, 믿음" -> ["사랑", "믿음"])
            raw_groups = str(current_user["담당소그룹"])
            my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
            
            # 2. 맡은 그룹이 2개 이상이면 선택 박스 표시
            if len(my_groups) > 1:
                selected_group = st.selectbox("📌 관리할 소그룹을 선택하세요", my_groups)
            elif len(my_groups) == 1:
                selected_group = my_groups[0]
                st.info(f"📌 담당: {selected_group}")
            else:
                st.error("담당 소그룹이 설정되지 않았습니다.")
                selected_group = None

        # --- 명단 필터링 및 출석 체크 UI (기존과 동일) ---
        if selected_group and selected_group != "전체 보기":
            target_members = df_members[df_members["소그룹"] == selected_group]
        elif selected_group == "전체 보기":
            target_members = df_members
        else:
            target_members = pd.DataFrame() # 선택 안됨

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
                    # 전체 데이터에서 (오늘날짜 + 모임 + 현재선택된소그룹) 데이터만 제거 후 재저장
                    # (다른 소그룹 데이터는 건드리지 않음)
                    mask = (
                        (df_att["날짜"] == str(check_date)) & 
                        (df_att["모임명"] == meeting_name) & 
                        (df_att["소그룹"] == selected_group)  # 중요: 현재 선택된 그룹만 갱신
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
            st.info("아직 데이터가 없습니다.")
        else:
            # 데이터 전처리 (날짜 형식 통일)
            df_att["날짜"] = pd.to_datetime(df_att["날짜"], errors='coerce')
            df_att["연도"] = df_att["날짜"].dt.year
            df_att["월"] = df_att["날짜"].dt.strftime("%Y-%m")

            # --- [기능 1] 전체 통계 (기존 기능) ---
            st.markdown("### 📊 전체 현황")
            stat_mode = st.radio("보기 방식", ["월별 추세", "소그룹별 출석왕"], horizontal=True)
            
            if stat_mode == "월별 추세":
                # 전체 출석 인원 추이
                daily_counts = df_att.groupby("월")["이름"].count()
                st.line_chart(daily_counts)
            else:
                # 소그룹별로 누가 많이 왔나
                if is_admin:
                    # 관리자는 전체 보기
                    group_stat = df_att.groupby("소그룹")["이름"].count().reset_index(name="총 출석수")
                    st.bar_chart(group_stat.set_index("소그룹"))
                else:
                    # 리더는 우리 그룹만
                    my_group_att = df_att[df_att["소그룹"] == current_user["담당소그룹"]]
                    member_counts = my_group_att["이름"].value_counts().reset_index()
                    member_counts.columns = ["이름", "출석횟수"]
                    st.dataframe(member_counts, use_container_width=True)

            st.divider()

            # --- [기능 2] 👤 개인별 상세 이력 (새로 추가된 기능!) ---
            if is_admin:
                st.markdown("### 👤 개인별 출석 히스토리 (관리자 전용)")
                st.caption("특정 성도가 연도별로 어느 소그룹에 있었고, 얼마나 출석했는지 확인합니다.")

                # 검색창 만들기
                search_person = st.selectbox("성도 이름 선택", ["선택해주세요"] + sorted(df_att["이름"].unique()))
                
                if search_person != "선택해주세요":
                    # 선택한 사람의 기록만 뽑기
                    person_history = df_att[df_att["이름"] == search_person]
                    
                    # [핵심 로직] 연도별 + 소그룹별로 묶어서 보여주기
                    # 예: 2026년 사랑목장 50회 / 2027년 믿음목장 2회
                    history_summary = person_history.groupby(["연도", "소그룹"])["출석여부"].count().reset_index()
                    history_summary.columns = ["연도", "당시 소그룹", "출석 횟수"]
                    
                    st.write(f"**📘 {search_person}님의 연도별 활동 내역**")
                    st.table(history_summary)
                    
                    # 상세 날짜별 기록 펼쳐보기
                    with st.expander(f"{search_person}님의 전체 출석 날짜 보기"):
                        st.dataframe(
                            person_history[["날짜", "모임명", "소그룹", "출석여부"]].sort_values(by="날짜", ascending=False),
                            use_container_width=True
                        )
    # --- TAB 3: 명단 관리 ---
    with tabs[2]:
        st.subheader("명단 관리")
        
        # [업그레이드] 다중 소그룹 권한 처리
        if is_admin:
            edit_target = df_members
        else:
            # 리더가 맡은 모든 그룹의 사람들을 가져옵니다.
            raw_groups = str(current_user["담당소그룹"])
            my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
            
            # 내 그룹들에 속한 사람들만 필터링
            edit_target = df_members[df_members["소그룹"].isin(my_groups)]
            
            if len(my_groups) > 1:
                st.info(f"📋 담당 그룹({len(my_groups)}개): {', '.join(my_groups)} 명단을 관리합니다.")
            else:
                st.info(f"📋 담당 그룹: {my_groups[0]}")

        edited = st.data_editor(edit_target, num_rows="dynamic", use_container_width=True)
        
        if st.button("명단 저장"):
            if is_admin:
                save_data("members", edited)
            else:
                # [안전 로직]
                # 1. 전체 데이터에서 '내 담당 그룹'에 속했던 사람들을 일단 뺍니다.
                # (리더가 맡은 그룹이 아닌 사람들은 건드리지 않기 위해)
                raw_groups = str(current_user["담당소그룹"])
                my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
                
                mask = df_members["소그룹"].isin(my_groups)
                other_people = df_members[~mask]
                
                # 2. 내가 수정한 데이터(edited)와 합칩니다.
                final = pd.concat([other_people, edited], ignore_index=True)
                save_data("members", final)
                
            st.success("명단이 업데이트되었습니다!")
            st.rerun()

    # --- TAB 4: 계정 관리 ---
    if is_admin:
        with tabs[3]:
            st.subheader("계정 관리 (구글 시트: users 탭)")
            df_users = load_data("users")
            edited_users = st.data_editor(df_users, num_rows="dynamic", use_container_width=True)
            if st.button("계정 저장"):
                save_data("users", edited_users)
                st.success("계정 정보 저장됨")
                st.rerun()

if __name__ == "__main__":
    main()




