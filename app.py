import streamlit as st
import pandas as pd
import datetime
import os

# --- 파일 경로 설정 ---
DATA_FILE = "church_attendance.csv"
LOG_FILE = "attendance_log.csv"
USER_FILE = "users.csv"  # 사용자(관리자/리더) 계정 정보

# 페이지 기본 설정
st.set_page_config(page_title="교회 출석체크", layout="wide", initial_sidebar_state="collapsed")

# --- 데이터 관리 함수들 ---
def load_data():
    """멤버 명단 로드"""
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=["이름", "성별", "생일", "전화번호", "주소", "가족ID", "소그룹", "비고"])
    return pd.read_csv(DATA_FILE)

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def load_attendance():
    """출석 기록 로드"""
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame(columns=["날짜", "모임명", "이름", "소그룹", "출석여부"])
    return pd.read_csv(LOG_FILE)

def save_attendance(df):
    df.to_csv(LOG_FILE, index=False)

def load_users():
    """사용자(관리자/리더) 목록 로드"""
    if not os.path.exists(USER_FILE):
        # 초기 관리자 계정 생성 (아이디: admin / 비번: 1234)
        df = pd.DataFrame([
            {"아이디": "admin", "비밀번호": "1234", "이름": "전체관리자", "역할": "admin", "담당소그룹": "전체"}
        ])
        df.to_csv(USER_FILE, index=False)
        return df
    return pd.read_csv(USER_FILE, dtype=str) # 비밀번호 등 문자열로 처리

def save_users(df):
    df.to_csv(USER_FILE, index=False)

# --- 로그인 세션 관리 ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_info"] = None

