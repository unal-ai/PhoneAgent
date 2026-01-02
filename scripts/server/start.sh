#!/bin/bash
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0
#############################################################################
# 启动PhoneAgent服务器
# 启动API服务器、WebSocket服务器和FRP服务器
#############################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${GREEN}🚀 启动 PhoneAgent 服务器${NC}"
echo ""

# 检查环境
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠ .env 文件不存在，请先配置${NC}"
    exit 1
fi

if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${YELLOW}⚠ 虚拟环境不存在，请先运行安装脚本${NC}"
    exit 1
fi

# 创建必要目录
mkdir -p "$PROJECT_ROOT/data"
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/frp"

# 加载环境变量
source "$PROJECT_ROOT/.env" 2>/dev/null || true

cd "$PROJECT_ROOT"

# 1. 启动FRP服务器
echo "1️⃣  启动 FRP 服务器..."
if [ -f "frp/frps" ] && [ -f "frp/frps.ini" ]; then
    cd frp
    nohup ./frps -c frps.ini > frps.log 2>&1 &
    FRP_PID=$!
    echo -e "  ${GREEN}✓${NC} FRP 启动成功 (PID: $FRP_PID)"
    cd "$PROJECT_ROOT"
else
    echo -e "  ${YELLOW}⚠${NC} FRP 未安装，跳过"
fi

# 2. 启动WebSocket服务器
echo "2️⃣  启动 WebSocket 服务器..."
source venv/bin/activate
nohup python -m server.websocket.server > logs/websocket.log 2>&1 &
WS_PID=$!
echo -e "  ${GREEN}✓${NC} WebSocket 启动成功 (PID: $WS_PID)"

# 等待WebSocket服务器就绪
echo "    等待 WebSocket 服务器就绪..."
for i in {1..10}; do
    if curl -s http://127.0.0.1:9999/health > /dev/null 2>&1; then
        echo -e "    ${GREEN}✓${NC} WebSocket 服务器已就绪"
        break
    fi
    sleep 1
done

# 3. 启动API服务器
echo "3️⃣  启动 API 服务器..."
nohup uvicorn server.api.app:app --host 0.0.0.0 --port 8000 --reload > logs/api.log 2>&1 &
API_PID=$!
echo -e "  ${GREEN}✓${NC} API 启动成功 (PID: $API_PID)"

sleep 2

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  ${GREEN}✅ PhoneAgent 启动完成！${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "服务地址:"
echo "  API:       http://localhost:8000"
echo "  API文档:   http://localhost:8000/docs"
echo "  WebSocket: ws://localhost:9999"
echo ""
echo "管理命令:"
echo "  查看状态:  bash scripts/server/status.sh"
echo "  查看日志:  bash scripts/server/logs.sh"
echo "  停止服务:  bash scripts/server/stop.sh"
echo ""

