import asyncio
import base64
import json
import logging

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.schemas.job import ExtractedJobInfo

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None
TIMEOUT_SECONDS = 60
MAX_RETRIES = 2


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=TIMEOUT_SECONDS,
        )
    return _client


def _map_openai_error(exc: Exception) -> AppError:
    if isinstance(exc, RateLimitError):
        return AppError(ErrorCode.UPSTREAM_ERROR, "LLM 调用频率限制，请稍后重试")
    if isinstance(exc, APITimeoutError):
        return AppError(ErrorCode.UPSTREAM_ERROR, f"LLM 调用超时 ({TIMEOUT_SECONDS}s)")
    if isinstance(exc, APIError):
        return AppError(ErrorCode.UPSTREAM_ERROR, f"LLM 调用异常: {exc.message}")
    return AppError(ErrorCode.UPSTREAM_ERROR, f"LLM 调用失败: {exc}")


async def chat(messages: list[dict], model: str = "gpt-4o", **kwargs) -> str:
    """通用 LLM 调用，含 timeout、错误映射。RateLimit 时自动重试。"""
    client = _get_client()
    last_exc: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                model=model, messages=messages, **kwargs
            )
            return response.choices[0].message.content
        except RateLimitError as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                wait = (attempt + 1) * 3
                logger.warning("LLM rate limited, retrying in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
                await asyncio.sleep(wait)
            else:
                logger.error("LLM rate limit exhausted after %d retries", MAX_RETRIES)
        except (APIError, APITimeoutError) as exc:
            last_exc = exc
            logger.warning("LLM API error attempt %d/%d: %s", attempt + 1, MAX_RETRIES + 1, exc)
        except Exception as exc:
            last_exc = exc
            logger.exception("LLM unexpected error")
            break

    raise _map_openai_error(last_exc)


async def suggest_directions(
    title: str,
    company: str,
    jd_summary: str,
    requirements: list[str],
    feedback: str | None = None,
) -> list[str]:
    """根据 JD 信息建议调研方向，至少 4 个，适配前端两列布局"""
    system_prompt = (
        "你是职位调研顾问。根据 JD 信息，建议至少 4 个调研方向。"
        "方向可覆盖：公司背景、技术栈、薪资竞争力、团队文化、面试经验等。"
        '返回 JSON：{"directions": ["方向1", "方向2", ...]}，不要多余内容。'
    )
    user_prompt = (
        f"职位：{title}\n公司：{company}\n摘要：{jd_summary}\n要求：{requirements}"
    )
    if feedback:
        user_prompt += f"\n\n用户反馈：{feedback}"

    resp = await chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
    )
    return json.loads(resp)["directions"]


async def extract_resume_info(raw_content: str) -> dict:
    """从简历纯文本提取结构化字段，返回 dict 对应 Resume 模型的解析字段"""
    system_prompt = (
        "你是简历解析专家。从下面的简历文本中提取关键信息，以 JSON 格式返回，字段如下：\n"
        '- "skills": list[str]，技术/专业技能列表\n'
        '- "experience_years": int，估算总工作年限（在校经历/实习不计），无法判断填 null\n'
        '- "work_experience": list[{company, title, duration, description}]\n'
        '- "education": list[{school, degree, major, year}]\n'
        '- "summary": str，2-3 句职业摘要（用中文）\n'
        "信息不足的字段填 null，不要编造。只返回合法 JSON，不要 markdown。"
    )
    resp = await chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_content[:8000]},
        ],
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
    )
    return json.loads(resp)


def _get_image_mime(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


async def extract_job_info_from_images(images: list[bytes]) -> "ExtractedJobInfo":
    """从 JD 截图（最多 3 张）提取结构化字段，使用 GPT-4o Vision"""
    logger.info("extract_job_info_from_images: image_count=%d total_bytes=%d", len(images), sum(len(i) for i in images))
    system_prompt = (
        "You are a job description parser. Extract key information from the job description images "
        "and return a JSON object with these exact fields:\n"
        '- "title": string (job title)\n'
        '- "company": string (company name)\n'
        '- "requirements": array of strings (key requirements, max 10 items)\n'
        '- "jd_summary": string (2-3 sentence summary of the role)\n'
        '- "salary_range": string or null\n'
        '- "location": string or null\n'
        '- "work_type": string or null ("remote", "hybrid", or "onsite")\n'
        "Return only valid JSON, no markdown."
    )
    image_contents: list[dict] = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{_get_image_mime(img)};base64,{base64.b64encode(img).decode()}"
            },
        }
        for img in images
    ]
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": image_contents + [{"type": "text", "text": "请从以上截图中提取职位信息"}],
        },
    ]
    response_text = await chat(messages=messages, model="gpt-4o", response_format={"type": "json_object"})
    data = json.loads(response_text)
    return ExtractedJobInfo(**data)


async def extract_job_info(markdown: str) -> ExtractedJobInfo:
    """从 JD Markdown 原文提取结构化字段，用 gpt-4o-mini + JSON mode 保证格式正确"""
    system_prompt = (
        "You are a job description parser. Extract key information from the job description "
        "and return a JSON object with these exact fields:\n"
        '- "title": string (job title)\n'
        '- "company": string (company name)\n'
        '- "requirements": array of strings (key requirements, max 10 items)\n'
        '- "jd_summary": string (2-3 sentence summary of the role)\n'
        '- "salary_range": string or null (e.g. "15k-25k", "年薪30万", "$80K-120K"; null if not mentioned)\n'
        '- "location": string or null (city/region, e.g. "北京", "Remote", "Shanghai"; null if not mentioned)\n'
        '- "work_type": string or null ("remote", "hybrid", or "onsite"; null if not mentioned)\n'
        "Return only valid JSON, no markdown."
    )
    response_text = await chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": markdown},
        ],
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
    )
    data = json.loads(response_text)
    return ExtractedJobInfo(**data)
