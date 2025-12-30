#!/data/data/com.termux/files/usr/bin/bash
#############################################################################
# PhoneAgent Termux 客户端安装脚本
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0
# 
# 架构说明：
# - FRP: 提供ADB端口转发，服务端通过扫描FRP端口发现设备
# - WebSocket: 实时任务下发和结果上报通道
# - ADB: 提供设备控制能力
# 
# 🚀 快速安装（国内推荐，自动选择最快镜像）:
#
#   【方式1 - jsDelivr CDN（推荐）】
#     bash <(curl -s https://cdn.jsdelivr.net/gh/tmwgsicp/PhoneAgent@main/client/install_termux.sh)
#
#   【方式2 - ghproxy 镜像】
#     bash <(curl -s https://mirror.ghproxy.com/https://raw.githubusercontent.com/tmwgsicp/PhoneAgent/main/client/install_termux.sh)
#
#   【方式3 - gh.ddlc.top 镜像】
#     bash <(curl -s https://gh.ddlc.top/https://raw.githubusercontent.com/tmwgsicp/PhoneAgent/main/client/install_termux.sh)
#
#   【方式4 - 官方GitHub（需要VPN）】
#     bash <(curl -s https://raw.githubusercontent.com/tmwgsicp/PhoneAgent/main/client/install_termux.sh)
#
# 💡 wget 方式（如果 curl 不可用）:
#     wget -O- https://cdn.jsdelivr.net/gh/tmwgsicp/PhoneAgent@main/client/install_termux.sh | bash
#
# 🌐 如果有云服务器，可以更快：
#     # 1. 在云服务器下载脚本
#     # 2. python3 -m http.server 8888
#     # 3. bash <(curl -s http://your-server:8888/install_termux.sh)
#
#############################################################################

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_step() {
    echo "" >&2
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
    echo -e "${BLUE}$1${NC}" >&2
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
    echo "" >&2
}

#############################################################################
# 辅助函数：检测端口是否被占用（本地检测）
#############################################################################

check_port_available() {
    local port="$1"
    if netstat -tuln 2>/dev/null | grep -q ":${port} "; then
        return 1  # 端口被占用
    else
        return 0  # 端口可用
    fi
}

#############################################################################
# 辅助函数：从服务端获取已占用的端口列表
#############################################################################

get_server_used_ports() {
    local server_ip="$1"
    local used_ports
    
    # 检查curl是否可用
    if ! command -v curl &> /dev/null; then
        return 1
    fi
    
    # 尝试从服务端API获取已注册的设备端口
    # 修正：使用正确的API服务器端口（8000），而不是WebSocket端口（9999）
    local api_url="http://${server_ip}:8000/api/v1/devices/scanned"
    local response
    local http_code
    
    # 尝试连接服务端API（优先尝试8000端口）
    response=$(curl -s --connect-timeout 3 --max-time 5 -w "\n%{http_code}" "$api_url" 2>/dev/null)
    http_code=$(echo "$response" | tail -n1)
    response=$(echo "$response" | sed '$d')
    
    # 检查HTTP状态码
    if [ "$http_code" = "200" ]; then
        # 解析JSON，提取frp_port字段
        # 使用简单的grep和sed提取（避免依赖jq）
        used_ports=$(echo "$response" | grep -o '"frp_port":[0-9]*' | grep -o '[0-9]*')
        
        if [ -n "$used_ports" ]; then
            log_info "📡 从服务端获取到已占用端口列表 (API: 8000)"
            echo "$used_ports"
            return 0
        else
            # API返回成功但没有设备
            log_info "📡 服务端暂无其他设备"
            return 0
        fi
    else
        # 如果8000端口失败，尝试9999端口（兼容旧版本）
        log_warn "   8000端口无响应 (HTTP $http_code)，尝试9999端口..."
        
        api_url="http://${server_ip}:9999/api/v1/devices/scanned"
        response=$(curl -s --connect-timeout 3 --max-time 5 -w "\n%{http_code}" "$api_url" 2>/dev/null)
        http_code=$(echo "$response" | tail -n1)
        response=$(echo "$response" | sed '$d')
        
        if [ "$http_code" = "200" ]; then
            used_ports=$(echo "$response" | grep -o '"frp_port":[0-9]*' | grep -o '[0-9]*')
            
            if [ -n "$used_ports" ]; then
                log_info "📡 从服务端获取到已占用端口列表 (API: 9999)"
                echo "$used_ports"
                return 0
            else
                log_info "📡 服务端暂无其他设备"
                return 0
            fi
        else
            # 两个端口都失败
            log_warn "   无法连接到服务端API (8000和9999端口均失败)"
            log_warn "   HTTP状态码: 8000=$http_code"
            return 1
        fi
    fi
}

#############################################################################
# 辅助函数：检测端口是否在服务端被占用
#############################################################################

check_port_used_on_server() {
    local port="$1"
    local used_ports="$2"
    
    if [ -z "$used_ports" ]; then
        return 0  # 没有已占用端口列表，认为可用
    fi
    
    # 检查端口是否在已占用列表中
    if echo "$used_ports" | grep -qw "$port"; then
        return 1  # 端口已被占用
    else
        return 0  # 端口可用
    fi
}

#############################################################################
# 辅助函数：自动生成设备名称
#############################################################################

generate_device_name() {
    # 尝试获取手机型号
    local model=$(getprop ro.product.model 2>/dev/null | tr -d ' ')
    if [ -n "$model" ]; then
        # 使用型号_随机数作为设备名
        echo "${model}_$(date +%s | tail -c 4)"
    else
        # 使用默认名称
        echo "device_$(date +%s | tail -c 4)"
    fi
}

#############################################################################
# 辅助函数：查找可用端口（增强版：检测本地+服务端）
#############################################################################

find_available_port() {
    local start_port="$1"
    local max_tries="${2:-99}"  # 默认100个端口（0-99，即6100-6199）
    local server_ip="$3"
    local port="$start_port"
    local end_port=$((start_port + max_tries))
    
    # 获取服务端已占用的端口列表
    local server_used_ports=""
    if [ -n "$server_ip" ]; then
        server_used_ports=$(get_server_used_ports "$server_ip")
        if [ $? -eq 0 ] && [ -n "$server_used_ports" ]; then
            local used_count
            used_count=$(echo "$server_used_ports" | wc -l)
            log_info "   服务端已占用: ${used_count} 个端口"
            # 只显示前5个，避免输出过长
            local preview
            preview=$(echo "$server_used_ports" | head -5 | tr '\n' ',' | sed 's/,$//')
            if [ "$used_count" -gt 5 ]; then
                log_info "   示例端口: ${preview}... (共${used_count}个)"
            else
                log_info "   已占用端口: ${preview}"
            fi
        else
            log_warn "   无法获取服务端端口信息，仅检测本地端口"
        fi
    fi
    
    # 查找同时满足本地和服务端都未占用的端口
    local i
    for i in $(seq 0 "$max_tries"); do
        # 检测本地端口
        if check_port_available "$port"; then
            # 检测服务端端口
            if check_port_used_on_server "$port" "$server_used_ports"; then
                echo "$port"
                return 0
            else
                log_info "   端口 $port 在服务端已被占用，继续查找..."
            fi
        else
            log_info "   端口 $port 在本地已被占用，继续查找..."
        fi
        port=$((port + 1))
    done
    
    log_error "在 ${start_port}-${end_port} 范围内未找到可用端口"
    return 1
}

