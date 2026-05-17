
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str
    FIRECRAWL_API_KEY: str
    TAVILY_API_KEY: str
    DATABASE_URL: str
    REDIS_URL: str
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # 运行环境
    ENV: str = "development"

    # Auth 配置
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    COOKIE_SECURE: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        is_default_key = self.SECRET_KEY == "dev-secret-key-change-in-production"
        if self.ENV == "production" and is_default_key:
            raise ValueError(
                "SECRET_KEY 不能使用默认值，生产环境必须通过环境变量设置 SECRET_KEY"
            )


settings = Settings()
