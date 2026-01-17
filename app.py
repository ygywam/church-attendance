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
        
        # [수정] 날짜 선택 및 요일 표시 기능
        check_date = c1.date_input("날짜 선택", datetime.date.today())
        
        weekdays = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
        korean_day = weekdays[check_date.weekday()]
        
        # 요일 표출 (일요일은 빨간색 강조)
        if korean_day == "(일)":
            c1.markdown(f":red[**오늘은 {korean_day}요일 입니다.**]") 
        else:
            c1.caption(f"선택한 날짜는 **{korean_day}요일** 입니다.")

        meeting_name = c2.selectbox("모임", ["주일 1부", "주일 2부", "주일 오후", "수요예배", "금요철야", "새벽예배"])

        all_groups = sorted(df_members["소그룹"].unique()) if not df_members.empty else []
        
        if is_admin:
            selected_group = st.selectbox("소그룹 (관리자)", ["전체 보기"] + list(all_groups))
        else:
            selected_group = current_user["담당소그룹"]
            st.info(f"📌 담당: {selected_group}")

        if selected_group != "전체 보기":
            target_members = df_members[df_members["소그룹"] == selected_group]
        else:
            target_members = df_members

        if not target_members.empty:
            # 현재 날짜/모임의 기존 출석자 명단 추출
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
                    # 1. 변화된 내용 계산
                    new_records = []
                    
                    # 해당 그룹의 기존 기록 삭제를 위해 필터링 필요 (복잡도 감소를 위해 덮어쓰기 대신 추가 방식 사용 권장하나, 정확성을 위해 삭제 후 재입력 로직 적용)
                    # 구글 시트에서는 '부분 삭제'가 어려우므로, 이 날짜/이 모임/이 그룹의 기존 데이터를 메모리에서 지우고 전체를 다시 저장하는 것은 너무 느림.
                    # 따라서 '추가(Append)'만 하되, 통계 낼 때 중복 제거하는 방식 or 
                    # 관리 편의를 위해 여기서는 [기존 전체 로드 -> 해당 부분 삭제 -> 추가 -> 전체 저장] 방식을 씁니다. (데이터 2000행 이하는 3~5초 소요됨)
                    
                    # 전체 데이터에서 (오늘날짜 + 지금모임 + 지금소그룹)에 해당하는 사람들을 일단 뺍니다.
                    mask = (
                        (df_att["날짜"] == str(check_date)) & 
                        (df_att["모임명"] == meeting_name) & 
                        (df_att["소그룹"].isin(target_members["소그룹"].unique()))
                    )
                    df_clean = df_att[~mask]

                    # 체크된 사람만 새로 리스트 생성
                    for name, checked in status_dict.items():
                        if checked:
                            grp = df_members[df_members["이름"]==name].iloc[0]["소그룹"]
                            new_records.append({
                                "날짜": str(check_date), "모임명": meeting_name,
                                "이름": name, "소그룹": grp, "출석여부": "출석"
                            })
                    
                    # 합치기
                    df_final = pd.concat([df_clean, pd.DataFrame(new_records)], ignore_index=True)
                    
                    # 구글 시트에 저장
                    save_data("attendance_log", df_final)
                    st.success("구글 시트에 저장되었습니다!")
                    st.rerun()

    # --- TAB 2: 통계 ---
    with tabs[1]:
        st.subheader("통계")
        if df_att.empty:
            st.info("데이터 없음")
        else:
            view_df = df_att if is_admin else df_att[df_att["소그룹"] == current_user["담당소그룹"]]
            # 날짜 변환
            view_df["날짜"] = pd.to_datetime(view_df["날짜"], errors='coerce')
            view_df["월"] = view_df["날짜"].dt.strftime("%Y-%m")
            
            mode = st.radio("보기", ["월별 추세", "인원별"])
            if mode == "월별 추세":
                st.line_chart(view_df.groupby("월")["이름"].count())
            else:
                st.dataframe(view_df["이름"].value_counts(), use_container_width=True)

    # --- TAB 3: 명단 관리 ---
    with tabs[2]:
        st.subheader("명단 관리 (구글 시트 연동)")
        
        edit_target = df_members if is_admin else df_members[df_members["소그룹"] == current_user["담당소그룹"]]
        edited = st.data_editor(edit_target, num_rows="dynamic", use_container_width=True)
        
        if st.button("명단 저장"):
            if is_admin:
                save_data("members", edited)
            else:
                # 리더는 자기 것만 수정 -> 전체와 병합
                my_grp = current_user["담당소그룹"]
                other = df_members[df_members["소그룹"] != my_grp]
                final = pd.concat([other, edited], ignore_index=True)
                save_data("members", final)
            st.success("업데이트 완료!")
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