def login(username, password):
    users = load_users()
    matched = users[(users["아이디"] == username) & (users["비밀번호"] == password)]
    
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

    # 1. 사이드바: 로그인/로그아웃 처리
    with st.sidebar:
        st.header("로그인")
        
        if not st.session_state["logged_in"]:
            input_id = st.text_input("아이디")
            input_pw = st.text_input("비밀번호", type="password")
            if st.button("로그인"):
                login(input_id, input_pw)
            st.info("초기 관리자 ID: admin / PW: 1234")
        else:
            user = st.session_state["user_info"]
            st.success(f"환영합니다! {user['이름']}님")
            st.caption(f"권한: {user['역할']}")
            if user['역할'] == 'leader':
                st.caption(f"담당: {user['담당소그룹']}")
                
            if st.button("로그아웃"):
                logout()

    # 로그인 안 되어 있으면 중단
    if not st.session_state["logged_in"]:
        st.warning("👈 사이드바에서 로그인 후 이용해주세요.")
        st.stop()

    # 현재 접속자 정보
    current_user = st.session_state["user_info"]
    is_admin = (current_user["역할"] == "admin")
    
    # 탭 구성 (관리자만 '계정 관리' 탭 보임)
    tabs = ["📋 출석체크", "📊 통계 확인", "👥 명단 관리"]
    if is_admin:
        tabs.append("🔐 리더 계정 관리")
    
    current_tab = st.tabs(tabs)

    df_members = load_data()
    df_att = load_attendance()

    # --- TAB 1: 출석체크 ---
    with current_tab[0]:
        st.subheader("모임 출석 확인")
        col1, col2 = st.columns(2)
        with col1:
            check_date = st.date_input("날짜", datetime.date.today())
        with col2:
            meeting_name = st.selectbox("모임", ["주일 1부", "주일 2부", "주일 오후", "수요예배", "금요철야", "새벽예배"])

        # 소그룹 선택 로직 (핵심 변경 사항)
        all_groups = sorted(df_members["소그룹"].astype(str).unique()) if not df_members.empty else []
        
        if is_admin:
            # 관리자는 모든 그룹 선택 가능
            selected_group = st.selectbox("소그룹 선택 (관리자)", ["전체 보기"] + list(all_groups))
        else:
            # 리더는 자기 그룹만 강제 선택
            my_group = current_user["담당소그룹"]
            st.info(f"📌 담당 소그룹: **{my_group}**")
            selected_group = my_group

        # 명단 필터링
        if selected_group != "전체 보기":
            target_members = df_members[df_members["소그룹"] == selected_group]
        else:
            target_members = df_members

        # 출석 체크 UI
        if target_members.empty:
            st.warning("표시할 명단이 없습니다.")
        else:
            current_att_log = df_att[(df_att["날짜"] == str(check_date)) & (df_att["모임명"] == meeting_name)]
            
            with st.form("att_form"):
                st.write(f"**{selected_group}** 명단 ({len(target_members)}명)")
                cols = st.columns(3)
                status_dict = {}
                
                for idx, row in target_members.iterrows():
                    name = row["이름"]
                    is_present = not current_att_log[current_att_log["이름"] == name].empty
                    status_dict[name] = cols[idx % 3].checkbox(name, value=is_present)
                
                if st.form_submit_button("저장하기", use_container_width=True):
                    new_rows = []
                    for name, checked in status_dict.items():
                        if checked:
                            mem_info = df_members[df_members["이름"] == name].iloc[0]
                            new_rows.append({
                                "날짜": str(check_date), "모임명": meeting_name,
                                "이름": name, "소그룹": mem_info["소그룹"], "출석여부": "출석"
                            })
                    
                    # 기존 데이터 삭제 후 갱신
                    clean_log = df_att[~((df_att["날짜"] == str(check_date)) & (df_att["모임명"] == meeting_name) & (df_att["소그룹"].isin(target_members["소그룹"].unique())))]
                    final_log = pd.concat([clean_log, pd.DataFrame(new_rows)], ignore_index=True)
                    save_attendance(final_log)
                    st.success("저장 완료!")
                    st.rerun()

    # --- TAB 2: 통계 ---
    with current_tab[1]:
        st.subheader("통계")
        if df_att.empty:
            st.info("데이터 없음")
        else:
            # 리더는 자기 그룹 통계만 봄 (선택사항)
            if not is_admin:
                view_df = df_att[df_att["소그룹"] == current_user["담당소그룹"]]
            else:
                view_df = df_att
                
            view_df["날짜"] = pd.to_datetime(view_df["날짜"])
            view_df["월"] = view_df["날짜"].dt.strftime("%Y-%m")
            
            mode = st.radio("보기", ["월별 추세", "인원별 출석률"])
            if mode == "월별 추세":
                st.line_chart(view_df.groupby("월")["이름"].count())
            else:
                counts = view_df["이름"].value_counts().reset_index()
                counts.columns = ["이름", "출석횟수"]
                st.dataframe(counts, use_container_width=True)

    # --- TAB 3: 명단 관리 ---
    with current_tab[2]:
        st.subheader("그룹원 명단 관리")
        
        # 리더는 자기 그룹원만 수정 가능하게 필터링
        if is_admin:
            edit_target = df_members
        else:
            edit_target = df_members[df_members["소그룹"] == current_user["담당소그룹"]]
            st.info(f"⚠️ {current_user['담당소그룹']} 그룹원만 수정할 수 있습니다.")

        edited = st.data_editor(edit_target, num_rows="dynamic", use_container_width=True)
        
        if st.button("명단 변경사항 저장"):
            if is_admin:
                save_data(edited)
            else:
                # 리더가 수정한 부분만 전체 데이터에 반영하는 로직 (조금 복잡하지만 안전하게)
                # 리더는 자기 소그룹 사람만 건드렸으므로, 전체 데이터에서 해당 소그룹 사람들을 빼고
                # 수정한 데이터를 끼워넣음
                my_grp = current_user["담당소그룹"]
                other_groups = df_members[df_members["소그룹"] != my_grp]
                final_merge = pd.concat([other_groups, edited], ignore_index=True)
                save_data(final_merge)
                
            st.success("저장되었습니다.")
            st.rerun()

    # --- TAB 4: (관리자 전용) 계정 관리 ---
    if is_admin:
        with current_tab[3]:
            st.subheader("🔐 소그룹 리더 계정 관리")
            st.markdown("여기서 소그룹 리더의 **아이디/비밀번호**와 **담당 소그룹**을 설정합니다.")
            
            users_df = load_users()
            
            # 리더 계정 추가/수정 에디터
            # 관리자는 수정 못하게 막거나 주의 필요. 여기서는 자유롭게 수정 가능.
            edited_users = st.data_editor(users_df, num_rows="dynamic", use_container_width=True)
            
            if st.button("계정 정보 저장"):
                save_users(edited_users)
                st.success("계정 정보가 업데이트되었습니다.")
                st.rerun()
            
            st.info("""
            **[사용법]**
            1. 새 리더를 추가하려면 표 아래 `+`를 누르세요.
            2. **역할**: `leader` (소문자)라고 적으세요. (`admin`은 전체 관리자)
            3. **담당소그룹**: '명단 관리'에 있는 소그룹 이름과 **띄어쓰기까지 똑같이** 적어야 합니다.
            """)

if __name__ == "__main__":
    main()
