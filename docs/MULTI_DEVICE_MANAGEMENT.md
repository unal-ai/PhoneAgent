# 多设备集中管理指南

> 本指南介绍如何在局域网环境中集中管理多台 Android 设备，支持单服务器或多服务器集群部署。

## 功能概述

PhoneAgent 内置多设备管理能力：

| 功能 | 说明 | 支持设备数 |
|------|------|-----------|
| **设备池管理** | 自动发现、注册、健康检查 | 100+ |
| **负载均衡** | 智能分配任务到空闲设备 | 支持 |
| **实时监控** | WebSocket 双通道连接状态 | 支持 |
| **统一控制台** | Web UI 集中管理所有设备 | 支持 |

---

## 单服务器架构（推荐入门）

适用于：**10-100 台设备**

```
                    ┌─────────────────────────────────────────┐
                    │           PhoneAgent Server             │
                    │         (192.168.1.100:8000)            │
                    ├─────────────────────────────────────────┤
                    │  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
                    │  │ API     │  │ FRP     │  │ WS      │  │
                    │  │ :8000   │  │ :7000   │  │ :9999   │  │
                    │  └────┬────┘  └────┬────┘  └────┬────┘  │
                    │       │            │            │       │
                    │  ┌────┴────────────┴────────────┴────┐  │
                    │  │         DevicePool (100台)         │  │
                    │  │    负载均衡 | 健康检查 | 任务分配   │  │
                    │  └──────────────────────────────────┘  │
                    └─────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
              │  Device 1 │   │  Device 2 │   │  Device N │
              │  :6100    │   │  :6101    │   │  :61XX    │
              │  (FRP)    │   │  (FRP)    │   │  (FRP)    │
              └───────────┘   └───────────┘   └───────────┘
```

### 快速配置

**服务器端**:

```bash
# 1. 编辑 .env
cp env.example .env

# 2. 配置设备容量
MAX_DEVICES=100               # 最大设备数
HEALTH_CHECK_INTERVAL=60      # 健康检查间隔

# 3. 启动服务
./scripts/server/start.sh
```

**设备端** (每台 Android 设备):

```bash
# 在 Termux 中执行（需要输入服务器IP和端口）
bash <(curl -s https://your-server/client/install_termux.sh)
```

### Web UI 管理

访问 `http://服务器IP:5173`，即可看到：

- **首页**: 创建任务、选择设备、实时执行
- **设备管理**: 查看所有设备状态、连接情况
- **任务管理**: 历史任务、成功率统计

---

## 多服务器集群架构（大规模部署）

适用于：**100-1000+ 台设备**

```
                    ┌─────────────────────────────────────────┐
                    │          负载均衡器 / API Gateway        │
                    │           (Nginx / HAProxy)             │
                    └────────────────┬────────────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
    ┌───────┴───────┐        ┌───────┴───────┐        ┌───────┴───────┐
    │   Server 1    │        │   Server 2    │        │   Server N    │
    │  100 devices  │        │  100 devices  │        │  100 devices  │
    │  :8000/:9999  │        │  :8000/:9999  │        │  :8000/:9999  │
    └───────┬───────┘        └───────┬───────┘        └───────┴───────┘
            │                        │                        │
    ┌───────┴───────┐        ┌───────┴───────┐        ┌───────┴───────┐
    │   Devices     │        │   Devices     │        │   Devices     │
    │   1-100       │        │   101-200     │        │   201-300     │
    └───────────────┘        └───────────────┘        └───────────────┘
```

### 服务器端配置

**每台服务器的 .env**:

```bash
# Server 1 (管理设备 1-100)
SERVER_HOST=0.0.0.0
FRP_PORT=7000
WEBSOCKET_PORT=9999
MAX_DEVICES=100

# FRP端口范围: 6100-6199
```

```bash
# Server 2 (管理设备 101-200)
SERVER_HOST=0.0.0.0
FRP_PORT=7001        # 使用不同端口
WEBSOCKET_PORT=9998  # 使用不同端口
MAX_DEVICES=100

# FRP端口范围: 6200-6299（需修改 frps.ini）
```