#############################################################################
# 步骤 1: 获取配置
#############################################################################

get_config() {
    log_step "📝 步骤 1/6: 配置信息"
    
    log_info "只需输入4个必要参数，其他参数自动配置！"
    log_info "必填参数: 后端服务器IP、FRP Token、连接方式、前端访问地址"
    echo ""
    
    # 服务器IP（必填，后端服务器）
    read -p "后端服务器IP地址: " SERVER_IP
    while [ -z "$SERVER_IP" ]; do
        log_warn "服务器IP不能为空"
        read -p "后端服务器IP地址: " SERVER_IP
    done
    
    # FRP Token（必填）
    read -p "FRP Token: " FRP_TOKEN
    while [ -z "$FRP_TOKEN" ]; do
        log_warn "FRP Token不能为空"
        read -p "FRP Token: " FRP_TOKEN
    done
    
    echo ""
    log_info "正在自动配置其他参数..."
    
    # 自动生成设备名称
    AUTO_DEVICE_NAME=$(generate_device_name)
    log_info "自动生成设备名称: $AUTO_DEVICE_NAME"
    read -p "使用此名称? (直接回车确认, 或输入自定义名称): " DEVICE_NAME
    DEVICE_NAME=${DEVICE_NAME:-$AUTO_DEVICE_NAME}
    
    # FRP端口配置（支持自动和手动两种模式）
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "FRP端口配置:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "【推荐】自动分配 - 智能检测可用端口"
    echo "  - 自动检测本地端口占用"
    echo "  - 尝试查询服务端已占用端口"
    echo "  - 从6100开始查找可用端口"
    echo ""
    echo "【手动】手动指定 - 自己指定端口号"
    echo "  - 适合：明确知道要使用的端口"
    echo "  - 适合：服务端API不可用时"
    echo "  - 范围：6100-6199（默认扫描范围）"
    echo ""
    read -p "选择配置方式 (1=自动分配, 2=手动指定, 默认: 1): " PORT_MODE
    PORT_MODE=${PORT_MODE:-1}
    
    if [ "$PORT_MODE" = "2" ]; then
        # 手动指定端口
        echo ""
        log_info "手动指定端口模式"
        read -p "请输入FRP端口号 (6100-6199推荐, 6200-65535需修改服务端): " MANUAL_PORT
        
        # 验证端口号
        if [ -z "$MANUAL_PORT" ]; then
            log_error "端口号不能为空"
            exit 1
        fi
        
        if [ "$MANUAL_PORT" -lt 6100 ] || [ "$MANUAL_PORT" -gt 65535 ]; then
            log_error "端口号必须在 6100-65535 范围内"
            exit 1
        fi
        
        # 检查本地端口是否被占用
        if ! check_port_available "$MANUAL_PORT"; then
            log_error "端口 $MANUAL_PORT 在本地已被占用，请选择其他端口"
            exit 1
        fi
        
        REMOTE_PORT=$MANUAL_PORT
        log_info "✅ 使用手动指定端口: $REMOTE_PORT"
        
        if [ "$REMOTE_PORT" -ge 6200 ]; then
            log_warn "⚠️  端口超出默认扫描范围(6100-6199)"
            log_warn "    需要修改服务端配置: server/services/device_scanner.py"
            log_warn "    将 port_range_end 修改为 $REMOTE_PORT 或更大"
        fi
    else
        # 自动分配端口
        log_info "🔍 正在智能分配FRP端口..."
        log_info "   检测范围: 6100-6199 (与服务端扫描范围一致)"
        
        AUTO_PORT=$(find_available_port 6100 99 "$SERVER_IP")
        if [ $? -eq 0 ]; then
            log_info "✅ 智能分配端口: $AUTO_PORT"
            log_info "   本地检测: ✓ 未占用"
            REMOTE_PORT=$AUTO_PORT
        else
            log_error "❌ 自动分配失败！"
            log_error "   6100-6199 范围内未找到可用端口"
            echo ""
            log_warn "可能的原因:"
            log_warn "  1. 服务端API服务未启动（需要启动FastAPI服务，默认8000端口）"
            log_warn "  2. 网络连接问题（无法连接到服务器）"
            log_warn "  3. 端口范围已全部占用（6100-6199范围内所有端口都已使用）"
            echo ""
            log_warn "建议："
            echo "  1. 重新运行脚本，选择【手动指定】模式"
            echo "  2. 手动指定一个未使用的端口（如 6100, 6101, 6102...）"
            echo "  3. 检查服务端FastAPI服务是否运行（端口8000）"
            echo "  4. 或者清理服务端的离线设备后重试"
            echo ""
            log_info "💡 如何查看服务端已占用端口:"
            echo "     curl http://${SERVER_IP}:8000/api/v1/devices/scanned | grep frp_port"
            echo ""
            read -p "是否现在手动指定端口? (y/n): " RETRY_MANUAL
            
            if [ "$RETRY_MANUAL" = "y" ]; then
                read -p "请输入FRP端口号 (6100-6199): " MANUAL_PORT
                if [ -z "$MANUAL_PORT" ] || [ "$MANUAL_PORT" -lt 6100 ] || [ "$MANUAL_PORT" -gt 6199 ]; then
                    log_error "无效的端口号，退出安装"
                    exit 1
                fi
                
                if ! check_port_available "$MANUAL_PORT"; then
                    log_error "端口 $MANUAL_PORT 在本地已被占用，退出安装"
                    exit 1
                fi
                
                REMOTE_PORT=$MANUAL_PORT
                log_info "✅ 使用手动指定端口: $REMOTE_PORT"
            else
                log_info "退出安装"
                exit 0
            fi
        fi
    fi
    
    # WebSocket连接方式选择
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "WebSocket连接方式:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "【推荐】简单模式 - 直连IP"
    echo "  - 适合：开发测试、快速体验、前后端同服务器"
    echo "  - 优点：配置简单，零成本"
    echo "  - 限制：前端需用HTTP访问（不支持语音功能）"
    echo ""
    echo "【可选】完整模式 - 域名代理"
    echo "  - 适合：生产环境、需要HTTPS或语音功能"
    echo "  - 优点：支持HTTPS、语音功能、灵活部署"
    echo "  - 要求：需要域名、SSL证书、Nginx配置"
    echo ""
    read -p "选择连接方式 (1=直连IP, 2=域名代理, 默认: 1): " WS_MODE
    WS_MODE=${WS_MODE:-1}
    
    echo ""
    if [ "$WS_MODE" = "2" ]; then
        # 域名代理模式
        read -p "请输入您的域名 (如: phoneagent.example.com): " WS_DOMAIN
        while [ -z "$WS_DOMAIN" ]; do
            log_warn "域名不能为空"
            read -p "请输入您的域名: " WS_DOMAIN
        done
        # 使用 frp_port 作为唯一标识，设备名称通过 device_online 消息上报
        WS_URL="wss://${WS_DOMAIN}/device-ws/device/${REMOTE_PORT}"
        log_info "✅ 使用域名代理模式"
        log_warn "注意：需要配置Nginx反向代理，详见项目文档"
    else
        # 直连IP模式（默认）
        read -p "前端服务器IP (直接回车使用后端IP ${SERVER_IP}): " FRONTEND_IP
        FRONTEND_IP=${FRONTEND_IP:-$SERVER_IP}
        # 使用 frp_port 作为唯一标识，设备名称通过 device_online 消息上报
        WS_URL="ws://${FRONTEND_IP}:9999/ws/device/${REMOTE_PORT}"
        log_info "✅ 使用直连IP模式"
        log_warn "注意：前端需用HTTP访问（不能用HTTPS）"
    fi
    
    echo ""
    log_info "配置信息:"
    log_info "  服务器IP: $SERVER_IP"
    log_info "  FRP Token: $FRP_TOKEN"
    log_info "  设备名称: $DEVICE_NAME"
    log_info "  FRP远程端口: $REMOTE_PORT"
    log_info "  WebSocket URL: $WS_URL"
    echo ""
    
    read -p "确认以上配置? (y/n, 默认: y): " CONFIRM
    CONFIRM=${CONFIRM:-y}
    if [ "$CONFIRM" != "y" ]; then
        log_warn "已取消安装"
        exit 0
    fi
}

