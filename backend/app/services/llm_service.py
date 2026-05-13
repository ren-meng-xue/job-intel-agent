from openai import AsyncOpenAI

from app.core.config import settings

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def chat(messages: list[dict], model: str = "gpt-4o") -> str:
    client = _get_client()
    response = await client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content
