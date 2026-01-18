import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- [설정] 구글 시트 파일 이름 ---
SHEET_NAME = "교회출석데이터"

# 페이지 기본 설정
st.set_page_config(page_title="회정교회", layout="wide", initial_sidebar_state="collapsed")

# --- 구글 시트 연결 함수 ---
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
        st.error(f"오류: 구글 시트 '{SHEET_NAME}'을 찾을 수 없습니다. 공유 설정을 확인해주세요.")
        return None

# --- 데이터 읽기/쓰기 함수 ---
def load_data(sheet_name):
    ws = get_worksheet(sheet_name)
    if not ws: return pd.DataFrame()
    
    data = ws.get_all_records()
    
    if not data:
        # 빈 데이터프레임 생성 (구조 유지)
        if sheet_name == "members":
            return pd.DataFrame(columns=["이름", "성별", "생일", "전화번호", "주소", "가족ID", "소그룹", "비고"])
        elif sheet_name == "attendance_log":
            return pd.DataFrame(columns=["날짜", "모임명", "이름", "소그룹", "출석여부"])
        elif sheet_name == "users":
            return pd.DataFrame(columns=["아이디", "비밀번호", "이름", "역할", "담당소그룹"])
        elif sheet_name == "prayer_log":
            return pd.DataFrame(columns=["날짜", "이름", "소그룹", "내용", "작성자"])
    
    df = pd.DataFrame(data)
    return df.astype(str)

def save_data(sheet_name, df):
    ws = get_worksheet(sheet_name)
    if ws:
        ws.clear()
        ws.append_row(df.columns.tolist())
        ws.update(range_name='A2', values=df.values.tolist())

# --- 날짜 관련 헬퍼 함수 ---
def get_week_range(date_obj):
    """선택한 날짜가 포함된 일요일~토요일 범위를 반환"""
    idx = (date_obj.weekday() + 1) % 7
    start_sunday = date_obj - datetime.timedelta(days=idx)
    end_saturday = start_sunday + datetime.timedelta(days=6)
    return start_sunday, end_saturday

# --- 로그인 시스템 ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None

