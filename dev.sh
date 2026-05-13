#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV="$BACKEND_DIR/.venv"

# 颜色输出
info()  { echo -e "\033[0;34m[dev]\033[0m $*"; }
ok()    { echo -e "\033[0;32m[dev]\033[0m $*"; }
err()   { echo -e "\033[0;31m[dev]\033[0m $*" >&2; }

# ── 前置检查 ──────────────────────────────────────────────
if ! docker info &>/dev/null; then
  err "Docker 未运行，请先启动 Docker Desktop"
  exit 1
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  err ".env 不存在，请先执行: cp .env.example .env"
  exit 1
fi

if [[ ! -d "$VENV" ]]; then
  err "后端依赖未安装，请先执行: cd backend && uv sync"
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  err "前端依赖未安装，请先执行: cd frontend && pnpm install"
  exit 1
fi

# 加载环境变量（导出到子进程）
set -a; source "$ROOT_DIR/.env"; set +a

# 激活后端 Python venv
source "$VENV/bin/activate"

# ── 基础设施（Docker）────────────────────────────────────
info "启动 postgres + redis ..."
docker compose -f "$ROOT_DIR/docker-compose.yml" up -d postgres redis

info "等待 PostgreSQL 就绪 ..."
for i in $(seq 1 30); do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T postgres \
       pg_isready -U "${POSTGRES_USER:-postgres}" &>/dev/null; then
    ok "PostgreSQL 已就绪"
    break
  fi
  if [[ $i -eq 30 ]]; then
    err "PostgreSQL 30s 内未就绪，请检查 docker 日志"
    exit 1
  fi
  sleep 1
done

# ── 数据库迁移（Alembic）────────────────────────────────
info "执行 alembic upgrade head ..."
(cd "$BACKEND_DIR" && alembic upgrade head)
ok "数据库迁移完成"

# ── 后台进程管理 ──────────────────────────────────────────
PIDS=()

cleanup() {
  echo ""
  info "正在关闭所有服务 ..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  docker compose -f "$ROOT_DIR/docker-compose.yml" stop postgres redis
  ok "已退出"
}
trap cleanup INT TERM

# ── 后端 FastAPI（uvicorn）───────────────────────────────
info "启动 FastAPI / uvicorn (port 8001) ..."
(cd "$BACKEND_DIR" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8001) &
PIDS+=($!)
ok "FastAPI PID=${PIDS[-1]}"

# ── Celery Worker ─────────────────────────────────────────
info "启动 Celery worker ..."
(cd "$BACKEND_DIR" && celery -A app.tasks:celery_app worker --loglevel=info) &
PIDS+=($!)
ok "Celery PID=${PIDS[-1]}"

# ── 前端 Next.js（前台，显示日志）────────────────────────
info "启动 Next.js / pnpm dev (port 3001) ..."
(cd "$FRONTEND_DIR" && pnpm dev --port 3001)
