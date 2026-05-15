from pydantic import BaseModel, HttpUrl


class ExtractedJobInfo(BaseModel):
    title: str
    company: str
    requirements: list[str]
    jd_summary: str
    salary_range: str | None = None
    location: str | None = None
    work_type: str | None = None


class JobCreate(BaseModel):
    url: HttpUrl
    resume_id: str | None = None


class JobResponse(BaseModel):
    id: str
    url: str
    status: str
    title: str | None = None
    company: str | None = None
    salary_range: str | None = None
    location: str | None = None
    work_type: str | None = None

    model_config = {"from_attributes": True}


class JobDetailResponse(BaseModel):
    """含完整 JD 字段，用于 confirm/start 接口的返回"""
    id: str
    url: str
    status: str
    title: str | None = None
    company: str | None = None
    requirements: list | None = None
    jd_summary: str | None = None
    salary_range: str | None = None
    location: str | None = None
    work_type: str | None = None
    selected_directions: list | None = None
    suggested_directions: list[str] | None = None  # confirm 时自动生成首批方向建议

    model_config = {"from_attributes": True}


class JobConfirmPayload(BaseModel):
    """用户修正 LLM 提取的 JD 字段，全部可选，只传需要改的"""
    title: str | None = None
    company: str | None = None
    requirements: list[str] | None = None
    jd_summary: str | None = None
    salary_range: str | None = None
    location: str | None = None
    work_type: str | None = None


class JobStartPayload(BaseModel):
    """用户选择的调研方向列表，至少一个"""
    selected_directions: list[str]


class DirectionsPayload(BaseModel):
    """可选 feedback，引导 LLM 生成/刷新方向建议"""
    feedback: str | None = None


class DirectionsResponse(BaseModel):
    suggestions: list[str]


class ReparsePayload(BaseModel):
    """重新触发 JD 解析，无需额外参数"""
    pass


class ResumePayload(BaseModel):
    """恢复 LangGraph 中断执行"""
    action: str  # "approve" | "edit" | "retry"
    edits: dict | None = None
    feedback: str | None = None