def login(username, password):
    df_users = load_data("users")
    if df_users.empty:
        st.error("사용자 데이터가 없습니다.")
        return

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
    st.title("⛪ 회정교회 출석체크 시스템")

    # 사이드바 로그인 UI
    with st.sidebar:
        st.header("로그인")
        if not st.session_state["logged_in"]:
            input_id = st.text_input("아이디", key="login_id")
            input_pw = st.text_input("비밀번호", type="password", key="login_pw")
            if st.button("로그인", key="login_btn"):
                login(input_id, input_pw)
            st.caption("※ 초기 설정: admin / 1234")
        else:
            user = st.session_state["user_info"]
            st.success(f"환영합니다! {user['이름']}님")
            st.caption(f"권한: {user['역할']}")
            if st.button("로그아웃", key="logout_btn"):
                logout()

    if not st.session_state["logged_in"]:
        st.warning("👈 사이드바에서 로그인해주세요.")
        st.stop()

    # 데이터 로드
    current_user = st.session_state["user_info"]
    is_admin = (current_user["역할"] == "admin")
    
    with st.spinner('데이터를 불러오는 중입니다...'):
        df_members = load_data("members")
        df_att = load_data("attendance_log")
        df_prayer = load_data("prayer_log")

    # 탭 구성
    tabs_list = ["🏠 홈 (대시보드)", "📋 출석체크", "📊 통계", "🙏 기도제목", "👥 명단 관리"]
    if is_admin:
        tabs_list.append("🔐 계정 관리")
    
    tabs = st.tabs(tabs_list)

    # --- TAB 1: 홈 (대시보드 & 생일) ---
    with tabs[0]:
        st.subheader(f"🎉 {datetime.date.today().month}월 생일자 명단")
        
        if df_members.empty:
            st.info("등록된 성도 데이터가 없습니다.")
        else:
            try:
                # [수정] 원본 데이터를 더럽히지 않도록 복사본(temp_df)을 만들어서 계산
                temp_df = df_members.copy()
                
                # 생일 데이터 처리 (YYYY-MM-DD 형식에서 월 추출)
                temp_df["생일_월"] = temp_df["생일"].astype(str).apply(
                    lambda x: x.split("-")[1] if "-" in x and len(x.split("-")) >= 2 else None
                )
                
                current_month_str = str(datetime.date.today().month).zfill(2)
                birthday_people = temp_df[temp_df["생일_월"] == current_month_str]

                if not birthday_people.empty:
                    # 일자별 정렬
                    birthday_people["생일_일"] = birthday_people["생일"].apply(lambda x: x.split("-")[-1])
                    birthday_people = birthday_people.sort_values("생일_일")
                    
                    # 카드 형태로 보여주기
                    b_cols = st.columns(4)
                    for idx, row in birthday_people.iterrows():
                        with b_cols[idx % 4]:
                            st.info(
                                f"**{row['이름']}** ({row['성별']})\n\n"
                                f"🎂 {int(row['생일_월'])}월 {int(row['생일_일'])}일\n\n"
                                f"🏷️ {row['소그룹']}"
                            )
                else:
                    st.write("이번 달 생일자가 없습니다.")
            except Exception as e:
                # 데이터 형식이 안 맞을 경우 에러 방지
                st.warning("생일 정보 형식을 확인해주세요. (예: 1986-05-02)")

        st.divider()
        st.markdown("### 👋 환영합니다")
        st.write(f"오늘 날짜: **{datetime.date.today().strftime('%Y년 %m월 %d일')}**")
        st.write("상단 탭을 눌러 출석체크 및 관리를 진행해주세요.")

    # --- TAB 2: 출석체크 ---
    with tabs[1]:
        st.subheader("모임 출석 확인")
        c1, c2 = st.columns(2)
        
        # [Key 추가] 날짜 선택
        check_date = c1.date_input("날짜 선택", datetime.date.today(), key="att_date_picker")
        weekdays = ["(월)", "(화)", "(수)", "(목)", "(금)", "(토)", "(일)"]
        korean_day = weekdays[check_date.weekday()]
        
        if korean_day == "(일)":
            c1.markdown(f":red[**오늘은 {korean_day}요일 입니다.**]") 
        else:
            c1.caption(f"선택한 날짜는 **{korean_day}요일** 입니다.")

        meeting_list = ["주일 1부", "주일 2부", "주일 오후", "소그룹 모임", "수요예배", "금요철야", "새벽기도"]
        # [Key 추가] 모임 선택
        meeting_name = c2.selectbox("모임", meeting_list, key="att_meeting_select")

        # 소그룹 선택 로직
        all_groups = sorted(df_members["소그룹"].unique()) if not df_members.empty else []
        
        if is_admin:
            # [Key 추가] 관리자용 그룹 선택
            selected_group = st.selectbox("소그룹 (관리자)", ["전체 보기"] + list(all_groups), key="att_group_admin")
        else:
            raw_groups = str(current_user["담당소그룹"])
            my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
            
            if len(my_groups) > 1:
                # [Key 추가] 리더용 그룹 선택
                selected_group = st.selectbox("📌 관리할 소그룹을 선택하세요", my_groups, key="att_group_leader")
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
                    status_dict[name] = cols[idx % 3].checkbox(name, value=is_checked, key=f"chk_{idx}_{name}")
                
                # [Key 추가] 저장 버튼
                if st.form_submit_button("저장하기", use_container_width=True):
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

    # --- TAB 3: 통계 (주간 리포트) ---
    with tabs[2]:
        st.subheader("📊 주간 사역 통계")
        
        if df_att.empty:
            st.info("아직 출석 데이터가 없습니다.")
        else:
            df_att["날짜"] = pd.to_datetime(df_att["날짜"], errors='coerce')
            
            col_stat1, col_stat2 = st.columns(2)
            
            # [Key 추가] 통계 날짜 선택
            stat_date = col_stat1.date_input("기준 날짜 선택 (해당 주간을 조회)", datetime.date.today(), key="stat_date_picker")
            start_sun, end_sat = get_week_range(stat_date)
            col_stat1.caption(f"📅 조회 기간: {start_sun.strftime('%m/%d')}(일) ~ {end_sat.strftime('%m/%d')}(토)")

            if is_admin:
                all_grps = sorted(df_att["소그룹"].unique())
                # [Key 추가] 통계 그룹 선택 (관리자)
                stat_group = col_stat2.selectbox("조회할 소그룹", ["전체 합계"] + all_grps, key="stat_group_admin")
            else:
                raw_groups = str(current_user["담당소그룹"])
                my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
                if len(my_groups) > 1:
                    # [Key 추가] 통계 그룹 선택 (리더)
                    stat_group = col_stat2.selectbox("소그룹 선택", my_groups, key="stat_group_leader")
                else:
                    stat_group = my_groups[0]
                    col_stat2.info(f"담당: {stat_group}")

            mask_date = (df_att["날짜"] >= pd.Timestamp(start_sun)) & (df_att["날짜"] <= pd.Timestamp(end_sat))
            weekly_df = df_att[mask_date]

            if stat_group != "전체 합계":
                weekly_df = weekly_df[weekly_df["소그룹"] == stat_group]

            st.divider()

            if weekly_df.empty:
                st.warning(f"해당 기간({start_sun.strftime('%m/%d')}~{end_sat.strftime('%m/%d')})에 출석 기록이 없습니다.")
            else:
                st.markdown(f"**📉 {stat_group} - 이번 주 모임별 출석 현황**")
                
                meeting_counts = weekly_df["모임명"].value_counts().reset_index()
                meeting_counts.columns = ["모임명", "출석인원"]
                st.bar_chart(meeting_counts.set_index("모임명"))

                with st.expander("상세 데이터 표 보기"):
                    st.dataframe(meeting_counts, use_container_width=True)

                st.divider()

                st.markdown(f"**🏆 {stat_group} 성실 출석왕 (이번 주)**")
                member_rank = weekly_df["이름"].value_counts().reset_index()
                member_rank.columns = ["이름", "총 참석횟수"]
                
                if not member_rank.empty:
                    top_score = member_rank.iloc[0]["총 참석횟수"]
                    top_members = member_rank[member_rank["총 참석횟수"] == top_score]["이름"].tolist()
                    st.success(f"🎉 1등: {', '.join(top_members)} ({top_score}회 참석)")
                
                st.dataframe(member_rank, use_container_width=True)

    # --- TAB 4: 기도제목 ---
    with tabs[3]:
        st.subheader("🙏 소그룹원 기도제목 관리")
        
        if is_admin:
            grp_list = sorted(df_members["소그룹"].unique())
            # [Key 추가] 기도제목 그룹 선택 (관리자)
            p_group = st.selectbox("소그룹 선택 (기도제목)", grp_list, key="prayer_group_admin")
        else:
            raw_groups = str(current_user["담당소그룹"])
            my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
            if len(my_groups) > 1:
                # [Key 추가] 기도제목 그룹 선택 (리더) - 여기가 에러 원인이었음!
                p_group = st.selectbox("소그룹 선택", my_groups, key="prayer_group_leader")
            elif len(my_groups) == 1:
                p_group = my_groups[0]
            else:
                p_group = None
        
        if p_group:
            p_members = df_members[df_members["소그룹"] == p_group]["이름"].tolist()
            if not p_members:
                st.warning("등록된 멤버가 없습니다.")
            else:
                # [Key 추가] 멤버 선택
                p_name = st.selectbox("이름을 선택하세요", p_members, key="prayer_member_select")
                
                with st.expander(f"✏️ {p_name}님 새 기도제목 입력하기", expanded=True):
                    with st.form("prayer_input"):
                        # [Key 추가] 기도 날짜
                        p_date = st.date_input("기도 요청 날짜", datetime.date.today(), key="prayer_date_input")
                        # [Key 추가] 기도 내용
                        p_content = st.text_area("기도제목 내용", height=100, placeholder="내용을 입력하세요...", key="prayer_content_input")
                        
                        # [Key 추가] 저장 버튼
                        if st.form_submit_button("저장하기"):
                            if p_content.strip() == "":
                                st.error("내용을 입력해주세요.")
                            else:
                                new_prayer = pd.DataFrame([{
                                    "날짜": str(p_date),
                                    "이름": p_name,
                                    "소그룹": p_group,
                                    "내용": p_content,
                                    "작성자": current_user["이름"]
                                }])
                                save_data("prayer_log", pd.concat([df_prayer, new_prayer], ignore_index=True))
                                st.success("저장되었습니다!")
                                st.rerun()

                st.divider()
                st.markdown(f"**📖 {p_name}님의 기도제목 히스토리**")
                
                my_prayers = df_prayer[df_prayer["이름"] == p_name]
                if my_prayers.empty:
                    st.info("아직 등록된 기도제목이 없습니다.")
                else:
                    my_prayers = my_prayers.sort_values(by="날짜", ascending=False)
                    for idx, row in my_prayers.iterrows():
                        st.info(f"**📅 {row['날짜']}**\n\n{row['내용']}")

    # --- TAB 5: 명단 관리 ---
    with tabs[4]:
        st.subheader("명단 관리")
        if is_admin:
            edit_target = df_members
        else:
            raw_groups = str(current_user["담당소그룹"])
            my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
            edit_target = df_members[df_members["소그룹"].isin(my_groups)]
            
            if len(my_groups) > 1:
                st.info(f"📋 담당 그룹({len(my_groups)}개): {', '.join(my_groups)} 통합 관리")
            else:
                st.info(f"📋 담당 그룹: {my_groups[0]}")

        # [Key 추가] 에디터
        edited = st.data_editor(edit_target, num_rows="dynamic", use_container_width=True, key="member_editor")
        
        # [Key 추가] 저장 버튼
        if st.button("명단 저장", key="member_save_btn"):
            if is_admin:
                save_data("members", edited)
            else:
                raw_groups = str(current_user["담당소그룹"])
                my_groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
                mask = df_members["소그룹"].isin(my_groups)
                other_people = df_members[~mask]
                final = pd.concat([other_people, edited], ignore_index=True)
                save_data("members", final)
            st.success("명단이 업데이트되었습니다!")
            st.rerun()

    # --- TAB 6: 계정 관리 (관리자만) ---
    if is_admin:
        with tabs[5]:
            st.subheader("계정 관리")
            df_users = load_data("users")
            edited_users = st.data_editor(df_users, num_rows="dynamic", use_container_width=True, key="user_editor")
            if st.button("계정 저장", key="user_save_btn"):
                save_data("users", edited_users)
                st.success("계정 정보 저장됨")
                st.rerun()

if __name__ == "__main__":
    main()

