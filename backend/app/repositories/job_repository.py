from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


class JobRepository:
    """Job 表数据访问层，供 API 层和 Celery task 使用"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(
        self, url: str, user_id: str, resume_id: str | None = None
    ) -> Job:
        """创建 Job 记录，初始 status 为 parsing（立即触发 Celery task）"""
        job = Job(url=url, user_id=user_id, resume_id=resume_id, status="parsing")
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: str) -> Job | None:
        """按 job_id 查询，Celery task 用它拿 url 和当前状态"""
        result = await self.session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def update_after_parse(
        self,
        job_id: str,
        *,
        raw_content: str,
        title: str,
        company: str,
        requirements: list[str],
        jd_summary: str,
        salary_range: str | None = None,
        location: str | None = None,
        work_type: str | None = None,
    ) -> None:
        """LLM 解析完后写回结果，status 改为 awaiting_confirm 等待用户确认"""
        job = await self.get_by_id(job_id)
        if not job:
            return
        job.raw_content = raw_content
        job.title = title
        job.company = company
        job.requirements = requirements
        job.jd_summary = jd_summary
        job.salary_range = salary_range
        job.location = location
        job.work_type = work_type
        job.status = "awaiting_confirm"
        await self.session.commit()

    async def update_status(self, job_id: str, status: str) -> None:
        """单独更新 status，主要用于异常时将状态改为 failed"""
        job = await self.get_by_id(job_id)
        if not job:
            return
        job.status = status
        await self.session.commit()

    async def confirm_job(
        self,
        job_id: str,
        *,
        title: str | None = None,
        company: str | None = None,
        requirements: list[str] | None = None,
        jd_summary: str | None = None,
        salary_range: str | None = None,
        location: str | None = None,
        work_type: str | None = None,
    ) -> "Job | None":
        """用户确认/修正 JD 字段，只更新非 None 的字段，status → awaiting_directions"""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        if title is not None:
            job.title = title
        if company is not None:
            job.company = company
        if requirements is not None:
            job.requirements = requirements
        if jd_summary is not None:
            job.jd_summary = jd_summary
        if salary_range is not None:
            job.salary_range = salary_range
        if location is not None:
            job.location = location
        if work_type is not None:
            job.work_type = work_type
        job.status = "awaiting_directions"
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def start_research(
        self, job_id: str, selected_directions: list[str]
    ) -> "Job | None":
        """保存用户选择的调研方向，status → researching"""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        job.selected_directions = selected_directions
        job.status = "researching"
        await self.session.commit()
        await self.session.refresh(job)
        return job
