import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )
    resume_id: Mapped[str | None] = mapped_column(String, nullable=True)  # 关联的简历 ID，可选
    url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text)  # Firecrawl 抓取的原始 Markdown
    title: Mapped[str | None] = mapped_column(String(256))  # LLM 提取的职位名称
    company: Mapped[str | None] = mapped_column(String(256))  # LLM 提取的公司名
    requirements: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 任职要求列表，max 10 条
    jd_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # 2-3 句岗位摘要
    salary_range: Mapped[str | None] = mapped_column(String(256), nullable=True)  # 薪资范围，保留原始写法（如 "15k-25k"）
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)  # 工作地点
    work_type: Mapped[str | None] = mapped_column(String(64), nullable=True)  # remote / hybrid / onsite
    selected_directions: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 用户选择的调研方向
    # pending → parsing → awaiting_confirm → awaiting_directions → researching → generating → done / failed
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
