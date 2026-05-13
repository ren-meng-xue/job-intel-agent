from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.job import JobCreate, JobResponse

router = APIRouter()


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(payload: JobCreate, db: AsyncSession = Depends(get_db)):
    # TODO: 存储 JD URL 到 DB，触发 research.run Celery 任务 ⚠️ 风险：URL 格式各平台不统一
    raise NotImplementedError
