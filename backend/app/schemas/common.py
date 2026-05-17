from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """统一错误响应格式"""
    code: str
    message: str
    detail: dict | None = None