#############################################################################
# 步骤 2: 安装依赖
#############################################################################

# 配置Termux国内镜像源（自动选择最快的）
configure_termux_mirror() {
    log_info "正在自动选择最快的Termux镜像源..."
    
    # 直接自动测速选择
    MIRROR_URL=$(select_fastest_mirror)
    
    if [ -z "$MIRROR_URL" ]; then
        log_warn "自动选择失败，使用清华源"
        MIRROR_URL="https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main"
    fi
    
    log_info "✅ 已选择最优镜像源"
    log_info "正在配置..."
    
    # 备份原配置
    if [ -f "$PREFIX/etc/apt/sources.list" ]; then
        cp "$PREFIX/etc/apt/sources.list" "$PREFIX/etc/apt/sources.list.bak" 2>/dev/null || true
    fi
    
    # 写入新配置
    echo "deb ${MIRROR_URL} stable main" > "$PREFIX/etc/apt/sources.list"
    
    log_info "✅ 镜像源配置完成"
}

# 自动选择最快的镜像源（无交互）
select_fastest_mirror() {
    local mirrors=(
        "https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main"
        "https://mirrors.bfsu.edu.cn/termux/apt/termux-main"
        "https://mirrors.nju.edu.cn/termux/apt/termux-main"
        "https://mirrors.ustc.edu.cn/termux/apt/termux-main"
    )
    
    local fastest_mirror=""
    local fastest_time=999999
    local DEFAULT_FAST_RESPONSE_MS=100  # 小于1秒的响应默认估计为100ms
    
    for mirror in "${mirrors[@]}"; do
        local domain
        domain=$(echo "$mirror" | awk -F/ '{print $3}')
        log_info "  测试 ${domain} ..."
        
        # 使用秒级时间戳（Termux/Android 不支持 %N 纳秒格式）
        local start_time
        start_time=$(date +%s)
        
        if curl -s --connect-timeout 2 --max-time 3 "$mirror" > /dev/null 2>&1; then
            local end_time
            end_time=$(date +%s)
            
            # 计算耗时（秒转毫秒）
            local duration
            local diff=$((end_time - start_time))
            if [ "$diff" -eq 0 ]; then
                duration=$DEFAULT_FAST_RESPONSE_MS  # 小于1秒，使用默认估计值
            else
                duration=$((diff * 1000))
            fi
            
            log_info "    ✓ 响应: ${duration}ms"
            
            if [ "$duration" -lt "$fastest_time" ]; then
                fastest_time=$duration
                fastest_mirror=$mirror
            fi
        else
            log_warn "    ✗ 超时"
        fi
    done
    
    if [ -z "$fastest_mirror" ]; then
        # 所有测试失败，返回清华源作为后备
        echo "https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main"
    else
        local fastest_domain
        fastest_domain=$(echo "$fastest_mirror" | awk -F/ '{print $3}')
        log_info "✅ 最优: ${fastest_domain} (${fastest_time}ms)"
        echo "$fastest_mirror"
    fi
}

