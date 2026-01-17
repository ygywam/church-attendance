import streamlit as st
import pandas as pd
import datetime
import os

# --- 설정 및 데이터 관리 ---
# 보안을 위해 실제 배포 시에는 비밀번호를 더 복잡하게 설정하세요.
PASSWORD = "church1234"  
DATA_FILE = "church_attendance.csv"
LOG_FILE = "attendance_log.csv"

# 페이지 기본 설정 (모바일 친화적, 제목 설정)
st.set_page_config(page_title="교회 출석체크", layout="wide", initial_sidebar_state="collapsed")

# --- 데이터 로드/저장 함수 ---
def load_data():
    """멤버 명단 불러오기"""
    if not os.path.exists(DATA_FILE):
        # 초기 데이터 구조 생성 (파일이 없을 경우)
        df = pd.DataFrame(columns=[
            "이름", "성별", "생일", "전화번호", "주소", 
            "가족ID", "소그룹", "비고"
        ])
        return df
    return pd.read_csv(DATA_FILE)

def save_data(df):
    """멤버 명단 저장하기"""
    df.to_csv(DATA_FILE, index=False)

def load_attendance():
    """출석 기록 불러오기"""
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame(columns=["날짜", "모임명", "이름", "소그룹", "출석여부"])
    return pd.read_csv(LOG_FILE)

def save_attendance(df):
    """출석 기록 저장하기"""
    df.to_csv(LOG_FILE, index=False)

