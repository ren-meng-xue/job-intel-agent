from tavily import TavilyClient

from app.core.config import settings

_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _client


async def search(query: str, max_results: int = 5) -> list[dict]:
    """公司调研搜索"""
    client = _get_client()
    response = client.search(query, max_results=max_results)
    return response.get("results", [])
