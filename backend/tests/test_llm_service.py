import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.job import ExtractedJobInfo
from app.services.llm_service import extract_job_info


async def test_extract_job_info_returns_structured_info():
    """正常情况：LLM 返回完整字段，能正确解析成 ExtractedJobInfo"""
    sample_response = json.dumps({
        "title": "Senior Python Developer",
        "company": "TechCorp",
        "requirements": ["Python 3.10+", "FastAPI", "PostgreSQL"],
        "jd_summary": "We are looking for a Python developer to join our backend team.",
        "salary_range": "25k-40k",
        "location": "上海",
        "work_type": "hybrid",
    })

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = sample_response

    with patch("app.services.llm_service._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        result = await extract_job_info("## Senior Python Developer\nTechCorp is hiring...")

    assert isinstance(result, ExtractedJobInfo)
    assert result.title == "Senior Python Developer"
    assert result.company == "TechCorp"
    assert result.requirements == ["Python 3.10+", "FastAPI", "PostgreSQL"]
    assert "Python developer" in result.jd_summary
    assert result.salary_range == "25k-40k"
    assert result.location == "上海"
    assert result.work_type == "hybrid"


async def test_extract_job_info_nullable_fields_can_be_absent():
    """JD 里没有薪资/地点/类型时，LLM 返回 null，字段应为 None"""
    sample_response = json.dumps({
        "title": "Engineer",
        "company": "Co",
        "requirements": ["Python"],
        "jd_summary": "A role.",
        "salary_range": None,
        "location": None,
        "work_type": None,
    })

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = sample_response

    with patch("app.services.llm_service._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        result = await extract_job_info("## Job\nSome description")

    assert result.salary_range is None
    assert result.location is None
    assert result.work_type is None


async def test_extract_job_info_uses_gpt4o_mini_with_json_mode():
    """必须使用 gpt-4o-mini 并开启 JSON mode"""
    sample_response = json.dumps({
        "title": "Engineer",
        "company": "Co",
        "requirements": ["Python"],
        "jd_summary": "A role.",
    })

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = sample_response

    with patch("app.services.llm_service._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_get_client.return_value = mock_client

        await extract_job_info("## Job\nSome description")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["response_format"] == {"type": "json_object"}
