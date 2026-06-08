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

RUN chmod +x start.sh

CMD ["./start.sh"]
