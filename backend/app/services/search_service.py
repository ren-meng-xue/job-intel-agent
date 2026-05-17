import asyncio
import logging

from tavily import TavilyClient

from app.core.config import settings
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

_client: TavilyClient | None = None
TIMEOUT_SECONDS = 30
MAX_RETRIES = 1


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _client


async def search(query: str, max_results: int = 5) -> list[dict]:
    """公司调研搜索，含 timeout、错误映射和一次重试。"""
    client = _get_client()
    last_exc: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(client.search, query, max_results=max_results),
                timeout=TIMEOUT_SECONDS,
            )
            return response.get("results", [])
        except asyncio.TimeoutError:
            last_exc = AppError(
                ErrorCode.UPSTREAM_ERROR,
                f"Tavily 搜索超时 ({TIMEOUT_SECONDS}s): {query[:80]}",
            )
            logger.warning("Tavily timeout attempt %d/%d: %s", attempt + 1, MAX_RETRIES + 1, query[:80])
        except AppError:
            raise
        except Exception as exc:
            last_exc = exc
            logger.warning("Tavily error attempt %d/%d: %s — %s", attempt + 1, MAX_RETRIES + 1, query[:80], exc)

    raise AppError(
        ErrorCode.UPSTREAM_ERROR,
        f"Tavily 搜索失败 (已重试 {MAX_RETRIES} 次): {query[:80]}",
    ) from last_exc
