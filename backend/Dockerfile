FROM python:3.12-slim

WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 先复制依赖文件，利用 Docker layer 缓存
COPY backend/pyproject.toml backend/uv.lock ./

# 安装依赖（不安装项目本身，仅依赖）
RUN uv sync --frozen --no-install-project --no-dev

# 再复制源码
COPY backend/ .

CMD ["sh", "-c", "uv run celery -A app.tasks:celery_app worker --loglevel=info & uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
