"""SilverForge API Server

FastAPI 기반 백엔드 - PDF 업로드, 비동기 처리, 결과 조회
"""

import asyncio
import io
import os
import tempfile
import uuid
import zipfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .core import process
from .curator import curate

app = FastAPI(
    title="SilverForge API",
    description="PDF를 구조화된 Markdown으로 변환",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobResult(BaseModel):
    job_id: str
    filename: str
    status: JobStatus
    progress: int = 0
    markdown: Optional[str] = None
    quality_score: Optional[int] = None
    quality_details: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# In-memory job storage (for prototype)
jobs: dict[str, JobResult] = {}


@app.get("/")
async def root():
    return {"message": "SilverForge API", "version": "0.1.0"}


@app.post("/upload", response_model=list[str])
async def upload_files(files: list[UploadFile] = File(...)):
    """
    여러 PDF 파일 업로드 및 Job 생성

    Returns:
        list[str]: 생성된 job_id 목록
    """
    job_ids = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"PDF 파일만 업로드 가능합니다: {file.filename}"
            )

        job_id = str(uuid.uuid4())[:8]

        # Save uploaded file temporarily
        content = await file.read()
        temp_dir = tempfile.gettempdir()
        temp_path = Path(temp_dir) / f"silverforge_{job_id}.pdf"
        temp_path.write_bytes(content)

        # Create job
        jobs[job_id] = JobResult(
            job_id=job_id,
            filename=file.filename,
            status=JobStatus.PENDING,
            progress=0,
            created_at=datetime.now(),
        )

        # Store temp path for processing
        jobs[job_id]._temp_path = str(temp_path)

        job_ids.append(job_id)

    return job_ids


@app.post("/process/{job_id}")
async def process_job(job_id: str):
    """
    단일 Job 처리 시작
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job.status == JobStatus.PROCESSING:
        return {"message": "Already processing"}

    if job.status == JobStatus.COMPLETED:
        return {"message": "Already completed"}

    # Start processing in background
    asyncio.create_task(_process_job(job_id))

    return {"message": "Processing started", "job_id": job_id}


@app.post("/process-all")
async def process_all_jobs():
    """
    모든 대기 중인 Job 순차 처리
    """
    pending_jobs = [
        job_id for job_id, job in jobs.items()
        if job.status == JobStatus.PENDING
    ]

    if not pending_jobs:
        return {"message": "No pending jobs"}

    # Start processing all jobs
    asyncio.create_task(_process_all_jobs(pending_jobs))

    return {"message": f"Processing {len(pending_jobs)} jobs", "job_ids": pending_jobs}


async def _process_job(job_id: str):
    """
    Job 처리 (비동기)
    """
    job = jobs[job_id]
    temp_path = getattr(job, "_temp_path", None)

    if not temp_path or not Path(temp_path).exists():
        job.status = JobStatus.FAILED
        job.error = "Temp file not found"
        return

    try:
        job.status = JobStatus.PROCESSING
        job.progress = 10

        # Step 1: Parse PDF (60%)
        job.progress = 20
        markdown = process(temp_path)
        job.progress = 60

        # Step 2: Quality check (90%)
        job.progress = 70
        quality = curate(markdown)
        job.progress = 90

        # Complete
        job.markdown = markdown
        job.quality_score = quality.get("overall_score", 0)
        job.quality_details = quality
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.completed_at = datetime.now()

        # Cleanup temp file
        Path(temp_path).unlink(missing_ok=True)

    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.progress = 0


async def _process_all_jobs(job_ids: list[str]):
    """
    여러 Job 순차 처리
    """
    for job_id in job_ids:
        await _process_job(job_id)
        await asyncio.sleep(0.1)  # Small delay between jobs


@app.get("/jobs", response_model=list[JobResult])
async def list_jobs():
    """
    모든 Job 목록 조회
    """
    return list(jobs.values())


@app.get("/jobs/{job_id}", response_model=JobResult)
async def get_job(job_id: str):
    """
    특정 Job 상태 조회
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/download/{job_id}")
async def download_job(job_id: str):
    """
    단일 결과 다운로드 (Markdown)
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed")

    if not job.markdown:
        raise HTTPException(status_code=400, detail="No markdown content")

    filename = Path(job.filename).stem + "_silver.md"

    return StreamingResponse(
        io.BytesIO(job.markdown.encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/download-all")
async def download_all():
    """
    모든 완료된 결과 ZIP 다운로드
    """
    completed_jobs = [
        job for job in jobs.values()
        if job.status == JobStatus.COMPLETED and job.markdown
    ]

    if not completed_jobs:
        raise HTTPException(status_code=400, detail="No completed jobs")

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for job in completed_jobs:
            filename = Path(job.filename).stem + "_silver.md"
            zf.writestr(filename, job.markdown)

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=silverforge_results.zip"}
    )


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Job 삭제
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # Cleanup temp file if exists
    temp_path = getattr(job, "_temp_path", None)
    if temp_path:
        Path(temp_path).unlink(missing_ok=True)

    del jobs[job_id]

    return {"message": "Job deleted", "job_id": job_id}


@app.delete("/jobs")
async def clear_all_jobs():
    """
    모든 Job 삭제
    """
    for job in jobs.values():
        temp_path = getattr(job, "_temp_path", None)
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)

    jobs.clear()

    return {"message": "All jobs cleared"}


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """
    API 서버 실행
    """
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
