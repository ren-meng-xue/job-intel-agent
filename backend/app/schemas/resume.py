from datetime import datetime

from pydantic import BaseModel


class ResumeResponse(BaseModel):
    """上传成功后立即返回，此时 LLM 尚未解析完"""
    id: str
    filename: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeDetailResponse(BaseModel):
    """GET /resume/ 返回，包含 LLM 解析结果（解析中时各字段为 null）"""
    id: str
    filename: str
    status: str
    skills: list | None = None
    experience_years: int | None = None
    work_experience: list | None = None  # [{company, title, duration, description}]
    education: list | None = None        # [{school, degree, major, year}]
    summary: str | None = None
    parsing_error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
