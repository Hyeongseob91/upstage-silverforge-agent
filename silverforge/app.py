"""SilverForge UI Console

Streamlit 기반 웹 인터페이스
- PDF 다중 업로드
- 분석 결과 목록
- 미리보기 팝업
- 개별/전체 다운로드
"""

import io
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st

# Handle both direct execution and package import
try:
    from .core import process
    from .curator import curate
except ImportError:
    # Add parent directory to path for direct execution
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from silverforge.core import process
    from silverforge.curator import curate


def init_session_state():
    """세션 상태 초기화"""
    if "jobs" not in st.session_state:
        st.session_state.jobs = {}
    if "preview_job_id" not in st.session_state:
        st.session_state.preview_job_id = None


def create_job(filename: str, content: bytes) -> str:
    """Job 생성"""
    job_id = f"{int(time.time() * 1000) % 100000:05d}"

    st.session_state.jobs[job_id] = {
        "job_id": job_id,
        "filename": filename,
        "content": content,
        "status": "pending",
        "progress": 0,
        "markdown": None,
        "quality_score": None,
        "quality_details": None,
        "error": None,
        "created_at": datetime.now(),
        "completed_at": None,
    }

    return job_id


def process_job(job_id: str):
    """Job 처리"""
    job = st.session_state.jobs[job_id]

    if job["status"] != "pending":
        return

    try:
        job["status"] = "processing"
        job["progress"] = 10

        # Save to temp file
        temp_dir = tempfile.gettempdir()
        temp_path = Path(temp_dir) / f"silverforge_{job_id}.pdf"
        temp_path.write_bytes(job["content"])

        # Process
        job["progress"] = 30
        markdown = process(str(temp_path))
        job["progress"] = 70

        # Quality check
        quality = curate(markdown)
        job["progress"] = 90

        # Complete
        job["markdown"] = markdown
        job["quality_score"] = quality.get("overall_score", 0)
        job["quality_details"] = quality
        job["status"] = "completed"
        job["progress"] = 100
        job["completed_at"] = datetime.now()

        # Cleanup
        temp_path.unlink(missing_ok=True)
        del job["content"]  # Free memory

    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
        job["progress"] = 0


def render_upload_zone():
    """업로드 존 렌더링"""
    st.markdown("### 📤 PDF 업로드")

    uploaded_files = st.file_uploader(
        "PDF 파일을 드래그하거나 클릭하여 선택",
        type=["pdf"],
        accept_multiple_files=True,
        key="pdf_uploader",
    )

    if uploaded_files:
        new_files = []
        for file in uploaded_files:
            # Check if already uploaded
            existing = [
                j for j in st.session_state.jobs.values()
                if j["filename"] == file.name and j["status"] == "pending"
            ]
            if not existing:
                content = file.read()
                job_id = create_job(file.name, content)
                new_files.append(file.name)

        if new_files:
            st.success(f"✅ {len(new_files)}개 파일 추가됨")

    # Pending jobs list
    pending_jobs = [
        j for j in st.session_state.jobs.values()
        if j["status"] == "pending"
    ]

    if pending_jobs:
        st.markdown("#### 📋 대기 중인 파일")
        for job in pending_jobs:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(f"📄 {job['filename']}")
            with col2:
                if st.button("❌", key=f"remove_{job['job_id']}"):
                    del st.session_state.jobs[job["job_id"]]
                    st.rerun()

        st.markdown("---")

        if st.button("🚀 분석 시작", type="primary", use_container_width=True):
            return True

    return False


def render_results_panel():
    """결과 패널 렌더링"""
    all_jobs = list(st.session_state.jobs.values())
    non_pending = [j for j in all_jobs if j["status"] != "pending"]

    if not non_pending:
        st.info("분석된 결과가 없습니다. PDF를 업로드하고 분석을 시작하세요.")
        return

    # Download all button
    completed_jobs = [j for j in non_pending if j["status"] == "completed"]
    if len(completed_jobs) > 1:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for job in completed_jobs:
                filename = Path(job["filename"]).stem + "_silver.md"
                zf.writestr(filename, job["markdown"])
        zip_buffer.seek(0)

        st.download_button(
            "⬇️ 전체 다운로드 (ZIP)",
            data=zip_buffer,
            file_name="silverforge_results.zip",
            mime="application/zip",
            use_container_width=True,
        )
        st.markdown("---")

    # Results list
    for job in reversed(non_pending):
        render_job_card(job)


