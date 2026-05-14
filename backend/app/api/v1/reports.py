from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.models.user import User
from app.schemas.report import ReportResponse
from app.services.auth_service import get_current_user

router = APIRouter()


@router.get("/{report_id}/stream")
async def stream_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    # TODO: 订阅 Redis Pub/Sub channel，以 SSE 格式推送调研进度 ⚠️ 风险：客户端断连时需主动清理订阅
    raise NotImplementedError


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
):
    # TODO: 从 DB 查询报告；status != done 时返回 202 ⚠️ 风险：content 大文本，注意序列化性能
    raise NotImplementedError
