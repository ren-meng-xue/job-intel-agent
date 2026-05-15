import io


def extract_text(file_bytes: bytes, filename: str) -> str:
    """从上传的简历文件中提取纯文本，支持 PDF 和 DOCX"""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    if lower.endswith(".docx"):
        return _extract_docx(file_bytes)
    raise ValueError(f"不支持的文件格式：{filename}，仅支持 PDF 或 DOCX")


def _extract_pdf(file_bytes: bytes) -> str:
    """用 pdfplumber 逐页提取文本，扫描版 PDF 提取结果为空字符串"""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts).strip()


def _extract_docx(file_bytes: bytes) -> str:
    """用 python-docx 提取所有段落文本"""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
