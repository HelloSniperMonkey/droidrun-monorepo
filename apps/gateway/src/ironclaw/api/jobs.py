"""
Job Hunter API endpoints.
Handles resume parsing and job application automation.
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..modules.job_hunter import JobHunterService

logger = logging.getLogger("ironclaw.api.jobs")
router = APIRouter()


class JobSearchRequest(BaseModel):
    """Request model for job search."""
    query: str  # e.g., "Senior Python Developer remote"
    max_applications: int = 3
    filters: Optional[dict] = None  # e.g., {"posted_within": "24h"}


class JobSearchResponse(BaseModel):
    """Response model for job search."""
    task_id: str
    status: str
    message: str


class ResumeParseResponse(BaseModel):
    """Response model for resume parsing."""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


@router.post("/upload-resume", response_model=ResumeParseResponse)
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload and parse a resume PDF.
    Extracts structured data for job applications.
    """
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        service = JobHunterService()
        result = await service.parse_resume(file)
        return ResumeParseResponse(success=True, data=result)
    except Exception as e:
        logger.error(f"Resume parsing failed: {e}")
        return ResumeParseResponse(success=False, error=str(e))


@router.post("/search-and-apply", response_model=JobSearchResponse)
async def search_and_apply(
    request: JobSearchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a job search and application workflow.
    Runs asynchronously in the background.
    """
    try:
        service = JobHunterService()

        # Generate task ID
        import uuid
        task_id = str(uuid.uuid4())[:8]

        # Queue the background task
        background_tasks.add_task(
            service.search_and_apply,
            query=request.query,
            max_applications=request.max_applications,
            filters=request.filters,
            task_id=task_id,
        )

        return JobSearchResponse(
            task_id=task_id,
            status="started",
            message=f"Job search started for: {request.query}",
        )
    except Exception as e:
        logger.error(f"Job search failed to start: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a job search task."""
    service = JobHunterService()
    status = await service.get_task_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return status
