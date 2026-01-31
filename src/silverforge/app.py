"""SilverForge UI Console

Streamlit 기반 웹 인터페이스
- Supabase 인증 (로그인/회원가입)
- PDF 다중 업로드 (Sidebar)
- 대기 목록에서 바로 처리 + Progress Bar
- 완료 시 결과 영역으로 이동
- 평가 지표 차트 시각화
- Supabase에 결과 저장
"""

import io
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

# Setup path for Streamlit Cloud deployment
_THIS_DIR = Path(__file__).parent.resolve()
_SRC_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _SRC_DIR.parent

# Add both src/ and src/silverforge/ to path
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import streamlit as st
import plotly.graph_objects as go

# Import modules directly (not as package)
from core import process
from curator import curate
import database as db


def inject_custom_css():
    """커스텀 CSS 주입"""
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            max-width: 100%;
        }

        [data-testid="stSidebar"] {
            min-width: 300px;
            max-width: 350px;
        }

        [data-testid="stSidebar"] [data-testid="stFileUploader"] {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 0.5rem;
        }

        [data-testid="stFileUploader"] > div > div {
            max-height: 200px;
            overflow-y: auto;
        }

        /* Main content columns - only when sidebar is present (logged in) */
        [data-testid="stSidebarContent"] ~ [data-testid="stAppViewContainer"] [data-testid="stHorizontalBlock"] > div:first-child {
            border-right: 2px solid #e0e0e0;
            padding-right: 1.5rem;
        }

        [data-testid="stSidebarContent"] ~ [data-testid="stAppViewContainer"] [data-testid="stHorizontalBlock"] > div:last-child {
            padding-left: 1.5rem;
        }

        .stButton > button {
            border-radius: 6px;
        }

        hr {
            margin: 0.75rem 0;
            border: none;
            border-top: 1px solid #e9ecef;
        }

        [data-testid="stMetric"] {
            background: #f8f9fa;
            padding: 0.5rem;
            border-radius: 6px;
        }

        .auth-container {
            max-width: 400px;
            margin: 2rem auto;
            padding: 2rem;
            background: #f8f9fa;
            border-radius: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_session_state():
    """세션 상태 초기화"""
    if "jobs" not in st.session_state:
        st.session_state.jobs = {}
    if "preview_job_id" not in st.session_state:
        st.session_state.preview_job_id = None
    if "processing_job_id" not in st.session_state:
        st.session_state.processing_job_id = None
    if "analysis_job_id" not in st.session_state:
        st.session_state.analysis_job_id = None
    # Auth
    if "user" not in st.session_state:
        st.session_state.user = None
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"


def render_auth_page():
    """로그인/회원가입 페이지 - Notion Style"""
    # Notion-style CSS
    st.markdown(
        """
        <style>
        /* Hide default streamlit elements for cleaner look */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Notion-style form inputs */
        .stTextInput > div > div > input {
            border: 1px solid rgba(55, 53, 47, 0.16) !important;
            border-radius: 4px !important;
            padding: 8px 10px !important;
            font-size: 14px !important;
            transition: border-color 0.2s, box-shadow 0.2s !important;
        }
        .stTextInput > div > div > input:focus {
            border-color: #2eaadc !important;
            box-shadow: 0 0 0 2px rgba(46, 170, 220, 0.2) !important;
        }

        /* Notion-style buttons */
        .stButton > button {
            border-radius: 4px !important;
            font-weight: 500 !important;
            transition: background-color 0.2s !important;
        }
        .stButton > button[kind="primary"] {
            background-color: #2eaadc !important;
            border: none !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #1a9bcd !important;
        }

        /* Consistent input width */
        .stTextInput {
            width: 100% !important;
        }
        .stTextInput > div {
            width: 100% !important;
        }
        .stTextInput > div > div {
            width: 100% !important;
        }
        .stTextInput > div > div > input {
            width: 100% !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

    # Spacer
    st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)

    # Centered container
    col1, col2, col3 = st.columns([1.2, 1.6, 1.2])

    with col2:
        # Logo & Title - Notion style
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 32px;">
                <div style="font-size: 48px; margin-bottom: 16px;">📄</div>
                <h1 style="font-size: 28px; font-weight: 700; color: rgb(55, 53, 47);
                           margin: 0 0 8px 0; letter-spacing: -0.5px;">
                    SilverForge
                </h1>
                <p style="font-size: 14px; color: rgba(55, 53, 47, 0.65); margin: 0;">
                    PDF를 구조화된 Markdown으로 변환하세요
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not db.is_configured():
            st.markdown(
                """
                <p style="text-align: center; color: rgba(55, 53, 47, 0.65);
                          font-size: 14px; margin-bottom: 16px;">
                    Supabase가 설정되지 않았습니다
                </p>
                """,
                unsafe_allow_html=True,
            )
            if st.button("게스트로 계속하기", type="primary", use_container_width=True):
                st.session_state.user = {"id": "guest", "email": "guest@local"}
                st.rerun()
            return

        # Check auth mode
        is_signup = st.session_state.auth_mode == "signup"

        if is_signup:
            # ===== SIGNUP MODE =====
            st.markdown(
                "<p style='font-size: 12px; color: rgba(55, 53, 47, 0.65); margin-bottom: 4px;'>이메일</p>",
                unsafe_allow_html=True,
            )
            email = st.text_input(
                "이메일",
                placeholder="name@company.com",
                label_visibility="collapsed",
                key="signup_email",
            )

            st.markdown(
                "<p style='font-size: 12px; color: rgba(55, 53, 47, 0.65); margin-bottom: 4px; margin-top: 12px;'>비밀번호</p>",
                unsafe_allow_html=True,
            )
            password = st.text_input(
                "비밀번호",
                type="password",
                placeholder="6자 이상",
                label_visibility="collapsed",
                key="signup_password",
            )

            st.markdown(
                "<p style='font-size: 12px; color: rgba(55, 53, 47, 0.65); margin-bottom: 4px; margin-top: 12px;'>비밀번호 확인</p>",
                unsafe_allow_html=True,
            )
            password_confirm = st.text_input(
                "비밀번호 확인",
                type="password",
                placeholder="비밀번호 다시 입력",
                label_visibility="collapsed",
                key="signup_password_confirm",
            )

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

            if st.button("Create Account", type="primary", use_container_width=True):
                if not email or not password:
                    st.warning("이메일과 비밀번호를 입력하세요")
                elif len(password) < 6:
                    st.warning("비밀번호는 6자 이상이어야 합니다")
                elif password != password_confirm:
                    st.warning("비밀번호가 일치하지 않습니다")
                else:
                    with st.spinner(""):
                        result = db.sign_up(email, password)
                    if "error" in result:
                        st.error(result['error'])
                    else:
                        st.success("가입 완료! 이메일을 확인하세요")

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

            if st.button("← Back to Login", use_container_width=True):
                st.session_state.auth_mode = "login"
                st.rerun()

        else:
            # ===== LOGIN MODE =====
            st.markdown(
                "<p style='font-size: 12px; color: rgba(55, 53, 47, 0.65); margin-bottom: 4px;'>이메일</p>",
                unsafe_allow_html=True,
            )
            email = st.text_input(
                "이메일",
                placeholder="name@company.com",
                label_visibility="collapsed",
                key="login_email",
            )

            st.markdown(
                "<p style='font-size: 12px; color: rgba(55, 53, 47, 0.65); margin-bottom: 4px; margin-top: 12px;'>비밀번호</p>",
                unsafe_allow_html=True,
            )
            password = st.text_input(
                "비밀번호",
                type="password",
                placeholder="비밀번호 입력",
                label_visibility="collapsed",
                key="login_password",
            )

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

            btn_col1, btn_col2 = st.columns(2)

            with btn_col1:
                if st.button("Enter", type="primary", use_container_width=True):
                    if email and password:
                        with st.spinner(""):
                            result = db.sign_in(email, password)
                        if "error" in result:
                            st.error(result['error'])
                        else:
                            st.session_state.user = result["user"]
                            st.session_state.access_token = result["session"].access_token
                            st.rerun()
                    else:
                        st.warning("이메일과 비밀번호를 입력하세요")

            with btn_col2:
                if st.button("Create Account", use_container_width=True):
                    st.session_state.auth_mode = "signup"
                    st.rerun()

        # Divider
        st.markdown(
            """
            <div style="display: flex; align-items: center; margin: 20px 0;">
                <div style="flex: 1; height: 1px; background: rgba(55, 53, 47, 0.09);"></div>
                <span style="padding: 0 12px; color: rgba(55, 53, 47, 0.4); font-size: 12px;">또는</span>
                <div style="flex: 1; height: 1px; background: rgba(55, 53, 47, 0.09);"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("게스트로 계속하기", use_container_width=True):
            st.session_state.user = {"id": "guest", "email": "guest@local"}
            st.rerun()

        st.markdown(
            """
            <p style="text-align: center; font-size: 11px; color: rgba(55, 53, 47, 0.4);
                      margin-top: 12px;">
                게스트 모드에서는 데이터가 저장되지 않습니다
            </p>
            """,
            unsafe_allow_html=True,
        )

        # Footer
        st.markdown(
            """
            <div style="text-align: center; margin-top: 32px;">
                <p style="font-size: 11px; color: rgba(55, 53, 47, 0.4);">
                    Powered by Upstage Document Parse & Solar Pro
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def create_job(filename: str, content: bytes) -> str:
    """Job 생성"""
    job_id = f"{int(time.time() * 1000) % 100000:05d}"

    st.session_state.jobs[job_id] = {
        "job_id": job_id,
        "filename": filename,
        "content": content,
        "status": "pending",
        "progress": 0,
        "step": "",
        "markdown": None,
        "quality_score": None,
        "quality_details": None,
        "error": None,
        "created_at": datetime.now(),
        "completed_at": None,
        "saved_to_db": False,
    }

    return job_id


def save_job_to_db(job: dict):
    """Job을 Supabase에 저장"""
    if not db.is_configured():
        return

    user = st.session_state.user
    if not user or user.get("id") == "guest":
        return

    if job.get("saved_to_db"):
        return

    result = db.save_document(
        user_id=user.id if hasattr(user, 'id') else user.get('id'),
        filename=job["filename"],
        markdown=job["markdown"],
        quality_score=job["quality_score"],
        quality_details=job["quality_details"],
    )

    if "error" not in result:
        job["saved_to_db"] = True


def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        # User info
        user = st.session_state.user
        user_email = user.email if hasattr(user, 'email') else user.get('email', 'Guest')

        st.markdown(f"👤 **{user_email}**")
        if st.button("로그아웃", use_container_width=True):
            db.sign_out()
            st.session_state.user = None
            st.session_state.access_token = None
            st.session_state.jobs = {}
            st.rerun()

        st.markdown("---")
        st.markdown("## 📤 PDF 업로드")

        uploaded_files = st.file_uploader(
            "PDF 파일을 드래그하거나 클릭",
            type=["pdf"],
            accept_multiple_files=True,
            key="pdf_uploader",
        )

        if uploaded_files:
            new_files = []
            for file in uploaded_files:
                existing = [
                    j for j in st.session_state.jobs.values()
                    if j["filename"] == file.name
                ]
                if not existing:
                    content = file.read()
                    create_job(file.name, content)
                    new_files.append(file.name)

            if new_files:
                st.rerun()

        pending_jobs = [
            j for j in st.session_state.jobs.values()
            if j["status"] == "pending"
        ]

        st.markdown("---")

        if st.button(
            f"🚀 변환 시작 ({len(pending_jobs)}개)",
            type="primary",
            use_container_width=True,
            disabled=len(pending_jobs) == 0,
        ):
            if pending_jobs:
                st.session_state.processing_job_id = pending_jobs[0]["job_id"]
                st.rerun()


def process_single_job(job_id: str, progress_bar, status_text):
    """단일 Job 처리"""
    job = st.session_state.jobs[job_id]

    try:
        job["status"] = "processing"

        status_text.text("📁 파일 준비 중...")
        progress_bar.progress(10)
        temp_dir = tempfile.gettempdir()
        temp_path = Path(temp_dir) / f"silverforge_{job['job_id']}.pdf"
        temp_path.write_bytes(job["content"])

        status_text.text("🔍 PDF 분석 중...")
        progress_bar.progress(30)
        markdown = process(str(temp_path))

        status_text.text("📊 품질 검사 중...")
        progress_bar.progress(70)
        quality = curate(markdown)

        progress_bar.progress(90)
        status_text.text("💾 저장 중...")

        job["markdown"] = markdown
        job["quality_score"] = quality.get("overall_score", 0)
        job["quality_details"] = quality
        job["status"] = "completed"
        job["completed_at"] = datetime.now()

        # DB 저장
        save_job_to_db(job)

        progress_bar.progress(100)
        status_text.text("✅ 완료!")

        temp_path.unlink(missing_ok=True)
        del job["content"]

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        progress_bar.progress(100)
        status_text.text(f"❌ 오류 발생")


def render_pending_list():
    """대기 목록 렌더링"""
    pending_jobs = [
        j for j in st.session_state.jobs.values()
        if j["status"] == "pending"
    ]

    st.markdown("### 📋 대기 목록")
    st.markdown("---")

    if not pending_jobs:
        st.markdown(
            """
            <div style="text-align: center; padding: 2rem; color: #6c757d;">
                <p style="font-size: 1.5rem;">📁</p>
                <p>대기 중인 파일이 없습니다</p>
                <p style="font-size: 0.85rem;">사이드바에서 PDF를 업로드하세요</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    processing_job_id = st.session_state.processing_job_id
    needs_continue = False

    for job in pending_jobs:
        job_id = job["job_id"]
        is_processing = (job_id == processing_job_id)

        with st.container():
            col1, col2 = st.columns([5, 1])
            with col1:
                if is_processing:
                    st.markdown(f"⏳ `{job['filename']}`")
                else:
                    st.markdown(f"📄 `{job['filename']}`")
            with col2:
                if not is_processing:
                    if st.button("✕", key=f"remove_{job_id}", help="제거"):
                        del st.session_state.jobs[job_id]
                        st.rerun()

            if is_processing:
                progress_bar = st.progress(0)
                status_text = st.empty()

                process_single_job(job_id, progress_bar, status_text)

                time.sleep(0.5)
                needs_continue = True

            st.markdown("")

    if needs_continue:
        remaining = [
            j for j in st.session_state.jobs.values()
            if j["status"] == "pending"
        ]
        if remaining:
            st.session_state.processing_job_id = remaining[0]["job_id"]
        else:
            st.session_state.processing_job_id = None
        st.rerun()


def render_results_panel():
    """결과 패널 렌더링"""
    st.markdown("### ✅ 변환 결과")
    st.markdown("---")

    all_jobs = list(st.session_state.jobs.values())
    non_pending = [j for j in all_jobs if j["status"] in ["completed", "failed"]]

    if not non_pending:
        st.markdown(
            """
            <div style="text-align: center; padding: 2rem; color: #6c757d;">
                <p style="font-size: 1.5rem;">📭</p>
                <p>변환 결과가 없습니다</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    completed_jobs = [j for j in non_pending if j["status"] == "completed"]
    if len(completed_jobs) > 1:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for job in completed_jobs:
                filename = Path(job["filename"]).stem + "_silver.md"
                zf.writestr(filename, job["markdown"])
        zip_buffer.seek(0)

        st.download_button(
            f"⬇️ 전체 다운로드 ({len(completed_jobs)}개)",
            data=zip_buffer,
            file_name="silverforge_results.zip",
            mime="application/zip",
            use_container_width=True,
        )
        st.markdown("")

    for job in reversed(non_pending):
        render_job_card(job)


def render_job_card(job: dict):
    """Job 카드 렌더링"""
    status = job["status"]
    filename = job["filename"]

    if status == "completed":
        score = job['quality_score']
        if score >= 80:
            border_color = "#28a745"
            score_color = "#28a745"
        elif score >= 60:
            border_color = "#ffc107"
            score_color = "#856404"
        else:
            border_color = "#dc3545"
            score_color = "#dc3545"

        saved_icon = "☁️" if job.get("saved_to_db") else ""

        st.markdown(
            f"""
            <div style="background: #f8f9fa; border-radius: 8px; padding: 0.75rem 1rem;
                        margin-bottom: 0.5rem; border-left: 4px solid {border_color};">
                <strong>✅ {filename}</strong> {saved_icon}<br>
                <small style="color: {score_color}; font-weight: 600;">점수: {score}/100</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        with col1:
            if st.button("📊", key=f"analysis_{job['job_id']}", help="상세 분석", use_container_width=True):
                st.session_state.analysis_job_id = job["job_id"]
                st.rerun()
        with col2:
            if st.button("👁️", key=f"preview_{job['job_id']}", help="미리보기", use_container_width=True):
                st.session_state.preview_job_id = job["job_id"]
                st.rerun()
        with col3:
            md_filename = Path(filename).stem + "_silver.md"
            st.download_button(
                "⬇️",
                data=job["markdown"],
                file_name=md_filename,
                mime="text/markdown",
                key=f"download_{job['job_id']}",
                use_container_width=True,
            )
        with col4:
            if st.button("🗑️", key=f"delete_{job['job_id']}", help="삭제", use_container_width=True):
                del st.session_state.jobs[job["job_id"]]
                st.rerun()

    elif status == "failed":
        st.markdown(
            f"""
            <div style="background: #f8d7da; border-radius: 8px; padding: 0.75rem 1rem;
                        margin-bottom: 0.5rem; border-left: 4px solid #dc3545;">
                <strong>❌ {filename}</strong><br>
                <small style="color: #721c24;">실패</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if job["error"]:
            st.error(f"오류: {job['error']}")

    st.markdown("")


def create_radar_chart(semantic_quality: dict) -> go.Figure:
    """Semantic Quality Radar Chart"""
    categories = ['구조 논리성', '완전성', '일관성']
    values = [
        semantic_quality.get('structure_score', 0),
        semantic_quality.get('completeness_score', 0),
        semantic_quality.get('coherence_score', 0),
    ]
    values.append(values[0])
    categories.append(categories[0])

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        fillcolor='rgba(99, 110, 250, 0.3)',
        line=dict(color='rgb(99, 110, 250)', width=2),
        name='Semantic Score'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10], tickmode='linear', tick0=0, dtick=2),
            angularaxis=dict(tickfont=dict(size=14)),
        ),
        showlegend=False,
        title=dict(text='Semantic Quality', x=0.5, font=dict(size=16)),
        height=350,
        margin=dict(t=60, b=40, l=40, r=40),
    )
    return fig


def create_structure_bar_chart(structure_quality: dict) -> go.Figure:
    """Structure Quality Bar Chart"""
    heading_count = structure_quality.get('heading_count', {})
    categories = ['H1', 'H2', 'H3', 'H4', 'Tables', 'Equations']
    values = [
        heading_count.get('h1', 0),
        heading_count.get('h2', 0),
        heading_count.get('h3', 0),
        heading_count.get('h4', 0),
        structure_quality.get('table_count', 0),
        structure_quality.get('equation_count', 0),
    ]
    colors = ['#636EFA', '#636EFA', '#636EFA', '#636EFA', '#EF553B', '#00CC96']

    fig = go.Figure(data=[go.Bar(x=categories, y=values, marker_color=colors, text=values, textposition='auto')])
    fig.update_layout(
        title=dict(text='Document Structure', x=0.5, font=dict(size=16)),
        xaxis_title='Element Type',
        yaxis_title='Count',
        height=350,
        margin=dict(t=60, b=40, l=40, r=40),
    )
    return fig


def create_gauge_chart(score: int) -> go.Figure:
    """Overall Score Gauge Chart"""
    if score >= 80:
        color = "#28a745"
    elif score >= 60:
        color = "#ffc107"
    else:
        color = "#dc3545"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={'text': "Overall Score", 'font': {'size': 16}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 60], 'color': '#ffebee'},
                {'range': [60, 80], 'color': '#fff3e0'},
                {'range': [80, 100], 'color': '#e8f5e9'},
            ],
            'threshold': {'line': {'color': "black", 'width': 2}, 'thickness': 0.75, 'value': score},
        }
    ))
    fig.update_layout(height=280, margin=dict(t=40, b=20, l=40, r=40))
    return fig


def create_quality_breakdown_chart(quality_details: dict) -> go.Figure:
    """Quality Breakdown Pie Chart"""
    text_pass = quality_details.get('text_quality', {}).get('pass', False)
    struct_pass = quality_details.get('structure_quality', {}).get('pass', False)

    labels = ['Text Quality', 'Structure Quality', 'Semantic Quality']
    values = [
        10 if text_pass else 0,
        10 if struct_pass else 0,
        quality_details.get('semantic_quality', {}).get('overall_score', 0),
    ]
    colors = [
        '#28a745' if text_pass else '#dc3545',
        '#28a745' if struct_pass else '#dc3545',
        '#636EFA',
    ]

    fig = go.Figure(data=[go.Pie(labels=labels, values=values, marker=dict(colors=colors), hole=0.4, textinfo='label+value')])
    fig.update_layout(
        title=dict(text='Score Breakdown', x=0.5, font=dict(size=16)),
        height=350,
        margin=dict(t=60, b=40, l=40, r=40),
        showlegend=False,
    )
    return fig


def render_analysis_view():
    """상세 분석 뷰"""
    job_id = st.session_state.analysis_job_id
    if not job_id or job_id not in st.session_state.jobs:
        return

    job = st.session_state.jobs[job_id]
    quality_details = job.get("quality_details", {})

    col1, col2 = st.columns([6, 1])
    with col1:
        st.markdown(f"### 📊 상세 분석: {job['filename']}")
    with col2:
        if st.button("✕ 닫기", use_container_width=True, key="close_analysis"):
            st.session_state.analysis_job_id = None
            st.rerun()

    st.markdown("---")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.plotly_chart(create_gauge_chart(job.get('quality_score', 0)), use_container_width=True)
    with col2:
        st.markdown("#### 📝 Text Quality")
        text_q = quality_details.get('text_quality', {})
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("문자 수", f"{text_q.get('char_count', 0):,}")
        with col_b:
            st.metric("단어 수", f"{text_q.get('word_count', 0):,}")
        status = "✅ Pass" if text_q.get('pass', False) else "❌ Fail"
        st.markdown(f"**상태:** {status}")

    st.markdown("---")

    semantic_q = quality_details.get('semantic_quality', {})
    structure_q = quality_details.get('structure_quality', {})

    col1, col2 = st.columns([1, 1])
    with col1:
        st.plotly_chart(create_radar_chart(semantic_q), use_container_width=True)
    with col2:
        st.plotly_chart(create_structure_bar_chart(structure_q), use_container_width=True)

    st.markdown("---")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.plotly_chart(create_quality_breakdown_chart(quality_details), use_container_width=True)
    with col2:
        st.markdown("#### ⚠️ Issues & Recommendations")

        struct_issues = structure_q.get('issues', [])
        if struct_issues:
            st.markdown("**구조 이슈:**")
            for issue in struct_issues:
                st.markdown(f"- {issue}")

        semantic_issues = semantic_q.get('issues', [])
        if semantic_issues:
            st.markdown("**의미론적 이슈:**")
            for issue in semantic_issues:
                st.markdown(f"- {issue}")

        recommendation = quality_details.get('recommendation', '')
        if recommendation:
            st.info(f"💡 **권장사항:** {recommendation}")

        st.markdown("---")
        st.markdown("#### ✅ Quality Checks")
        checks = [
            ("Text Quality", text_q.get('pass', False)),
            ("Structure", structure_q.get('pass', False)),
            ("Semantic", semantic_q.get('pass', False)),
        ]
        for name, passed in checks:
            icon = "✅" if passed else "❌"
            st.markdown(f"{icon} {name}")


def render_preview_modal():
    """미리보기 모달"""
    job_id = st.session_state.preview_job_id
    if not job_id or job_id not in st.session_state.jobs:
        return

    job = st.session_state.jobs[job_id]

    col1, col2 = st.columns([6, 1])
    with col1:
        st.markdown(f"### 📄 {job['filename']}")
    with col2:
        if st.button("✕ 닫기", use_container_width=True):
            st.session_state.preview_job_id = None
            st.rerun()

    st.markdown("---")

    if job["quality_details"]:
        details = job["quality_details"]
        struct = details.get("structure_quality", {})

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("품질 점수", f"{job['quality_score']}/100")
        with col2:
            headings = struct.get("heading_count", {})
            st.metric("Headings", sum(headings.values()))
        with col3:
            st.metric("Tables", struct.get("table_count", 0))
        with col4:
            st.metric("Equations", struct.get("equation_count", 0))

    st.markdown("---")

    if job["markdown"]:
        with st.expander("📖 렌더링된 문서", expanded=True):
            st.markdown(job["markdown"][:10000])
            if len(job["markdown"]) > 10000:
                st.info("... (문서가 길어 일부만 표시)")

        with st.expander("📝 Raw Markdown"):
            st.code(job["markdown"][:5000], language="markdown")
            if len(job["markdown"]) > 5000:
                st.info("... (문서가 길어 일부만 표시)")

    md_filename = Path(job["filename"]).stem + "_silver.md"
    st.download_button(
        "⬇️ 다운로드",
        data=job["markdown"],
        file_name=md_filename,
        mime="text/markdown",
        use_container_width=True,
    )


def main():
    """메인 앱"""
    st.set_page_config(
        page_title="SilverForge",
        page_icon="🔥",
        layout="wide",
    )

    inject_custom_css()
    init_session_state()

    # Auth check
    if not st.session_state.user:
        render_auth_page()
        return

    # Sidebar
    render_sidebar()

    # Header
    st.markdown("# 🔥 SilverForge")
    st.caption("PDF를 구조화된 Markdown으로 변환 - VLM/SLM 학습용 GT 데이터 생성")
    st.markdown("---")

    # Analysis view
    if st.session_state.analysis_job_id:
        render_analysis_view()
        return

    # Preview modal
    if st.session_state.preview_job_id:
        render_preview_modal()
        return

    # Main layout
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        render_pending_list()

    with col_right:
        render_results_panel()


if __name__ == "__main__":
    main()
