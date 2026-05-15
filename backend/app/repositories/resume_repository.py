from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import Resume


class ResumeRepository:
    """Resume 表数据访问层，供 API 层和 Celery task 使用"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, resume: Resume) -> Resume:
        """插入新简历记录"""
        self.session.add(resume)
        await self.session.commit()
        await self.session.refresh(resume)
        return resume

    async def get_by_id(self, resume_id: str) -> Resume | None:
        """按 ID 查单条"""
        result = await self.session.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: str) -> Resume | None:
        """查该用户当前的简历，每人只能有一份"""
        result = await self.session.execute(
            select(Resume).where(Resume.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_after_parse(
        self,
        resume_id: str,
        *,
        skills: list | None,
        experience_years: int | None,
        work_experience: list | None,
        education: list | None,
        summary: str | None,
    ) -> None:
        """LLM 解析完后写回结构化字段，status → done"""
        resume = await self.get_by_id(resume_id)
        if not resume:
            return
        resume.skills = skills
        resume.experience_years = experience_years
        resume.work_experience = work_experience
        resume.education = education
        resume.summary = summary
        resume.status = "done"
        await self.session.commit()

    async def update_status(self, resume_id: str, status: str, error: str | None = None) -> None:
        """更新 status，解析失败时同步写入 parsing_error"""
        resume = await self.get_by_id(resume_id)
        if not resume:
            return
        resume.status = status
        if error is not None:
            resume.parsing_error = error
        await self.session.commit()

    async def delete(self, resume_id: str) -> bool:
        """删除简历记录，返回是否成功"""
        resume = await self.get_by_id(resume_id)
        if not resume:
            return False
        await self.session.delete(resume)
        await self.session.commit()
        return True