def render_job_card(job: dict):
    """Job 카드 렌더링"""
    status = job["status"]
    filename = job["filename"]

    # Status icon
    if status == "completed":
        icon = "✅"
        status_text = f"{job['quality_score']}/100"
    elif status == "processing":
        icon = "⏳"
        status_text = f"처리 중... {job['progress']}%"
    elif status == "failed":
        icon = "❌"
        status_text = "실패"
    else:
        icon = "⏸️"
        status_text = "대기"

    with st.container():
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            st.markdown(f"**{icon} {filename}**")
            st.caption(status_text)

        with col2:
            if status == "completed":
                if st.button("👁️", key=f"preview_{job['job_id']}", help="미리보기"):
                    st.session_state.preview_job_id = job["job_id"]
                    st.rerun()

        with col3:
            if status == "completed":
                md_filename = Path(filename).stem + "_silver.md"
                st.download_button(
                    "⬇️",
                    data=job["markdown"],
                    file_name=md_filename,
                    mime="text/markdown",
                    key=f"download_{job['job_id']}",
                    help="다운로드",
                )

        if status == "failed" and job["error"]:
            st.error(f"오류: {job['error']}")

        if status == "processing":
            st.progress(job["progress"] / 100)

        st.markdown("---")


def render_preview_modal():
    """미리보기 모달 렌더링"""
    job_id = st.session_state.preview_job_id

    if not job_id or job_id not in st.session_state.jobs:
        return

    job = st.session_state.jobs[job_id]

    # Modal container
    with st.container():
        st.markdown(
            """
            <style>
            .preview-modal {
                background-color: #f0f2f6;
                border-radius: 10px;
                padding: 20px;
                margin: 10px 0;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns([6, 1])
        with col1:
            st.markdown(f"### 📄 {job['filename']} - Silver Markdown")
        with col2:
            if st.button("✕ 닫기"):
                st.session_state.preview_job_id = None
                st.rerun()

        # Quality info
        if job["quality_details"]:
            details = job["quality_details"]
            struct = details.get("structure_quality", {})

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("품질 점수", f"{job['quality_score']}/100")
            with col2:
                headings = struct.get("heading_count", {})
                total_headings = sum(headings.values())
                st.metric("Headings", total_headings)
            with col3:
                st.metric("Tables", struct.get("table_count", 0))
            with col4:
                st.metric("Equations", struct.get("equation_count", 0))

        st.markdown("---")

        # Markdown preview
        if job["markdown"]:
            # Show rendered markdown
            with st.expander("📖 렌더링된 문서", expanded=True):
                st.markdown(job["markdown"][:10000])
                if len(job["markdown"]) > 10000:
                    st.info("... (문서가 길어 일부만 표시)")

            # Show raw markdown
            with st.expander("📝 Raw Markdown"):
                st.code(job["markdown"][:5000], language="markdown")
                if len(job["markdown"]) > 5000:
                    st.info("... (문서가 길어 일부만 표시)")

        # Download button
        md_filename = Path(job["filename"]).stem + "_silver.md"
        st.download_button(
            "⬇️ 다운로드",
            data=job["markdown"],
            file_name=md_filename,
            mime="text/markdown",
            use_container_width=True,
        )

        st.markdown("---")


def main():
    """메인 앱"""
    st.set_page_config(
        page_title="SilverForge",
        page_icon="🔥",
        layout="wide",
    )

    init_session_state()

    # Header
    st.markdown("# 🔥 SilverForge")
    st.caption("PDF를 구조화된 Markdown으로 변환 - VLM/SLM 학습용 GT 데이터 생성")

    # Preview modal (if active)
    if st.session_state.preview_job_id:
        render_preview_modal()
        return

    # Main layout
    col_left, col_right = st.columns([1, 1])

    with col_left:
        start_processing = render_upload_zone()

    with col_right:
        st.markdown("### 📋 Results")
        render_results_panel()

    # Process jobs if requested
    if start_processing:
        pending_jobs = [
            j for j in st.session_state.jobs.values()
            if j["status"] == "pending"
        ]

        if pending_jobs:
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, job in enumerate(pending_jobs):
                status_text.text(f"처리 중: {job['filename']} ({i+1}/{len(pending_jobs)})")
                process_job(job["job_id"])
                progress_bar.progress((i + 1) / len(pending_jobs))

            status_text.text("✅ 모든 처리 완료!")
            time.sleep(1)
            st.rerun()


if __name__ == "__main__":
    main()
