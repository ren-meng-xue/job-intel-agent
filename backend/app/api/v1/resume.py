from fastapi import APIRouter, UploadFile

router = APIRouter()


@router.post("/", status_code=201)
async def upload_resume(file: UploadFile):
    # TODO: 写入 S3 / 本地存储，调用 resume_service.parse_resume ⚠️ 风险：扫描版 PDF 解析准确率低
    raise NotImplementedError
