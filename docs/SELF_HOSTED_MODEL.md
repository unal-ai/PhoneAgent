# 自托管 AutoGLM 模型配置指南

> 本指南介绍如何在本地部署 AutoGLM-Phone-9B 模型并与 PhoneAgent 集成

## 前提条件

1. **硬件要求**:
   - GPU: NVIDIA GPU (至少 16GB 显存，推荐 A100/4090)
   - 内存: 32GB+ RAM
   - 存储: 50GB+ 可用空间

2. **软件要求**:
   - Python 3.10+
   - CUDA 11.8+ / 12.0+
   - PyTorch 2.0+

3. **已部署的模型服务**:
   - AutoGLM-Phone-9B 模型 (OpenAI 兼容 API)
   - 服务地址，如: `http://127.0.0.1:6002/v1`

---

## 快速配置

### 方式一: 通过 .env 文件配置

编辑项目根目录下的 `.env` 文件:

```bash
# 1. 设置提供商为 "local"
MODEL_PROVIDER=local

# 2. 设置你的本地模型服务地址
CUSTOM_BASE_URL=http://127.0.0.1:6002/v1

# 3. API Key（本地部署可能不需要，但需要设置一个值）
CUSTOM_API_KEY=EMPTY

# 4. 模型名称（与你部署时使用的模型名称一致）
CUSTOM_MODEL_NAME=autoglm-phone-9b
```

### 方式二: 通过环境变量配置

```bash
# 启动前设置环境变量
export MODEL_PROVIDER=local
export CUSTOM_BASE_URL=http://127.0.0.1:6002/v1
export CUSTOM_API_KEY=EMPTY
export CUSTOM_MODEL_NAME=autoglm-phone-9b

# 然后启动服务
./scripts/server/start.sh
```

---

## 完整单机 MVP 流程

以下是在一台电脑上从零开始运行 PhoneAgent + 自托管模型的完整流程:

### Step 1: 部署 AutoGLM-Phone-9B 模型

```bash
# 克隆官方模型仓库
git clone https://github.com/zai-org/AutoGLM-Phone-9B-Multilingual.git
cd AutoGLM-Phone-9B-Multilingual

# 安装依赖
pip install -r requirements.txt

# 启动 OpenAI 兼容的 API 服务
# 注意: --trust-remote-code 允许执行远程代码，仅在信任模型来源时使用
python -m vllm.entrypoints.openai.api_server \
    --model zai-org/AutoGLM-Phone-9B-Multilingual \
    --port 6002 \
    --host 127.0.0.1 \
    --trust-remote-code

# 服务启动后，会在 http://127.0.0.1:6002/v1 提供 API
```

### Step 2: 配置 PhoneAgent

```bash
# 进入 PhoneAgent 目录
cd PhoneAgent

# 复制并编辑配置文件
cp env.example .env
nano .env
```

在 `.env` 中添加以下配置:

```bash
# 本地模型配置
MODEL_PROVIDER=local
CUSTOM_BASE_URL=http://127.0.0.1:6002/v1
CUSTOM_API_KEY=EMPTY
CUSTOM_MODEL_NAME=autoglm-phone-9b

# 禁用智谱API（使用本地模型）
ZHIPU_API_KEY=
```

### Step 3: 连接 Android 设备

```bash
# 确保设备已通过 USB 连接并开启开发者模式
adb devices

# 应该看到你的设备列表
# List of devices attached
# XXXXXXXX    device

# 可选: 开启 ADB 网络调试（仅在受信任的本地网络中使用）
# 注意: ADB TCP 模式无认证，请勿在公共网络中使用
adb tcpip 5555
adb connect 127.0.0.1:5555
```

### Step 4: 启动 PhoneAgent 服务

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端服务
# 本地开发建议使用 127.0.0.1，如需远程访问请配置防火墙
python -m uvicorn server.api.app:app --host 127.0.0.1 --port 8000 &

