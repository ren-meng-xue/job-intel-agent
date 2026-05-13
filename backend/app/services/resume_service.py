async def parse_resume(file_bytes: bytes, filename: str) -> dict:
    # TODO: pdfplumber/docx2txt 解析正文，LLM 提炼结构化字段 ⚠️ 风险：扫描版 PDF 需 OCR 回退
    raise NotImplementedError