# 智能下载：自动测速选择最快镜像源下载文件
# 用法: download_with_fastest_mirror "url1" "url2" "url3" ...
download_with_fastest_mirror() {
    local mirrors=("$@")
    
    if [ "${#mirrors[@]}" -eq 0 ]; then
        log_error "没有提供镜像源URL"
        return 1
    fi
    
    log_info "正在测速选择最快镜像源..."
    
    local fastest_mirror=""
    local fastest_time=999999
    local tested_count=0
    local DEFAULT_FAST_RESPONSE_MS=100  # 小于1秒的响应默认估计为100ms
    
    # 并发测速所有镜像源（最多前3个）
    for mirror in "${mirrors[@]}"; do
        [ "$tested_count" -ge 3 ] && break  # 只测试前3个，加快速度
        
        local domain
        domain=$(echo "$mirror" | awk -F/ '{print $3}')
        
        # 使用秒级时间戳（Termux/Android 不支持 %N 纳秒格式）
        local start_time
        start_time=$(date +%s)
        
        # 使用HEAD请求测速（更快）
        if curl -I -s --connect-timeout 2 --max-time 3 "$mirror" > /dev/null 2>&1; then
            local end_time
            end_time=$(date +%s)
            
            # 计算耗时（秒转毫秒）
            local duration
            local diff=$((end_time - start_time))
            if [ "$diff" -eq 0 ]; then
                duration=$DEFAULT_FAST_RESPONSE_MS  # 小于1秒，使用默认估计值
            else
                duration=$((diff * 1000))
            fi
            
            log_info "  ✓ ${domain}: ${duration}ms"
            
            if [ "$duration" -lt "$fastest_time" ]; then
                fastest_time=$duration
                fastest_mirror=$mirror
            fi
        else
            log_info "  ✗ ${domain}: 超时"
        fi
        
        tested_count=$((tested_count + 1))
    done
    
    # 如果前3个都失败，尝试剩余的
    if [ -z "$fastest_mirror" ] && [ "${#mirrors[@]}" -gt 3 ]; then
        log_warn "前3个镜像源不可用，尝试其他镜像..."
        for mirror in "${mirrors[@]:3}"; do
            local domain
            domain=$(echo "$mirror" | awk -F/ '{print $3}')
            log_info "  尝试 ${domain} ..."
            
            if curl -I -s --connect-timeout 2 --max-time 3 "$mirror" > /dev/null 2>&1; then
                fastest_mirror=$mirror
                log_info "  ✓ ${domain} 可用"
                break
            fi
        done
    fi
    
    if [ -z "$fastest_mirror" ]; then
        log_error "所有镜像源均不可用"
        return 1
    fi
    
    local fastest_domain
    fastest_domain=$(echo "$fastest_mirror" | awk -F/ '{print $3}')
    log_info "🚀 使用最快镜像: ${fastest_domain}"
    
    # 开始下载
    local filename
    filename=$(basename "$fastest_mirror")
    
    if wget --progress=bar:force:noscroll --timeout=60 -O "$filename" "$fastest_mirror" 2>&1; then
        log_info "✅ 下载成功: ${filename}"
        return 0
    else
        log_error "下载失败: ${filename}"
        return 1
    fi
}

# 配置pip国内镜像
configure_pip_mirror() {
    log_info "配置pip国内镜像源..."
    
    mkdir -p ~/.pip
    cat > ~/.pip/pip.conf << EOF
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
extra-index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = pypi.tuna.tsinghua.edu.cn mirrors.aliyun.com
timeout = 120

[install]
trusted-host = pypi.tuna.tsinghua.edu.cn mirrors.aliyun.com
EOF
    
    log_info "✅ pip镜像源配置完成"
}

install_dependencies() {
    log_step "📦 步骤 2/6: 安装依赖"
    
    # 配置镜像源
    configure_termux_mirror
    configure_pip_mirror
    
    log_info "更新软件包列表..."
    pkg update -y || {
        log_error "软件包列表更新失败，尝试清理缓存..."
        pkg clean
        pkg update -y
    }
    
    log_info "安装必要软件包..."
    pkg install -y \
        python \
        termux-api \
        android-tools \
        wget \
        curl \
        git || {
        log_error "软件包安装失败"
        log_info "尝试逐个安装..."
        for pkg_name in python termux-api android-tools wget curl git; do
            log_info "  安装 $pkg_name ..."
            pkg install -y $pkg_name || log_warn "  $pkg_name 安装失败，继续..."
        done
    }
    
    log_info "创建Python虚拟环境..."
    cd ~ || exit 1
    if [ ! -d "phoneagent_venv" ]; then
        python -m venv phoneagent_venv
    fi
    
    source phoneagent_venv/bin/activate
    
    log_info "安装Python依赖..."
    pip install --upgrade pip -q || pip install --upgrade pip
    pip install websockets -q || pip install websockets
    
    deactivate
    
    log_info "✅ 依赖安装完成"
}

#############################################################################
# 步骤 3: 下载并配置 FRP
#############################################################################

setup_frp() {
    log_step "🔧 步骤 3/6: 配置 FRP 客户端"
    
    cd ~ || exit 1
    
    local FRP_VERSION="0.52.0"
    
    # 自动检测系统架构
    local MACHINE_ARCH=$(uname -m)
    local FRP_ARCH=""
    
    case "$MACHINE_ARCH" in
        x86_64)
            FRP_ARCH="amd64"
            ;;
        aarch64)
            FRP_ARCH="arm64"
            ;;
        armv7l)
            FRP_ARCH="arm"
            ;;
        i386|i686)
            FRP_ARCH="386"
            ;;
        *)
            log_error "不支持的架构: $MACHINE_ARCH"
            log_warn "支持的架构: x86_64, aarch64, armv7l, i386, i686"
            exit 1
            ;;
    esac
    
    log_info "检测到系统架构: $MACHINE_ARCH → FRP 架构: $FRP_ARCH"
    
    local FRP_FILE="frp_${FRP_VERSION}_linux_${FRP_ARCH}.tar.gz"
    
    if [ ! -f "$FRP_FILE" ]; then
        log_info "下载 FRP ${FRP_VERSION} (${FRP_ARCH})..."
        
        # 自动选择最快的镜像源下载
        local MIRRORS=(
            "https://mirror.ghproxy.com/https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${FRP_FILE}"
            "https://ghp.ci/https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${FRP_FILE}"
            "https://gh.ddlc.top/https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${FRP_FILE}"
            "https://github.moeyy.xyz/https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${FRP_FILE}"
            "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${FRP_FILE}"
        )
        
        if ! download_with_fastest_mirror "${MIRRORS[@]}"; then
            log_error "FRP 下载失败"
            log_warn "可以稍后手动下载: wget https://mirror.ghproxy.com/https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${FRP_FILE}"
            exit 1
        fi
    else
        log_info "FRP 安装包已存在，跳过下载"
    fi
    
    log_info "解压 FRP..."
    tar -xzf "$FRP_FILE" || exit 1
    
    local FRP_DIR="frp_${FRP_VERSION}_linux_${FRP_ARCH}"
    
    if [ -d "frp" ]; then
        rm -rf frp
    fi
    
    mv "$FRP_DIR" frp || exit 1
    cd frp || exit 1
    
    log_info "创建 FRP 配置文件..."
    cat > frpc.ini << EOF
[common]
server_addr = ${SERVER_IP}
server_port = 7000
token = ${FRP_TOKEN}
log_file = ./frpc.log
log_level = info

[adb_${DEVICE_NAME}]
type = tcp
local_ip = 127.0.0.1
local_port = 5555
remote_port = ${REMOTE_PORT}
EOF
    
    log_info "✅ FRP 配置完成"
}

#############################################################################
# 步骤 4: 配置 ADB
#############################################################################

