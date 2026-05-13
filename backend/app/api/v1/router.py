from fastapi import APIRouter

from app.api.v1 import jobs, reports, resume

router = APIRouter()
router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(reports.router, prefix="/reports", tags=["reports"])
router.include_router(resume.router, prefix="/resume", tags=["resume"])