# 启动前端（另一个终端）
cd web
npm install
npm run dev
```

### Step 5: 验证配置

```bash
# 测试模型连接
curl http://127.0.0.1:6002/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "autoglm-phone-9b",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 测试 PhoneAgent 服务
curl http://127.0.0.1:8000/api/v1/health
```

### Step 6: 使用 Web 界面

1. 打开浏览器访问: `http://localhost:5173`
2. 在设备列表中选择你的 Android 设备
3. 输入任务指令（如: "打开设置"）
4. 点击"创建并执行任务"

---

## 高级配置

### 多模型配置

如果你部署了多个模型，可以分别配置:

```bash
# 逐步执行模式使用的模型
VISION_KERNEL_MODEL=autoglm-phone-9b

# 智能规划模式使用的模型
PLANNING_KERNEL_MODEL=glm-4-9b
```

### 负载均衡配置

如果有多个模型服务实例:

```bash
# 可使用 nginx 做负载均衡
# nginx.conf 示例:
# upstream model_servers {
#     server 127.0.0.1:6002;
#     server 127.0.0.1:6003;
# }

CUSTOM_BASE_URL=http://127.0.0.1/v1  # nginx 代理地址
```

### 性能优化

```bash
# 减少 token 使用（本地模型可能较慢）
MAX_TOKENS=2000

# 降低温度以获得更稳定的输出
TEMPERATURE=0.3

# 减少最大步数（防止长时间运行）
MAX_TASK_STEPS=50
```

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      单机部署架构                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐     ┌─────────────────┐     ┌─────────────┐  │
│   │  Web 前端   │────→│  PhoneAgent     │────→│  AutoGLM    │  │
│   │  :5173     │     │  Server :8000   │     │  API :6002  │  │
│   └─────────────┘     └────────┬────────┘     └─────────────┘  │
│                                │                               │
│                                │ ADB 通信                      │
│                                ▼                               │
│                        ┌─────────────┐                         │
│                        │  Android    │                         │
│                        │  设备       │                         │
│                        │  USB/WiFi   │                         │
│                        └─────────────┘                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 常见问题

### Q1: 本地模型响应很慢怎么办？

**A**: 尝试以下优化:
1. 使用量化版本的模型 (AWQ/GPTQ)
2. 增加 GPU 数量 (`tensor-parallel-size`)
3. 调整 `MAX_TOKENS` 为较小的值

### Q2: 模型输出格式不正确怎么办？

**A**: AutoGLM-Phone 期望特定的输出格式。确保:
1. 使用官方推荐的 prompt 模板
2. 检查模型版本是否正确
3. 查看日志中的原始输出

### Q3: ADB 连接失败怎么办？

**A**: 检查以下项目:
```bash
# 重启 ADB 服务
adb kill-server
adb start-server

# 检查设备授权
adb devices  # 设备状态应为 "device" 而非 "unauthorized"

# 检查开发者选项
# 设置 → 开发者选项 → USB 调试 → 开启
```

### Q4: 如何同时使用本地模型和云端API？

**A**: 目前 PhoneAgent 单次运行只支持一个模型端点。建议:
1. 生产任务使用云端 API (稳定)
2. 测试/开发使用本地模型 (省钱)
3. 通过切换 `.env` 配置来切换

---

## 相关资源

- [AutoGLM-Phone-9B 官方仓库](https://github.com/zai-org/AutoGLM-Phone-9B-Multilingual)
- [vLLM 部署指南](https://docs.vllm.ai/en/latest/)
- [PhoneAgent 部署文档](DEPLOYMENT.md)
- [项目评估](PROJECT_ASSESSMENT.md)

---

## 最佳实践总结

1. **先验证模型服务**: 启动 PhoneAgent 前，确保 `curl` 能正常调用模型 API
2. **使用稳定版本**: 推荐使用官方发布的模型版本
3. **监控资源使用**: 关注 GPU 显存和系统内存使用情况
4. **保存日志**: 开启 `LOG_LEVEL=DEBUG` 便于排查问题
5. **逐步测试**: 先测试简单任务（如"返回主页"），再尝试复杂任务

---

**最后更新**: 2025-01