setup_adb() {
    log_step "📱 步骤 4/6: 配置 ADB"
    
    log_info "启动 ADB 服务..."
    adb kill-server 2>/dev/null || true
    
    # 禁用模拟器自动连接
    export ADB_MDNS_AUTO_CONNECT=0
    export ADB_LIBUSB=0
    
    adb start-server
    
    log_info "等待 ADB 服务启动..."
    sleep 2
    
    # 连接到本地 adbd (5555)
    log_info "连接到系统 ADB Daemon..."
    adb connect localhost:5555 >/dev/null 2>&1
    sleep 2
    
    # 断开可能存在的模拟器连接
    adb disconnect emulator-5554 >/dev/null 2>&1 || true
    
    # 验证连接
    if adb -s localhost:5555 shell echo "test" 2>/dev/null | grep -q "test"; then
        log_info "✅ ADB 连接成功"
        
        # 获取设备信息
        local model=$(adb -s localhost:5555 shell getprop ro.product.model 2>/dev/null | tr -d '\r')
        local resolution=$(adb -s localhost:5555 shell wm size 2>/dev/null | grep "Physical" | cut -d: -f2 | tr -d ' \r')
        
        log_info "📱 设备型号: ${model}"
        log_info "📺 屏幕分辨率: ${resolution}"
    else
        log_error "❌ ADB 连接失败"
        log_warn ""
        log_warn "⚠️  需要先通过 USB 启用 TCP 模式："
        log_warn "  1. 用 USB 线连接手机到电脑"
        log_warn "  2. 在电脑上执行: adb tcpip 5555"
        log_warn "  3. 断开 USB，重新运行此脚本"
        log_warn ""
        log_warn "或者："
        log_warn "  1. 开启开发者选项 -> 无线调试"
        log_warn "  2. 在 Termux 中执行:"
        log_warn "     su -c 'setprop service.adb.tcp.port 5555'"
        log_warn "     su -c 'stop adbd && start adbd'"
        return 1
    fi
    
    log_info "💡 说明: 使用系统 adbd (tcp:5555)"
    log_info "💡 FRP将映射5555端口到服务器，实现远程ADB控制"
}

#############################################################################
# 步骤 4.5: 安装 scrcpy-server（用于 H.264 实时预览）
#############################################################################

setup_scrcpy_server() {
    log_step "📺 步骤 4.5/6: 安装 scrcpy-server"
    
    cd ~ || exit 1
    
    local SCRCPY_VERSION="3.3.3"
    local SCRCPY_SERVER_FILE="scrcpy-server-v${SCRCPY_VERSION}"
    local TARGET_PATH="/data/local/tmp/scrcpy-server"
    local LOCAL_CACHE_PATH="$HOME/scrcpy-server"
    
    # 检查是否已安装（使用文件系统检查，更可靠）
    if [ -f "$TARGET_PATH" ]; then
        log_info "scrcpy-server 已存在，跳过安装"
        # 备份一份到本地，避免 /data/local/tmp 被清理后无法恢复
        cp -f "$TARGET_PATH" "$LOCAL_CACHE_PATH" 2>/dev/null || true
        return 0
    fi
    
    log_info "下载 scrcpy-server ${SCRCPY_VERSION}..."
    
    # 自动选择最快的镜像源下载
    local MIRRORS=(
        "https://mirror.ghproxy.com/https://github.com/Genymobile/scrcpy/releases/download/v${SCRCPY_VERSION}/${SCRCPY_SERVER_FILE}"
        "https://ghp.ci/https://github.com/Genymobile/scrcpy/releases/download/v${SCRCPY_VERSION}/${SCRCPY_SERVER_FILE}"
        "https://gh.ddlc.top/https://github.com/Genymobile/scrcpy/releases/download/v${SCRCPY_VERSION}/${SCRCPY_SERVER_FILE}"
        "https://github.moeyy.xyz/https://github.com/Genymobile/scrcpy/releases/download/v${SCRCPY_VERSION}/${SCRCPY_SERVER_FILE}"
        "https://github.com/Genymobile/scrcpy/releases/download/v${SCRCPY_VERSION}/${SCRCPY_SERVER_FILE}"
    )
    
    if ! download_with_fastest_mirror "${MIRRORS[@]}"; then
        log_error "scrcpy-server 下载失败"
        log_warn "⚠️  实时预览功能将不可用，但不影响其他功能"
        log_warn ""
        log_warn "可以稍后手动安装:"
        log_warn "  wget https://mirror.ghproxy.com/https://github.com/Genymobile/scrcpy/releases/download/v${SCRCPY_VERSION}/${SCRCPY_SERVER_FILE}"
        log_warn "  cp ${SCRCPY_SERVER_FILE} /data/local/tmp/scrcpy-server"
        log_warn "  chmod 755 /data/local/tmp/scrcpy-server"
        return 0  # 返回成功，允许继续安装
    fi
    
    log_info "安装 scrcpy-server 到设备..."
    # 保留一份本地副本，防止 /data/local/tmp 被系统清理
    cp -f "${SCRCPY_SERVER_FILE}" "$LOCAL_CACHE_PATH" 2>/dev/null || true
    
    # 方案1：直接复制（最简单，推荐）
    if cp "${SCRCPY_SERVER_FILE}" "$TARGET_PATH" 2>/dev/null && chmod 755 "$TARGET_PATH" 2>/dev/null; then
        log_info "✅ scrcpy-server 安装成功 (方案1: 直接复制)"
        log_info "✓ 文件大小: $(ls -lh $TARGET_PATH | awk '{print $5}')"
        rm -f "${SCRCPY_SERVER_FILE}"
        return 0
    fi
    
    log_warn "⚠️  方案1失败，尝试方案2..."
    
    # 方案2：通过 adb shell 复制（Termux特有方案）
    # 原理：adb shell 可以直接操作本机，通过 cat 命令传输文件
    if adb shell "cat > $TARGET_PATH" < "${SCRCPY_SERVER_FILE}" 2>/dev/null; then
        adb shell "chmod 755 $TARGET_PATH" 2>/dev/null
        
        # 验证
        if adb shell "ls $TARGET_PATH" 2>/dev/null | grep -q "scrcpy-server"; then
            log_info "✅ scrcpy-server 安装成功 (方案2: adb shell)"
            log_info "✓ scrcpy-server 验证通过"
            rm -f "${SCRCPY_SERVER_FILE}"
            return 0
        fi
    fi
    
    log_warn "⚠️  方案2失败，尝试方案3..."
    
    # 方案3：使用root权限（如果有）
    if command -v su >/dev/null 2>&1; then
        if su -c "cp ${SCRCPY_SERVER_FILE} $TARGET_PATH && chmod 755 $TARGET_PATH" 2>/dev/null; then
            log_info "✅ scrcpy-server 安装成功 (方案3: root权限)"
            rm -f "${SCRCPY_SERVER_FILE}"
            return 0
        fi
    fi
    
    log_warn "⚠️  所有方案都失败，使用备用方案..."
    
    # 备用方案：安装到Termux临时目录
    local TERMUX_TMP="/data/data/com.termux/files/usr/tmp/scrcpy-server"
    if cp "${SCRCPY_SERVER_FILE}" "$TERMUX_TMP" 2>/dev/null && chmod 755 "$TERMUX_TMP" 2>/dev/null; then
        log_warn "⚠️  scrcpy-server 已安装到备用位置: $TERMUX_TMP"
        log_warn "⚠️  实时预览可能无法使用"
        log_warn ""
        log_warn "建议手动复制到标准位置:"
        log_warn "  su -c 'cp $TERMUX_TMP /data/local/tmp/scrcpy-server'"
        log_warn "  su -c 'chmod 755 /data/local/tmp/scrcpy-server'"
    else
        log_error "scrcpy-server 安装失败"
        log_warn "⚠️  实时预览功能将不可用，但不影响其他功能"
    fi
    
    # 清理下载文件
    rm -f "${SCRCPY_SERVER_FILE}"
    return 0  # 返回成功，允许继续安装
}