# --- 메인 앱 로직 ---
def main():
    st.title("⛪ 회교회 출석체크 시스템")

    # [사이드바] 로그인 및 메뉴
    with st.sidebar:
        st.header("관리자 로그인")
        input_pass = st.text_input("비밀번호 입력", type="password")
        is_admin = (input_pass == PASSWORD)
        
        if is_admin:
            st.success("✅ 관리자/리더 권한 확인됨")
            st.info("출석 수정 및 명단 관리가 가능합니다.")
        else:
            st.warning("🔒 조회 모드 (수정 불가)")
            st.caption("비밀번호를 입력하면 출석 체크 및 명단 관리가 가능합니다.")

    # [메인] 탭 구성
    tab1, tab2, tab3 = st.tabs(["📋 출석체크", "📊 통계 확인", "👥 명단 관리"])

    # 데이터 불러오기
    df_members = load_data()
    df_att = load_attendance()

    # --- TAB 1: 출석체크 ---
    with tab1:
        st.subheader("모임 출석 확인")
        
        # 1. 날짜 및 모임 선택
        col1, col2 = st.columns(2)
        with col1:
            check_date = st.date_input("날짜 선택", datetime.date.today())
        with col2:
            # 필요에 따라 모임 목록을 수정하세요
            meeting_options = ["주일 1부", "주일 2부", "주일 오후", "수요예배", "금요철야", "새벽예배"] 
            meeting_name = st.selectbox("모임 선택", meeting_options)

        # 2. 소그룹 필터
        if not df_members.empty:
            groups = sorted(df_members["소그룹"].astype(str).unique())
            selected_group = st.selectbox("소그룹 선택", ["전체 보기"] + list(groups))
        else:
            groups = []
            selected_group = "전체 보기"
            st.error("등록된 명단이 없습니다. '명단 관리' 탭에서 인원을 등록해주세요.")

        # 3. 필터링된 명단 가져오기
        if selected_group != "전체 보기":
            target_members = df_members[df_members["소그룹"] == selected_group]
        else:
            target_members = df_members

        # 4. 해당 날짜/모임의 기존 출석 기록 가져오기
        current_att_log = df_att[
            (df_att["날짜"] == str(check_date)) & 
            (df_att["모임명"] == meeting_name)
        ]
        
        # 5. 출석 체크 UI 생성
        if not target_members.empty:
            with st.form("attendance_form"):
                st.markdown(f"**📌 {selected_group} 명단** ({len(target_members)}명)")
                
                # 모바일 화면을 고려하여 2~3열로 배치
                cols = st.columns(3)
                attendance_status = {}
                
                for idx, row in target_members.iterrows():
                    name = row["이름"]
                    # 기존 기록이 있으면 True(체크됨), 없으면 False
                    is_present = not current_att_log[current_att_log["이름"] == name].empty
                    
                    col_idx = idx % 3
                    if is_admin:
                        # 관리자/리더: 체크박스로 수정 가능
                        attendance_status[name] = cols[col_idx].checkbox(f"{name}", value=is_present)
                    else:
                        # 일반 사용자: 텍스트로 상태만 확인 (개인정보 보호)
                        icon = "✅" if is_present else "⬜"
                        cols[col_idx].write(f"{icon} {name}")

                st.markdown("---")
                
                if is_admin:
                    submit_btn = st.form_submit_button("💾 출석 저장하기", use_container_width=True)
                    if submit_btn:
                        # 1) 현재 화면의 체크 결과 리스트화
                        new_records = []
                        for name, present in attendance_status.items():
                            if present:
                                # 멤버 정보 가져오기 (소그룹 등)
                                member_info = df_members[df_members["이름"] == name].iloc[0]
                                new_records.append({
                                    "날짜": str(check_date),
                                    "모임명": meeting_name,
                                    "이름": name,
                                    "소그룹": member_info["소그룹"],
                                    "출석여부": "출석"
                                })
                        
                        # 2) 기존 데이터에서 [해당 날짜 + 해당 모임] 데이터만 삭제 (덮어쓰기 로직)
                        df_att_clean = df_att[~((df_att["날짜"] == str(check_date)) & (df_att["모임명"] == meeting_name))]
                        
                        # 3) 새 데이터 병합 및 저장
                        df_new = pd.DataFrame(new_records)
                        final_df = pd.concat([df_att_clean, df_new], ignore_index=True)
                        save_attendance(final_df)
                        
                        st.success(f"{len(df_new)}명의 출석이 저장되었습니다!")
                        st.rerun() # 화면 새로고침
                else:
                    st.caption("※ 출석 체크를 하려면 관리자 비밀번호가 필요합니다.")

    # --- TAB 2: 통계 ---
    with tab2:
        st.subheader("📈 출석 통계 현황")
        if df_att.empty:
            st.info("아직 저장된 출석 데이터가 없습니다.")
        else:
            # 날짜 데이터 타입 변환
            df_att["날짜"] = pd.to_datetime(df_att["날짜"])
            df_att["월"] = df_att["날짜"].dt.strftime("%Y-%m")
            
            # 탭 내에서 보기 방식 선택
            stats_type = st.radio("통계 기준", ["소그룹별 현황", "월별 추세"], horizontal=True)
            
            if stats_type == "소그룹별 현황":
                # 소그룹별 총 출석 횟수 집계
                group_counts = df_att.groupby("소그룹")["이름"].count().reset_index(name="총 출석수")
                st.bar_chart(group_counts.set_index("소그룹"))
                st.dataframe(group_counts, use_container_width=True)
                
            elif stats_type == "월별 추세":
                # 월별 총 출석 인원 추세
                monthly_counts = df_att.groupby("월")["이름"].count()
                st.line_chart(monthly_counts)
                st.write("월별 상세 데이터:")
                st.dataframe(monthly_counts, use_container_width=True)

    # --- TAB 3: 명단 관리 (보안 구역) ---
    with tab3:
        if not is_admin:
            st.error("⛔ 접근 권한이 없습니다.")
            st.info("사이드바에서 비밀번호를 입력해주세요.")
        else:
            st.subheader("👥 전체 그룹원 명단 관리")
            
            st.markdown("""
            **사용법:**
            1. 아래 표를 엑셀처럼 직접 클릭해서 수정할 수 있습니다.
            2. 엑셀 파일에서 [이름, 성별, 생일...] 순서로 복사해서 붙여넣기도 가능합니다.
            3. **가족ID**가 같으면 가족 찾기에서 함께 조회됩니다.
            """)
            
            # 데이터 에디터 (행 추가/삭제 가능)
            edited_df = st.data_editor(
                df_members, 
                num_rows="dynamic", 
                use_container_width=True,
                key="member_editor"
            )
            
            col_save, col_fam = st.columns([1, 1])
            
            with col_save:
                if st.button("✅ 명단 변경사항 저장"):
                    save_data(edited_df)
                    st.success("명단이 성공적으로 업데이트되었습니다!")
                    st.rerun()
            
            st.divider()
            
            # 가족 검색 기능
            st.subheader("🔍 가족 관계 조회")
            search_name = st.text_input("이름으로 가족 찾기", placeholder="이름 입력")
            
            if search_name:
                found = df_members[df_members["이름"] == search_name]
                if not found.empty:
                    fam_id = found.iloc[0]["가족ID"]
                    if pd.isna(fam_id) or str(fam_id).strip() == "":
                        st.warning(f"'{search_name}'님은 가족ID가 설정되지 않았습니다.")
                    else:
                        family_members = df_members[df_members["가족ID"] == fam_id]
                        st.success(f"'{search_name}'님의 가족 목록 (가족ID: {fam_id})")
                        st.table(family_members[["이름", "소그룹", "전화번호", "생일"]])
                else:
                    st.error("해당 이름의 멤버를 찾을 수 없습니다.")

if __name__ == "__main__":

    main()
