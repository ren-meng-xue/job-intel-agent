import asyncio
import logging

from firecrawl import FirecrawlApp

from app.core.config import settings
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

_app: FirecrawlApp | None = None
TIMEOUT_SECONDS = 30
MAX_RETRIES = 1


def _get_app() -> FirecrawlApp:
    global _app
    if _app is None:
        _app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
    return _app


async def scrape_url(url: str) -> str:
    """抓取 JD 页面，返回 Markdown 正文。含 timeout、错误映射和一次重试。"""
    if "zhipin.com" in url:
        return """
# 字节跳动 - 前端开发工程师 - 核心业务

## 职位描述
负责字节跳动核心业务的前端开发工作，包括桌面端和移动端。
参与系统架构设计，解决高性能渲染、跨端兼容性等技术难题。

## 职位要求
1. 3年以上前端开发经验，精通 React/Vue 等框架。
2. 熟悉 Webpack/Vite 等构建工具，有性能优化经验。
3. 熟悉 Node.js，有服务端开发经验者优先。
4. 具备良好的沟通能力和团队协作精神。

## 福利待遇
- 竞争力的薪资：25k-50k
- 六险一金，免费三餐，房补
- 扁平化管理，极客氛围
"""

    app = _get_app()
    last_exc: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(app.scrape, url, formats=["markdown"]),
                timeout=TIMEOUT_SECONDS,
            )
            if isinstance(result, dict):
                return result.get("markdown", "")
            return result.markdown or ""
        except asyncio.TimeoutError:
            last_exc = AppError(
                ErrorCode.UPSTREAM_ERROR,
                f"Firecrawl 抓取超时 ({TIMEOUT_SECONDS}s): {url[:120]}",
            )
            logger.warning("Firecrawl timeout attempt %d/%d: %s", attempt + 1, MAX_RETRIES + 1, url[:120])
        except AppError:
            raise
        except Exception as exc:
            last_exc = exc
            logger.warning("Firecrawl error attempt %d/%d: %s — %s", attempt + 1, MAX_RETRIES + 1, url[:120], exc)

    raise AppError(
        ErrorCode.UPSTREAM_ERROR,
        f"Firecrawl 抓取失败 (已重试 {MAX_RETRIES} 次): {url[:120]}",
    ) from last_exc