#############################################################################
# 步骤 5: 创建WebSocket客户端
#############################################################################

create_ws_client() {
    log_step "🔌 步骤 5/6: 创建 WebSocket 客户端"
    
    cd ~ || exit 1
    
    cat > ws_client_simple.py << 'PYTHON_EOF'
#!/usr/bin/env python3
"""
PhoneAgent WebSocket 客户端 - 设备管理专用

功能：设备注册、在线状态维护、设备信息上报
架构：所有任务执行（网页端/手机App）统一走 FRP + ADB 通道
"""
import asyncio
import websockets
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/data/com.termux/files/home/ws_client_simple.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def handle_task(websocket, task_data):
    """
    处理服务端消息（心跳、状态查询等）
    注：任务执行走FRP+ADB通道，此处仅处理设备管理相关消息
    """
    try:
        task_id = task_data.get("task_id")
        task_type = task_data.get("type")
        
        logger.info(f"📥 收到任务: {task_type} (ID: {task_id})")
        
        # WebSocket仅用于设备管理，任务执行统一通过FRP+ADB通道
        # 此处仅做确认响应
        
        # 发送任务结果
        result = {
            "type": "task_result",
            "task_id": task_id,
            "status": "success",
            "message": "任务已接收（演示）"
        }
        
        await websocket.send(json.dumps(result))
        logger.info(f"✅ 任务结果已上报: {task_id}")
        
    except Exception as e:
        logger.error(f"❌ 任务处理失败: {e}")


async def get_device_specs():
    """获取设备规格信息"""
    import subprocess
    
    specs = {
        "device_id": "",
        "device_name": "",
        "model": "Unknown",
        "android_version": "Unknown",
        "screen_resolution": "Unknown",
        "battery": 100
    }
    
    try:
        # 获取型号
        result = subprocess.run(
            ["adb", "shell", "getprop", "ro.product.model"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            specs["model"] = result.stdout.strip()
        
        # 获取Android版本
        result = subprocess.run(
            ["adb", "shell", "getprop", "ro.build.version.release"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            specs["android_version"] = result.stdout.strip()
        
        # 获取屏幕分辨率
        result = subprocess.run(
            ["adb", "shell", "wm", "size"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and ":" in result.stdout:
            resolution = result.stdout.split(":")[-1].strip()
            if resolution:
                specs["screen_resolution"] = resolution
        
        # 获取电池电量
        result = subprocess.run(
            ["adb", "shell", "dumpsys", "battery"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'level:' in line:
                    try:
                        specs["battery"] = int(line.split(':')[1].strip())
                    except:
                        pass
                    break
    
    except Exception as e:
        logger.warning(f"⚠️  获取设备规格失败: {e}")
    
    return specs


async def ws_client(ws_url, frp_port, device_name):
    """
    WebSocket客户端主循环
    
    Args:
        ws_url: WebSocket服务器地址
        frp_port: FRP端口（唯一标识）
        device_name: 设备名称（用户自定义）
    """
    while True:
        try:
            logger.info(f"🔗 连接到 {ws_url}...")
            
            async with websockets.connect(
                ws_url,
                ping_interval=30,
                ping_timeout=10
            ) as websocket:
                logger.info("✅ WebSocket已连接")
                
                # 发送设备上线消息（包含 frp_port 用于唯一标识）
                specs = await get_device_specs()
                specs["frp_port"] = int(frp_port)  # 关键：用于服务端匹配
                specs["device_name"] = device_name
                specs["device_id"] = f"device_{frp_port}"  # 统一格式
                
                online_msg = {
                    "type": "device_online",
                    "specs": specs
                }
                await websocket.send(json.dumps(online_msg))
                logger.info(f"📤 已发送设备上线消息: {specs['model']} (Android {specs['android_version']}) [FRP端口: {frp_port}]")
                
                # 等待服务器确认
                confirm_msg = await websocket.recv()
                confirm_data = json.loads(confirm_msg)
                if confirm_data.get("type") == "registered":
                    logger.info("✅ 设备已在服务器注册成功")
                
                # 持续接收消息
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        msg_type = data.get("type")
                        
                        if msg_type == "task":
                            # 处理任务
                            await handle_task(websocket, data)
                        else:
                            logger.info(f"📬 收到消息: {msg_type}")
                    
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ JSON解析失败: {e}")
                    except Exception as e:
                        logger.error(f"❌ 消息处理失败: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️  连接关闭，10秒后重连...")
            await asyncio.sleep(10)
        
        except Exception as e:
            logger.error(f"❌ 连接失败: {e}，10秒后重试...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python ws_client_simple.py <ws_url> <frp_port> <device_name>")
        sys.exit(1)
    
    ws_url = sys.argv[1]
    frp_port = sys.argv[2]
    device_name = sys.argv[3]
    
    logger.info(f"🚀 启动 WebSocket 客户端")
    logger.info(f"   FRP端口: {frp_port}")
    logger.info(f"   设备名称: {device_name}")
    logger.info(f"   服务器: {ws_url}")
    
    asyncio.run(ws_client(ws_url, frp_port, device_name))
PYTHON_EOF
    
    chmod +x ws_client_simple.py
    
    log_info "✅ WebSocket 客户端创建完成"
}

#############################################################################
# 步骤 6: 创建启动脚本
#############################################################################

create_start_script() {
    log_step "🚀 步骤 6/6: 创建启动脚本"
    
    cd ~ || exit 1
    
    # 创建启动脚本
    cat > start_all.sh << EOF
#!/data/data/com.termux/files/usr/bin/bash
#############################################################################
# PhoneAgent 客户端启动脚本
# 
# 功能：
# 1. 启动 ADB 服务（设备控制）
# 2. 启动 FRP 客户端（端口转发和设备发现）
# 3. 启动 WebSocket 客户端（任务下发和结果上报）
#############################################################################

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "\${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\${NC}"
echo -e "\${BLUE}🚀 启动 PhoneAgent 客户端\${NC}"
echo -e "\${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\${NC}"
echo ""
echo -e "\${YELLOW}📝 设备信息:\${NC}"
echo -e "  设备名称: \${GREEN}${DEVICE_NAME}\${NC}"
echo -e "  FRP端口:  \${GREEN}${REMOTE_PORT}\${NC}"
echo -e "  设备ID:   \${GREEN}device_${REMOTE_PORT}\${NC}"
echo ""

# 确保 scrcpy-server 存在（/data/local/tmp 可能会被清理）
SCRCPY_TARGET="/data/local/tmp/scrcpy-server"
SCRCPY_CACHE="$HOME/scrcpy-server"
if [ ! -f "\$SCRCPY_TARGET" ] && [ -f "\$SCRCPY_CACHE" ]; then
    echo -e "\${YELLOW}🛠️  检测到 scrcpy-server 缺失，正在恢复...\${NC}"
    mkdir -p /data/local/tmp 2>/dev/null || true
    if cp "\$SCRCPY_CACHE" "\$SCRCPY_TARGET" 2>/dev/null && chmod 755 "\$SCRCPY_TARGET" 2>/dev/null; then
        echo -e "   \${GREEN}✅ scrcpy-server 已恢复到 /data/local/tmp/scrcpy-server\${NC}"
    else
        echo -e "   \${YELLOW}⚠️  scrcpy-server 自动恢复失败，请手动复制到 /data/local/tmp/scrcpy-server\${NC}"
    fi
fi

# 1. 启动 ADB
echo "1️⃣  启动 ADB 服务..."
adb kill-server 2>/dev/null || true

# 禁用模拟器自动连接
export ADB_MDNS_AUTO_CONNECT=0
export ADB_LIBUSB=0

adb start-server
sleep 2

# 连接到系统 adbd
echo "   连接到系统 ADB Daemon (5555)..."
adb connect localhost:5555 >/dev/null 2>&1
sleep 1

# 断开模拟器（如果存在）
adb disconnect emulator-5554 >/dev/null 2>&1 || true
adb disconnect emulator-5555 >/dev/null 2>&1 || true

# 再次确认只有 localhost:5555
sleep 1

# 验证连接
if adb -s localhost:5555 shell echo "test" 2>/dev/null | grep -q "test"; then
    echo -e "   \${GREEN}✅ ADB 连接成功\${NC}"
    
    # 获取设备信息
    MODEL=\$(adb -s localhost:5555 shell getprop ro.product.model 2>/dev/null | tr -d '\r')
    echo -e "   \${GREEN}📱 设备: \${MODEL}\${NC}"
else
    echo -e "   \${RED}❌ ADB 连接失败\${NC}"
    echo -e "   \${YELLOW}⚠️  需要先执行: adb tcpip 5555\${NC}"
fi

# 2. 启动 FRP
echo ""
echo "2️⃣  启动 FRP 客户端 (端口: ${REMOTE_PORT})..."
cd ~/frp || exit 1

# 停止旧的 FRP 进程
pkill -f frpc || true
sleep 1

# 启动 FRP
nohup ./frpc -c frpc.ini > frpc.log 2>&1 &
FRP_PID=\$!

sleep 2

# Termux/Android 兼容的进程检查（不使用 ps -p）
if pgrep -f frpc > /dev/null 2>&1; then
    echo -e "   \${GREEN}✅ FRP 启动成功 (PID: \$FRP_PID)\${NC}"
    echo -e "   \${BLUE}   服务端可通过 localhost:${REMOTE_PORT} 访问此设备\${NC}"
else
    echo -e "   \${YELLOW}⚠️  FRP 进程检测失败（可能正在启动）\${NC}"
    echo -e "   \${YELLOW}   查看日志确认状态:\${NC}"
    tail -5 frpc.log
    echo -e "   \${YELLOW}   继续执行后续步骤...\${NC}"
    # 不退出，继续启动 WebSocket
fi

# 3. 启动 WebSocket 客户端
echo ""
echo "3️⃣  启动 WebSocket 客户端..."
cd ~ || exit 1

# 停止旧的 WebSocket 进程
pkill -f ws_client_simple.py || true
sleep 1

# 启动 WebSocket（传递 frp_port 和 device_name）
source ~/phoneagent_venv/bin/activate
nohup python ~/ws_client_simple.py "${WS_URL}" "${REMOTE_PORT}" "${DEVICE_NAME}" > ~/ws_client_simple.log 2>&1 &
WS_PID=\$!
deactivate

sleep 3

# Termux/Android 兼容的进程检查（不使用 ps -p）
if pgrep -f ws_client_simple.py > /dev/null 2>&1; then
    echo -e "   \${GREEN}✅ WebSocket 启动成功 (PID: \$WS_PID)\${NC}"
else
    echo -e "   \${RED}❌ WebSocket 启动失败，查看日志:\${NC}"
    tail -20 ~/ws_client_simple.log
fi

echo ""
echo -e "\${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\${NC}"
echo -e "\${GREEN}✅ PhoneAgent 客户端启动完成！\${NC}"
echo -e "\${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\${NC}"
echo ""
echo -e "\${YELLOW}📊 服务状态:\${NC}"
echo -e "  - ADB:       \$(pgrep -f adb > /dev/null && echo '\${GREEN}✅ 运行中\${NC}' || echo '\${RED}❌ 未运行\${NC}')"
echo -e "  - FRP:       \$(pgrep -f frpc > /dev/null && echo '\${GREEN}✅ 运行中\${NC}' || echo '\${RED}❌ 未运行\${NC}')"
echo -e "  - WebSocket: \$(pgrep -f ws_client_simple.py > /dev/null && echo '\${GREEN}✅ 运行中\${NC}' || echo '\${RED}❌ 未运行\${NC}')"
echo ""
echo -e "\${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\${NC}"
echo -e "\${YELLOW}🌐 前端连接信息（重要！）\${NC}"
echo -e "\${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\${NC}"
echo ""
echo -e "  \${BLUE}前端地址:\${NC}  http://${SERVER_IP}:9999"
echo -e "  \${GREEN}设备ID:\${NC}    device_${REMOTE_PORT}"
echo -e "  \${GREEN}设备名称:\${NC}  ${DEVICE_NAME}"
echo -e "  \${GREEN}FRP端口:\${NC}   ${REMOTE_PORT}"
echo ""
echo -e "\${RED}⚠️  注意:\${NC}"
echo -e "  1. 在前端设备列表中查找 \${GREEN}device_${REMOTE_PORT}\${NC} 或 \${GREEN}${DEVICE_NAME}\${NC}"
echo -e "  2. 如果看不到新设备，请点击刷新按钮"
echo -e "  3. 确认设备显示为 \${GREEN}在线\${NC} 状态后即可使用"
echo -e "  4. 多台设备会有不同的端口号，请注意区分"
echo ""
echo -e "\${YELLOW}📋 查看日志:\${NC}"
echo -e "  tail -f ~/frp/frpc.log         # FRP日志"
echo -e "  tail -f ~/ws_client_simple.log # WebSocket日志"
echo ""
echo "💡 工作原理:"
echo "  - 设备发现: 服务端扫描FRP端口（每10秒）"
echo "  - 任务执行: 服务端通过FRP隧道执行ADB命令"
echo "  - WebSocket: 设备注册和状态管理"
echo "  - 防风控: 内置时间/坐标随机化"
echo ""
echo "📋 查看日志:"
echo "  tail -f ~/frp/frpc.log         # FRP日志"
echo "  tail -f ~/ws_client_simple.log # WebSocket日志"
echo ""
EOF
    
    chmod +x start_all.sh
    
    # 创建停止脚本
    cat > stop_all.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
echo "🛑 停止 PhoneAgent 客户端..."

pkill -f frpc
pkill -f ws_client_simple.py
pkill -f adb

echo "✅ 已停止所有服务"
EOF
    
    chmod +x stop_all.sh
    
    # 创建状态检查脚本
    cat > check_status.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
echo "📊 PhoneAgent 客户端状态检查"
echo ""

# ADB 状态
if pgrep -f adb > /dev/null; then
    echo "✅ ADB: 运行中"
    adb devices | tail -n +2
else
    echo "❌ ADB: 未运行"
fi

echo ""

# FRP 状态
if pgrep -f frpc > /dev/null; then
    echo "✅ FRP: 运行中"
    FRP_PID=$(pgrep -f frpc)
    echo "   PID: $FRP_PID"
    echo "   最后10行日志:"
    tail -10 ~/frp/frpc.log | sed 's/^/   /'
else
    echo "❌ FRP: 未运行"
fi

echo ""

# WebSocket 状态
if pgrep -f ws_client_simple.py > /dev/null; then
    echo "✅ WebSocket: 运行中"
    WS_PID=$(pgrep -f ws_client_simple.py)
    echo "   PID: $WS_PID"
    echo "   最后10行日志:"
    tail -10 ~/ws_client_simple.log | sed 's/^/   /'
else
    echo "❌ WebSocket: 未运行"
fi

echo ""
EOF
    
    chmod +x check_status.sh
    
    log_info "✅ 启动脚本创建完成"
}

#############################################################################
# 显示完成信息
#############################################################################

show_completion() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ PhoneAgent 客户端安装完成!                            ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📝 设备配置信息（重要！请记录）${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BLUE}服务器IP:${NC}   $SERVER_IP"
    echo -e "  ${BLUE}设备名称:${NC}   $DEVICE_NAME"
    echo -e "  ${GREEN}FRP端口:${NC}    ${GREEN}${REMOTE_PORT}${NC}  ${RED}⭐ 重要！前端连接需要此端口${NC}"
    echo -e "  ${BLUE}连接模式:${NC}   $([ "$WS_MODE" = "2" ] && echo "域名代理" || echo "直连IP")"
    echo ""
    echo -e "${RED}⚠️  注意事项：${NC}"
    echo -e "  1. 此设备的唯一标识是 FRP端口: ${GREEN}${REMOTE_PORT}${NC}"
    echo -e "  2. 前端界面需要选择 ${GREEN}device_${REMOTE_PORT}${NC} 来连接此设备"
    echo -e "  3. 如果前端显示旧设备，请刷新设备列表或检查端口号"
    echo -e "  4. 多台设备部署时，每台设备会自动分配不同端口"
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    echo -e "${YELLOW}🚀 启动服务:${NC}"
    echo "  bash ~/start_all.sh"
    echo ""
    
    echo -e "${YELLOW}🛑 停止服务:${NC}"
    echo "  bash ~/stop_all.sh"
    echo ""
    
    echo -e "${YELLOW}📊 查看状态:${NC}"
    echo "  bash ~/check_status.sh"
    echo ""
    
    echo -e "${YELLOW}📋 查看日志:${NC}"
    echo "  tail -f ~/frp/frpc.log         # FRP日志"
    echo "  tail -f ~/ws_client_simple.log # WebSocket日志"
    echo ""
    
    echo -e "${YELLOW}💡 架构说明:${NC}"
    echo "  - FRP: 端口转发 + 任务执行主通道（ADB over TCP）"
    echo "  - WebSocket: 设备注册 + 状态管理 + 在线检测"
    echo ""
    
    echo -e "${GREEN}🌐 前端访问提示:${NC}"
    echo "  1. 打开前端界面: http://${SERVER_IP}:9999"
    echo "  2. 在设备列表中找到: ${GREEN}device_${REMOTE_PORT}${NC} 或 ${GREEN}${DEVICE_NAME}${NC}"
    echo "  3. 如果看不到新设备，点击刷新按钮"
    echo "  4. 确认设备在线后即可执行任务"
    echo "  - ADB: 设备控制接口（截图、点击、滑动、输入）"
    echo "  - 防风控: 时间/坐标随机化，模拟人类操作"
    echo ""
    
    read -p "现在启动服务吗? (y/n, 默认: y): " START_NOW
    START_NOW=${START_NOW:-y}
    if [ "$START_NOW" = "y" ]; then
        bash ~/start_all.sh
    else
        log_info "稍后可运行 'bash ~/start_all.sh' 启动服务"
    fi
}

#############################################################################
# 主流程
#############################################################################

main() {
    clear
    
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  PhoneAgent Termux 客户端安装脚本                         ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    get_config
    install_dependencies
    setup_frp
    setup_adb
    setup_scrcpy_server  # 新增：安装 scrcpy-server
    create_ws_client
    create_start_script
    show_completion
}

# 执行主流程
main
