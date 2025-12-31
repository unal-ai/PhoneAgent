# PhoneAgent 部署指南

> **🎯 目标：10分钟完成简单模式，30分钟完成完整模式**

---

## ⚠️ 重要提示

**首次部署必须执行 ADB TCP 配置**，否则设备会显示为 `offline` 无法使用！详细步骤请查看简单模式中的步骤2。

---

## 📋 快速导航

| 我要... | 跳转到 |
|--------|--------|
| 了解需要什么 | [→ 系统要求](#系统要求) |
| 快速体验 | [→ 简单模式](#简单模式10分钟) |
| 完整部署 | [→ 完整模式](#完整模式30分钟) |
| 解决问题 | [→ 故障排查](#故障排查) |

---

## 🎯 部署模式对比

| 模式 | 时间 | 难度 | 语音输入 | Scrcpy 视频流 | 适用场景 |
|-----|------|------|---------|-------------|---------|
| **简单模式** | 10分钟 | ⭐ | ❌ | ✅ | 快速体验、学习测试 |
| **完整模式** | 30分钟 | ⭐⭐⭐ | ✅ | ✅ | 生产使用、日常使用 |

**为什么简单模式不支持语音输入？**
- 浏览器 `getUserMedia` API 要求 HTTPS 或 localhost
- 简单模式使用 `http://服务器IP:5173` 访问，不满足要求
- 完整模式通过域名 + SSL 证书解决此问题

---

## 🖥️ 系统要求

### 服务器（必需公网IP）

| 项目 | 最低 | 推荐 |
|-----|------|------|
| **系统** | Ubuntu 20.04+ | Ubuntu 22.04 LTS |
| **配置** | 1核2GB | 2核4GB |
| **网络** | 公网 IP（必需） | 固定 IP |
| **端口** | 见下表 | 需防火墙开放 |

**需要开放的端口**：

| 端口 | 服务 | 用途 |
|-----|------|------|
| **7000** | FRP 服务器 | 设备端口转发和发现 |
| **8000** | API 服务器 | REST API + 前端 WS + Scrcpy WS |
| **9999** | 设备 WebSocket | 设备连接和任务下发 |
| **6100-6199** | FRP 客户端端口 | 每台设备占用1个（支持100台） |
| **5173** | 前端开发服务器 | 简单模式需要 |
| **80/443** | HTTP/HTTPS | 完整模式需要 |

**配置防火墙**：
```bash
sudo ufw allow 7000/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 9999/tcp
sudo ufw allow 6100:6199/tcp  # 支持最多100台设备
sudo ufw allow 5173/tcp        # 简单模式
sudo ufw allow 80/tcp          # 完整模式
sudo ufw allow 443/tcp         # 完整模式
sudo ufw enable
```

### Android 设备

- Android 7.0+，USB 调试已开启
- 已安装 Termux（从 [F-Droid](https://f-droid.org/packages/com.termux/) 下载）

---

## 🚀 简单模式（10分钟）

### 步骤1：服务端（5分钟）

```bash
# SSH 连接服务器
ssh root@YOUR_SERVER_IP

# 克隆项目
git clone https://github.com/unal-ai/PhoneAgent.git
cd PhoneAgent

# 配置 API Key
cp env.example .env
nano .env  # 填写 ZHIPU_API_KEY

# 一键安装
sudo bash scripts/install/install_server.sh
```

**安装过程会提示输入**：
- `FRP Token`：用于客户端认证，请设置一个强密码（如 `my_secure_token_123`）
- 是否创建 systemd 服务：建议选择 `y`

**⚠️ 重要**：请记住您输入的 `FRP Token`，客户端部署时需要使用相同的 Token

**验证**：
```bash
curl http://localhost:8000/health  # 应返回 {"status": "ok"}
```

### 步骤2：客户端（3分钟）

在 Android 手机的 Termux 中运行：

```bash
# 使用官方源（需要VPN）
bash <(curl -s https://raw.githubusercontent.com/unal-ai/PhoneAgent/main/client/install_termux.sh)

# 使用国内CDN（推荐）
bash <(curl -s https://cdn.jsdelivr.net/gh/unal-ai/PhoneAgent@main/client/install_termux.sh)

# 使用国内镜像
bash <(curl -s https://mirror.ghproxy.com/https://raw.githubusercontent.com/unal-ai/PhoneAgent/main/client/install_termux.sh)
```

**安装过程会提示输入**（4 个必填参数）：

1. **后端服务器 IP**
   - 填写后端服务器的公网 IP
   - 示例：`1.2.3.4`

2. **FRP Token**
   - ⚠️ **必须与服务端输入的 Token 完全一致**
   - 示例：`my_secure_token_123`

3. **WebSocket 连接方式**
   - `1` = 直连IP（推荐：前后端同服务器）
   - `2` = 域名代理（推荐：需要HTTPS或语音功能）

4. **前端访问地址**
   - 选择 `1=直连IP`：输入前端服务器IP（通常与后端相同）
   - 选择 `2=域名代理`：输入域名（如 `phoneagent.example.com`）

**其他参数（可选，自动配置）**：

4. **设备名称**
   - 脚本会自动生成（如 `Redmi_K50_1234`）
   - 也可手动输入自定义名称

5. **FRP 端口分配**
   - 推荐选择 `1=自动分配`（智能检测可用端口）
   - 也可选择 `2=手动指定`（6100-6199 范围）

**⚠️ FRP Token 认证说明**：
- 服务端和客户端使用 FRP Token 进行双向认证
- Token 不匹配会导致客户端连接失败
- Token 存储在 `~/frp/frpc.ini`（客户端）和 `frp/frps.ini`（服务端）

**验证**：
```bash
bash ~/check_status.sh  # 查看服务状态
```

**预期输出**：
```
✅ ADB: 运行中
✅ FRP: 运行中
✅ WebSocket: 运行中
```

---

### ⚠️ 关键步骤：ADB TCP 连接配置（必须执行）

**问题**：此时虽然服务已启动，但**设备在服务端会显示为 `offline` 状态**，无法正常使用。

**原因**：Android 系统的 ADB 守护进程（`adbd`）默认不监听 TCP 端口，需要手动开启。

#### 方法1：通过USB连接电脑（推荐 ⭐）

**步骤**：
1. 用 USB 数据线连接手机到电脑
2. 在电脑上执行：
   ```bash
   adb tcpip 5555
   ```
3. 拔掉 USB 线，手机通过 FRP 隧道连接

**优点**：简单可靠，适合首次配置

#### 方法2：使用无线调试（Android 11+）

**步骤**：
1. 打开手机设置 → 开发者选项 → 无线调试
2. 点击"使用配对码配对设备"，记下 IP 和端口
3. 在 Termux 中执行：
   ```bash
   adb pair <IP>:<端口>  # 输入配对码
   adb connect localhost:5555
   ```

**优点**：无需电脑，但需要 Android 11+


#### 验证连接

在服务端执行：
```bash
adb devices -l
```

**正常输出**（应显示 `device` 而非 `offline`）：
```
List of devices attached
localhost:6100    device product:mars model:M2102K1AC device:mars transport_id:1
```

如果显示 `offline`，请检查：
1. 是否执行了 `adb tcpip 5555`
2. FRP 隧道是否正常（检查 `~/frp/frpc.log`）
3. 手机是否重启过（重启后需重新执行 `adb tcpip 5555`）

---

### 步骤3：前端（2分钟）

在服务器上：

```bash
cd ~/PhoneAgent/web
npm install
npm run dev -- --host 0.0.0.0
```

**访问**：`http://YOUR_SERVER_IP:5173`

**完成！** ✅

---

## 🌐 完整模式（30分钟）

> 完整模式通过域名 + SSL + Nginx 反向代理，支持语音输入和完整功能

### 架构说明

```
┌─────────────────────────────────────────────────────────────┐
│                 用户浏览器（前端）                             │
│             https://your-domain.com                          │
└────────────┬────────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────────┐
│              Nginx 反向代理（前端服务器）                      │
│                                                              │
│  /               → 前端静态文件 (Vue SPA)                    │
│  /api/           → http://127.0.0.1:8000/api/               │
│  /api/v1/ws      → http://127.0.0.1:8000/api/v1/ws    ← 前端WS │
│  /device-ws/     → http://127.0.0.1:9999/ws/          ← 设备WS │
│  /api/v1/scrcpy/stream/* → http://127.0.0.1:8000/... ← Scrcpy WS │
└────────────┬────────────────────────────────────────────────┘
             │
             ├──────────────────┬──────────────────┐
             ↓                  ↓                  ↓
    ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐
    │  API服务器      │  │ WebSocket服务器 │  │  FRP服务器       │
    │  (8000端口)     │  │  (9999端口)     │  │  (7000端口)      │
    └────────────────┘  └─────────────────┘  └──────────────────┘
```

### 前置准备

#### 1. 域名准备（5分钟）

**免费域名**：
- [Freenom](https://www.freenom.com) - .tk, .ml, .ga, .cf, .gq
- [Duck DNS](https://www.duckdns.org) - 免费子域名

**DNS 配置**（以 Cloudflare 为例）：
1. 注册 Cloudflare，添加域名
2. 添加 A 记录：`@ → YOUR_SERVER_IP`
3. 等待 DNS 生效（5-30分钟）

#### 2. 安装 1Panel（5分钟）

```bash
# 一键安装
curl -sSL https://resource.fit2cloud.com/1panel/package/quick_start.sh -o quick_start.sh && bash quick_start.sh

# 访问面板
https://YOUR_SERVER_IP:端口  # 安装完成后会显示
```

### 步骤1：服务端部署

```bash
git clone https://github.com/unal-ai/PhoneAgent.git
cd PhoneAgent
cp env.example .env
nano .env  # 填写 ZHIPU_API_KEY
sudo bash scripts/install/install_server.sh
```

**安装时需要手动设置 FRP Token**，请记住您输入的 Token，客户端部署时需要使用相同的 Token。

### 步骤2：客户端部署

```bash
# 使用官方源（需要VPN）
bash <(curl -s https://raw.githubusercontent.com/unal-ai/PhoneAgent/main/client/install_termux.sh)

# 使用国内CDN（推荐）
bash <(curl -s https://cdn.jsdelivr.net/gh/unal-ai/PhoneAgent@main/client/install_termux.sh)

# 使用国内镜像
bash <(curl -s https://mirror.ghproxy.com/https://raw.githubusercontent.com/unal-ai/PhoneAgent/main/client/install_termux.sh)
```

**必填参数**：
- 服务器 IP
- FRP Token（与服务端输入的一致）

**选择连接方式**：建议选择 `2=域名代理`（支持 HTTPS + 语音功能）

**⚠️ 客户端部署完成后，务必执行 ADB TCP 连接配置**（参见简单模式步骤2）

### 步骤3：前端部署（15分钟）

#### 3.1 构建前端

```bash
cd ~/PhoneAgent/web

# 创建生产环境配置（留空，使用相对路径）
cat > .env.production << EOF
VITE_API_BASE_URL=
VITE_WS_URL=
EOF

npm install
npm run build
```

**重要**：环境变量留空的原因是 Nginx 会反向代理，前端使用相对路径访问。

#### 3.2 在 1Panel 中配置

**创建网站**：
- 域名：`your-domain.com`
- 网站目录：`/root/PhoneAgent/web/dist`
- 运行时：静态网站

**配置反向代理**（网站配置 → 反向代理）：

```nginx
# ============================================
# 前端 WebSocket（8000端口）
# ⚠️ 重要：必须在 /api/ 之前！
# ============================================
location = /api/v1/ws {
    proxy_pass http://127.0.0.1:8000/api/v1/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 86400s;  # 24小时
    proxy_send_timeout 86400s;
    proxy_buffering off;
}

# ============================================
# Scrcpy 视频流 WebSocket（8000端口）
# ⚠️ 重要：必须在 /api/ 之前！
# ============================================
location ~ ^/api/v1/scrcpy/stream/(.+)$ {
    proxy_pass http://127.0.0.1:8000/api/v1/scrcpy/stream/$1;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 3600s;   # 1小时
    proxy_send_timeout 3600s;
    proxy_buffering off;
}

# ============================================
# API 代理（8000端口）
# ============================================
location /api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 60s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
}

# ============================================
# 设备 WebSocket（9999端口）
# ============================================
location /device-ws/ {
    proxy_pass http://127.0.0.1:9999/ws/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 86400s;  # 24小时
    proxy_send_timeout 86400s;
    proxy_buffering off;
}
```

**配置顺序很重要**！WebSocket 配置必须在 `/api/` 之前，否则会被 `/api/` 规则拦截。

**配置 SSL**（网站配置 → SSL）：
- 选择 "Let's Encrypt"
- 点击 "申请"（自动完成）

**配置 SPA 路由**（网站配置 → 配置文件）：

```nginx
location / {
    root /root/PhoneAgent/web/dist;
    try_files $uri $uri/ /index.html;
    index index.html;
}
```

#### 3.3 更新客户端配置（可选）

**注意**：客户端安装时已经配置好 WebSocket 连接，通常无需修改。

如果需要从直连IP模式切换到域名代理模式：

```bash
# 在 Termux 中
nano ~/start_all.sh

# 找到 WS_URL 行，修改为域名模式：
# 原来：WS_URL="ws://SERVER_IP:9999/ws/device/6100"
# 修改为（注意端口号要与你的 FRP 端口一致）：
WS_URL="wss://your-domain.com/device-ws/device/6100"

# 重启
bash ~/stop_all.sh && bash ~/start_all.sh
```

**重要提示**：
- `/ws/device/` 后面的数字是 **FRP 端口**（如 6100, 6101 等），不是设备名称
- 端口号必须与 `~/frp/frpc.ini` 中的 `remote_port` 一致
- 每台设备使用不同的端口：第一台用 6100，第二台用 6101，依次递增

**访问**：`https://your-domain.com`

**完成！** ✅

---

## ✅ 验证测试

### 1. 检查服务

```bash
# 服务端
bash scripts/server/status.sh

# 客户端（Termux）
bash ~/check_status.sh
```

### 2. 测试 API

```bash
# 健康检查
curl http://localhost:8000/health

# 查看设备列表
curl http://localhost:8000/api/v1/devices/scanned
```

### 3. 测试 WebSocket

**使用 wscat**：
```bash
npm install -g wscat

# 前端 WebSocket
wscat -c ws://localhost:8000/api/v1/ws

# 设备 WebSocket
wscat -c ws://localhost:9999/ws/device/6100

# Scrcpy WebSocket
wscat -c ws://localhost:8000/api/v1/scrcpy/stream/device_6100
```

### 4. 测试功能

1. 浏览器访问前端
2. 点击"设备管理"，查看在线设备
3. 创建任务："打开设置"
4. 观察执行结果
5. 测试实时预览（Scrcpy）

### 5. 测试语音（完整模式）

1. 点击"语音输入"
2. 允许麦克风权限
3. 说话测试

---

## 🔧 故障排查

### 服务启动失败

```bash
# 查看日志
tail -50 logs/api.log
tail -50 logs/websocket.log

# 检查端口占用
netstat -tlnp | grep -E '7000|8000|9999|6100'

# 检查进程
ps aux | grep -E 'uvicorn|frps'
```

### 客户端连接失败

```bash
# 在 Termux 中测试网络
ping YOUR_SERVER_IP

# 检查 FRP 配置
cat ~/frp/frpc.ini | grep -E 'server_addr|server_port|token'

# 查看 FRP 日志
tail -50 ~/frp/frpc.log

# 查看 WebSocket 日志
tail -50 ~/ws_client_simple.log
```

### 前端无法访问

**简单模式**：
- 检查防火墙是否开放 5173 端口
- 检查前端服务是否运行：`ps aux | grep vite`

**完整模式**：
- 检查域名 DNS 是否生效：`ping your-domain.com`
- 检查 SSL 证书是否正确：`curl -I https://your-domain.com`
- 检查 Nginx 配置：`sudo nginx -t`
- 查看 Nginx 日志：`sudo tail -f /var/log/nginx/error.log`

### WebSocket 连接失败

**症状**：浏览器控制台显示 `WebSocket connection failed`

**排查步骤**：
1. 打开浏览器 F12 → Network → WS，查看实际连接的 URL
2. 确认 WebSocket URL 是否正确：
   - 前端 WS 应该是 `wss://your-domain.com/api/v1/ws`
   - 设备 WS 应该是 `wss://your-domain.com/device-ws/device/xxx`
3. 检查 Nginx 配置中的 WebSocket 代理是否正确
4. 检查后端服务是否正常运行
5. 查看后端日志：`tail -f logs/websocket.log`

### Scrcpy 视频流无法显示

**症状**：点击"实时预览"后黑屏或连接失败

**排查步骤**：
1. 检查是否配置了 Scrcpy WebSocket 反向代理
2. 确认浏览器 F12 → Network → WS 中看到 `/api/v1/scrcpy/stream/{device_id}` 连接
3. 检查防火墙是否开放了 6100-6199 端口
4. 在 Termux 中测试 Scrcpy：`scrcpy -s 127.0.0.1:6100`
5. 查看 API 日志：`tail -f logs/api.log | grep scrcpy`

### 语音输入不工作

**症状**：点击麦克风图标无反应或报错

**原因**：
- ⚠️ 浏览器 `getUserMedia` API 要求 HTTPS 或 localhost
- ⚠️ 简单模式（HTTP + IP）不支持语音输入

**解决**：
- 使用完整模式（HTTPS + 域名）
- 或在本地浏览器访问 `http://localhost:5173`

---

## 📚 常用命令

### 服务端

```bash
bash scripts/server/start.sh    # 启动
bash scripts/server/stop.sh     # 停止
bash scripts/server/status.sh   # 状态
tail -f logs/api.log            # API 日志
tail -f logs/websocket.log      # WebSocket 日志
tail -f logs/frps.log           # FRP 日志
```

### 客户端

```bash
bash ~/start_all.sh             # 启动
bash ~/stop_all.sh              # 停止
bash ~/check_status.sh          # 状态
tail -f ~/ws_client_simple.log  # WebSocket 日志
tail -f ~/frp/frpc.log          # FRP 日志
```

### Nginx

```bash
sudo nginx -t                   # 测试配置
sudo nginx -s reload            # 重载配置
sudo tail -f /var/log/nginx/error.log   # 错误日志
sudo tail -f /var/log/nginx/access.log  # 访问日志
```

---

## 💡 最佳实践

### 推荐配置

- **新手/测试**：简单模式
- **个人使用**：完整模式 + Cloudflare + 1Panel
- **企业使用**：完整模式 + 付费域名 + CDN

### 安全建议

- 使用强 FRP Token（16位以上随机字符）
- 定期备份 `data/` 目录
- 监控日志和错误
- 限制 FRP 端口范围，根据设备数量调整

### 性能优化

- 多设备时合理分配 FRP 端口（6100-6199）
- 使用 CDN 加速前端访问
- 定期清理日志文件
- Scrcpy 视频流根据网络调整码率

### 架构理解

PhoneAgent 使用**双 WebSocket 服务**架构，理解这一点很重要：

1. **API 服务器（8000 端口）**：
   - 提供 REST API
   - 提供前端 WebSocket（`/api/v1/ws`）用于实时状态推送
   - 提供 Scrcpy WebSocket（`/api/v1/scrcpy/stream/{device_id}`）用于视频流传输

2. **设备 WebSocket 服务器（9999 端口）**：
   - 提供设备 WebSocket（`/ws/device/{frp_port}`）用于设备连接和任务下发

3. **Nginx 反向代理**：
   - 将 `/api/` 代理到 8000 端口
   - 将 `/api/v1/ws` 代理到 8000 端口（前端 WS）
   - 将 `/api/v1/scrcpy/stream/*` 代理到 8000 端口（Scrcpy WS）
   - 将 `/device-ws/` 代理到 9999 端口（设备 WS）

---

## ⚙️ 高级配置

### 多模型平台配置

默认使用智谱AI，也支持 OpenAI、Google Gemini、通义千问等平台。

#### 切换到 OpenAI

```bash
# 编辑 .env
nano .env

# 添加配置
MODEL_PROVIDER=openai
CUSTOM_API_KEY=sk-proj-xxxxx
CUSTOM_MODEL_NAME=gpt-4o

# 重启服务
bash scripts/server/restart.sh
```

#### 切换到 Google Gemini

```bash
# 编辑 .env
nano .env

# 添加配置
MODEL_PROVIDER=gemini
CUSTOM_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX
CUSTOM_MODEL_NAME=gemini-2.0-flash

# 重启服务
bash scripts/server/restart.sh
```

#### 切换到通义千问（国内推荐）

```bash
# 编辑 .env
nano .env

# 添加配置
MODEL_PROVIDER=qwen
CUSTOM_API_KEY=sk-xxxxx
CUSTOM_MODEL_NAME=qwen-vl-plus

# 重启服务
bash scripts/server/restart.sh
```

#### 支持的环境变量

```bash
# 模型提供商（zhipu, openai, gemini, qwen）
MODEL_PROVIDER=zhipu

# 自定义 API Key
CUSTOM_API_KEY=your_api_key

# 自定义模型名称
CUSTOM_MODEL_NAME=gpt-4o

# 自定义 base_url（高级，一般不需要修改）
CUSTOM_BASE_URL=https://api.openai.com/v1

# 分别配置不同内核（高级）
XML_KERNEL_MODEL=gpt-4-turbo       # XML内核专用
VISION_KERNEL_MODEL=gpt-4o         # Vision内核专用
PLANNING_KERNEL_MODEL=gpt-4o       # 规划模式专用

# 任务执行配置
MAX_TASK_STEPS=100                 # 最大执行步数（1-200）
MAX_TOKENS=3000                    # 模型输出Token限制
TEMPERATURE=0.7                    # 模型温度（0-1，越高越随机）
```

### 配置说明

**MODEL_PROVIDER** - 模型提供商，支持以下选项：
- `zhipu`（默认）- 智谱AI，国内访问快，免费额度
- `openai` - OpenAI GPT系列
- `gemini` - Google Gemini系列
- `qwen` - 阿里通义千问系列

**配置优先级**:
1. `CUSTOM_MODEL_NAME` - 所有内核使用同一模型（最高优先级）
2. `XML_KERNEL_MODEL` 等 - 分别为不同内核指定模型
3. `MODEL_PROVIDER` - 根据提供商自动选择默认模型
4. 智谱AI默认策略（fallback）

---

**需要帮助？** 提交 [Issue](https://github.com/unal-ai/PhoneAgent/issues)
