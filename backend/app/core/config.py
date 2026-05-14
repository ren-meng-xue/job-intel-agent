from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str
    FIRECRAWL_API_KEY: str
    TAVILY_API_KEY: str
    DATABASE_URL: str
    REDIS_URL: str
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Auth 配置
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