**frps.ini 配置示例**（Server 2）:

```ini
[common]
bind_port = 7001
allow_ports = 6200-6299  # 不同服务器使用不同端口范围
max_pool_count = 200
```

### Nginx 负载均衡配置

```nginx
# /etc/nginx/conf.d/phoneagent.conf

upstream phoneagent_api {
    least_conn;  # 最少连接数策略
    server 192.168.1.101:8000 weight=1;
    server 192.168.1.102:8000 weight=1;
    server 192.168.1.103:8000 weight=1;
}

upstream phoneagent_ws {
    ip_hash;  # WebSocket需要会话保持
    server 192.168.1.101:9999;
    server 192.168.1.102:9998;
    server 192.168.1.103:9997;
}

server {
    listen 80;
    server_name phoneagent.your-domain.com;

    # API 代理
    location /api/ {
        proxy_pass http://phoneagent_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://phoneagent_ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

---

## 设备管理 API

PhoneAgent 提供完整的 RESTful API 用于设备管理：

### 获取所有设备

```bash
curl http://服务器IP:8000/api/v1/devices/scanned
```

**响应**:

```json
{
  "devices": [
    {
      "device_id": "device_6100",
      "device_name": "Xiaomi-12-6100",
      "status": "online",
      "frp_port": 6100,
      "frp_connected": true,
      "ws_connected": true,
      "model": "Xiaomi 12",
      "android_version": "13",
      "battery": 85,
      "current_task": null
    }
  ],
  "count": 50
}
```

### 获取设备详情

```bash
curl http://服务器IP:8000/api/v1/devices/device_6100
```

### 重命名设备

```bash
curl -X PATCH http://服务器IP:8000/api/v1/devices/device_6100/name \
  -H "Content-Type: application/json" \
  -d '{"device_name": "测试机-01"}'
```

### 获取统计信息

```bash
curl http://服务器IP:8000/api/v1/stats
```

---

## 自动任务分配

PhoneAgent 支持智能任务分配，无需手动指定设备：

```python
# Python SDK 示例
from phone_agent import PhoneAgent
from phone_agent.model import ModelConfig

config = ModelConfig(api_key="your-api-key")
agent = PhoneAgent(model_config=config)

# 自动选择空闲设备执行
result = agent.run("打开微信，发送消息给张三")
```

**负载均衡策略**:

1. 筛选可用设备（双通道连接 + 在线 + 无任务）
2. 检查心跳是否过期（默认 2 分钟超时）
3. 按成功率排序（优先使用稳定设备）
4. 返回最优设备

---

## 故障排查

### 设备连接问题

```bash
# 检查 FRP 连接
netstat -tlnp | grep 610

# 检查 WebSocket 服务
curl http://127.0.0.1:9999/devices

# 查看服务器日志
tail -f logs/phoneagent.log | grep -E "Device|FRP|WebSocket"
```

### 设备离线处理

设备离线时会自动：
1. 标记为 `offline` 状态
2. 释放占用的 FRP 端口
3. 从任务队列中移除

重新连接后会自动恢复。

---

## 扩展建议

| 规模 | 建议配置 | 服务器数量 |
|------|---------|-----------|
| 1-50 台 | 单服务器，默认配置 | 1 |
| 50-100 台 | 单服务器，增加 `HEALTH_CHECK_INTERVAL=120` | 1 |
| 100-300 台 | 3 台服务器 + Nginx | 3 |
| 300-1000 台 | K8s 集群部署 | 10+ |

---

## 相关文档

- [部署指南](DEPLOYMENT.md) - 完整安装步骤
- [自托管模型](SELF_HOSTED_MODEL.md) - 本地模型部署
- API 参考: `http://YOUR_SERVER_IP:8000/docs` - Swagger API 文档

---

**最后更新**: 2025-01
