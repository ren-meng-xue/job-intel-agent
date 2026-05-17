#!/bin/bash
unset VIRTUAL_ENV

export http_proxy=http://127.0.0.1:10808
export https_proxy=http://127.0.0.1:10808
export ALL_PROXY=http://127.0.0.1:10808

BACKEND_PORT=8001
FRONTEND_PORT=3001

echo "🧹 清理残留进程..."
pkill -f "celery.*worker" 2>/dev/null || true
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

echo "🚀 启动 Docker 依赖..."
docker compose up -d postgres redis || exit 1

echo "等待数据库和 Redis 就绪..."
sleep 2

echo "🧹 清理 Celery 残留任务..."
(cd backend && uv run celery -A app.tasks:celery_app purge -f) || true

cleanup() {
    echo ""
    echo "🛑 正在停止所有服务..."
    kill $BACKEND_PID $CELERY_PID $FRONTEND_PID 2>/dev/null
    echo "✅ 服务已关闭。"
    exit
}

trap cleanup SIGINT

echo "后台服务启动中..."

echo "📡 [Backend] 启动中..."
(
    cd backend && \
    uv run uvicorn app.main:app \
    --reload \
    --host 0.0.0.0 \
    --port $BACKEND_PORT \
    > ../backend.log 2>&1
) &
BACKEND_PID=$!

echo "👷 [Celery] 启动中..."
(
    cd backend && \
    uv run celery \
    -A app.tasks:celery_app worker \
    --loglevel=info \
    > ../celery.log 2>&1
) &
CELERY_PID=$!

echo "🎨 [Frontend] 启动中..."
(
    cd frontend && \
    pnpm dev --port $FRONTEND_PORT \
    > ../frontend.log 2>&1
) &
FRONTEND_PID=$!

echo "-------------------------------------------------------"
echo "✅ 所有服务已在后台运行！"
echo "🌐 前端地址: http://localhost:$FRONTEND_PORT"
echo "🔧 后端地址: http://localhost:$BACKEND_PORT"
echo "📘 接口文档: http://localhost:$BACKEND_PORT/docs"
echo "-------------------------------------------------------"
echo "📝 日志:"
echo "   tail -f backend.log"
echo "   tail -f celery.log"
echo "   tail -f frontend.log"
echo "-------------------------------------------------------"
echo "💡 按 [Ctrl+C] 可同时停止所有服务。"

wait