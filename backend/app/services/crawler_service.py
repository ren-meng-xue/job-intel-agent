from firecrawl import FirecrawlApp

from app.core.config import settings

_app: FirecrawlApp | None = None


def _get_app() -> FirecrawlApp:
    global _app
    if _app is None:
        _app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
    return _app


async def scrape_url(url: str) -> str:
    """抓取 JD 页面，返回 Markdown 正文"""
    app = _get_app()
    result = app.scrape_url(url, params={"formats": ["markdown"]})
    return result.get("markdown", "")
