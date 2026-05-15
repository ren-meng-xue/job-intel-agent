import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id"), nullable=False, index=True
    )  # 归属用户
    filename: Mapped[str] = mapped_column(String(256), nullable=False)  # 上传的原始文件名
    raw_content: Mapped[str | None] = mapped_column(Text)  # pdfplumber/python-docx 提取的纯文本
    skills: Mapped[list | None] = mapped_column(JSON)  # LLM 提取的技能列表，如 ["Python", "React"]
    experience_years: Mapped[int | None] = mapped_column(Integer)  # LLM 估算的总工作年限（在校/实习不计）
    work_experience: Mapped[list | None] = mapped_column(JSON)  # [{company, title, duration, description}]
    education: Mapped[list | None] = mapped_column(JSON)  # [{school, degree, major, year}]
    summary: Mapped[str | None] = mapped_column(Text)  # LLM 生成的职业摘要，2-3 句
    parsing_error: Mapped[str | None] = mapped_column(Text)  # 解析失败原因，如扫描版 PDF
    # pending → parsing → done / failed
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
