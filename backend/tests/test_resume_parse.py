import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.resume_service import extract_text
from app.tasks.resume import _do_parse_resume


# ── resume_service 文本提取 ────────────────────────────────────────────────


def test_extract_text_pdf_returns_text():
    """PDF 正常文本 → 返回非空字符串"""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Python 工程师\n5年经验"
    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    # pdfplumber 在函数内懒加载，patch 库本身的 open
    with patch("pdfplumber.open", return_value=mock_pdf):
        result = extract_text(b"fake-pdf", "resume.pdf")

    assert "Python 工程师" in result
    assert "5年经验" in result


def test_extract_text_pdf_scanned_returns_empty():
    """扫描版 PDF 无法提取文本 → 返回空字符串"""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None
    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    with patch("pdfplumber.open", return_value=mock_pdf):
        result = extract_text(b"fake-scan-pdf", "resume.pdf")

    assert result == ""


def test_extract_text_docx_returns_text():
    """DOCX 正常文本 → 返回段落拼接结果"""
    mock_para1 = MagicMock()
    mock_para1.text = "张三"
    mock_para2 = MagicMock()
    mock_para2.text = "后端开发工程师"
    mock_para_empty = MagicMock()
    mock_para_empty.text = ""  # 空段落应被过滤

    mock_doc = MagicMock()
    mock_doc.paragraphs = [mock_para1, mock_para2, mock_para_empty]

    # Document 在函数内懒加载，patch docx 库本身
    with patch("docx.Document", return_value=mock_doc):
        result = extract_text(b"fake-docx", "resume.docx")

    assert "张三" in result
    assert "后端开发工程师" in result


def test_extract_text_unsupported_format_raises():
    """不支持的格式 → 抛出 ValueError"""
    with pytest.raises(ValueError, match="不支持的文件格式"):
        extract_text(b"content", "resume.txt")


# ── task_parse_resume ─────────────────────────────────────────────────────


async def test_do_parse_resume_success():
    """正常流程：查库 → LLM 提取 → 写库 → Redis publish parsed"""
    mock_resume = MagicMock(id="r-1", raw_content="张三 Python工程师 5年经验")
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = mock_resume

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()
    mock_info = {
        "skills": ["Python", "FastAPI"],
        "experience_years": 5,
        "work_experience": [{"company": "字节", "title": "后端", "duration": "2019-2024", "description": "..."}],
        "education": [{"school": "复旦", "degree": "本科", "major": "CS", "year": "2019"}],
        "summary": "5年后端经验",
    }

    with (
        patch("app.tasks.resume.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.tasks.resume.ResumeRepository", return_value=mock_repo),
        patch("app.tasks.resume.extract_resume_info", AsyncMock(return_value=mock_info)),
        patch("app.tasks.resume.aioredis") as mock_aioredis_mod,
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await _do_parse_resume("r-1")

    mock_repo.update_after_parse.assert_called_once_with(
        "r-1",
        skills=["Python", "FastAPI"],
        experience_years=5,
        work_experience=mock_info["work_experience"],
        education=mock_info["education"],
        summary="5年后端经验",
    )

    channel, payload_str = mock_redis.publish.call_args[0]
    assert channel == "resume:r-1"
    assert json.loads(payload_str)["type"] == "parsed"
    mock_redis.aclose.assert_called_once()


async def test_do_parse_resume_empty_content():
    """raw_content 为空（扫描版 PDF）→ status=failed，publish error"""
    mock_resume = MagicMock(id="r-2", raw_content=None)
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = mock_resume

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()

    with (
        patch("app.tasks.resume.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.tasks.resume.ResumeRepository", return_value=mock_repo),
        patch("app.tasks.resume.aioredis") as mock_aioredis_mod,
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await _do_parse_resume("r-2")

    # 验证 status=failed 且 error 是非空字符串
    call_args = mock_repo.update_status.call_args
    assert call_args[0][0] == "r-2"
    assert call_args[0][1] == "failed"
    assert isinstance(call_args[1]["error"], str) and len(call_args[1]["error"]) > 0

    channel, payload_str = mock_redis.publish.call_args[0]
    assert channel == "resume:r-2"
    assert json.loads(payload_str)["type"] == "error"


async def test_do_parse_resume_not_found():
    """resume_id 不存在 → 直接返回，不调用任何写库或 publish"""
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = None

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()

    with (
        patch("app.tasks.resume.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.tasks.resume.ResumeRepository", return_value=mock_repo),
        patch("app.tasks.resume.aioredis") as mock_aioredis_mod,
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await _do_parse_resume("nonexistent")

    mock_repo.update_after_parse.assert_not_called()
    mock_redis.publish.assert_not_called()


async def test_do_parse_resume_llm_error():
    """LLM 调用失败 → status=failed，publish error"""
    mock_resume = MagicMock(id="r-3", raw_content="一些文本")
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = mock_resume

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_redis = AsyncMock()

    with (
        patch("app.tasks.resume.AsyncSessionLocal", return_value=mock_session_ctx),
        patch("app.tasks.resume.ResumeRepository", return_value=mock_repo),
        patch("app.tasks.resume.extract_resume_info", AsyncMock(side_effect=RuntimeError("OpenAI timeout"))),
        patch("app.tasks.resume.aioredis") as mock_aioredis_mod,
    ):
        mock_aioredis_mod.from_url = AsyncMock(return_value=mock_redis)
        await _do_parse_resume("r-3")

    call_args = mock_repo.update_status.call_args
    assert call_args[0][0] == "r-3"
    assert call_args[0][1] == "failed"

    channel, payload_str = mock_redis.publish.call_args[0]
    assert channel == "resume:r-3"
    assert json.loads(payload_str)["type"] == "error"
