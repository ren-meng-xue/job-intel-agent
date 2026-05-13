from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: str
    job_id: str
    status: str
    content: str | None = None

    model_config = {"from_attributes": True}
