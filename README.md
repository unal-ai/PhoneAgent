<div align="center">

# PhoneAgent

### 基于 Open-AutoGLM 的 Android Agent 完整解决方案

**Web 交互界面 + 后端 + 终端 | 一键部署 | 多设备管理 | 实时预览**

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D?style=for-the-badge&logo=vue.js&logoColor=white)](https://vuejs.org/)

<br>

[中文](README.md) | [English](README_EN.md)

</div>

---

## 这是什么？

PhoneAgent 是 [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) 的社区改进版。

Open-AutoGLM 是智谱团队开源的优秀 Android Agent 项目，提供了命令行工具和 API。我们在此基础上增加了工程化功能，让它能够真正落地使用：

- **Web 交互界面** - 现代化 UI，无需写代码
- **多设备管理** - 同时管理多台设备
- **实时屏幕预览** - 集成 Scrcpy，延迟 <150ms
- **多模型支持** - GLM-4.6v 系列 + 第三方 API

---

## 项目展示

<div align="center">
<img src="assets/images/首页.jpg" alt="首页" width="800">
<p><em>首页 - 多设备管理与任务监控</em></p>
</div>

<div align="center">
<img src="assets/images/设备管理.jpg" alt="设备管理" width="800">
<p><em>设备管理 - 多设备池实时状态监控</em></p>
</div>

---

## 主要功能

### 任务执行

- **自然语言任务** - 用中文描述任务，AI 自动执行
- **语音输入** - Web 端语音录制 + STT 识别（需 HTTPS）
- **实时反馈** - WebSocket 推送每步进度

### 设备管理

- **多设备池** - 支持同时管理 100+ 台设备
- **自动发现** - FRP 端口扫描，自动识别在线设备
- **状态同步** - WebSocket 实时同步设备状态

### 实时预览

- **Scrcpy 集成** - 实时查看设备屏幕
- **H.264 视频流** - 高效压缩，节省带宽

---

## 快速开始

### 系统要求

**服务器**：Ubuntu 20.04+ / Debian 11+，2核4GB+，公网 IP

**Android 设备**：Android 7.0+，已开启 USB 调试

### 10分钟部署

#### 1️⃣ 服务端

```bash
git clone https://github.com/unal-ai/PhoneAgent.git
cd PhoneAgent

# 配置 API 密钥
cp env.example .env
nano .env  # 填写 ZHIPU_API_KEY

# 一键安装
sudo bash scripts/install/install_server.sh
```

#### 2️⃣ 客户端（Termux）

```bash
bash <(curl -s https://cdn.jsdelivr.net/gh/unal-ai/PhoneAgent@main/client/install_termux.sh)
```

#### 3️⃣ 前端

```bash
cd web
npm install && npm run dev -- --host 0.0.0.0
# 访问：http://SERVER_IP:5173
```

详细步骤请参考 [部署文档](docs/DEPLOYMENT.md)。

### 获取 API 密钥

访问 [智谱AI开放平台](https://open.bigmodel.cn/) → 注册 → 创建 API 密钥 → 填入 `.env`

---

## AI 模型支持

### 默认模型（智谱 AI）

| 模型 | 类型 | 特点 |
|------|------|------|
| `autoglm-phone` | 🆓 免费 | 官方 Phone 模型，针对手机优化 |
| `glm-4.6v-flash` | 🆓 免费 | 最新视觉模型，高性价比 |
| `glm-4.6v` | 💰 付费 | 旗舰视觉模型 |

### 多平台支持

支持任何 OpenAI 兼容的视觉模型：

```bash
# OpenAI GPT-4o
MODEL_PROVIDER=openai
CUSTOM_API_KEY=sk-proj-xxxxx
CUSTOM_MODEL_NAME=gpt-4o

# Google Gemini
MODEL_PROVIDER=gemini
CUSTOM_API_KEY=AIzaSyXXXXXXXX
CUSTOM_MODEL_NAME=gemini-2.0-flash
```

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Web 前端（Vue 3）                          │
└────────────┬────────────────────────────────────────────────┘
             │
             ├─────────────────┬──────────────────┬───────────┐
             ↓                 ↓                  ↓           ↓
    ┌────────────────┐ ┌─────────────────┐ ┌──────────┐ ┌──────────┐
    │  API 服务器     │ │ WebSocket 服务器│ │FRP 服务器│ │  设备端  │
    │   (8000端口)    │ │   (9999端口)    │ │(7000端口)│ │ (Termux) │
    └────────────────┘ └─────────────────┘ └──────────┘ └──────────┘
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3 + Vite + Element Plus |
| **后端** | FastAPI + SQLite + WebSocket |
| **AI** | AutoGLM-Phone / GLM-4.6v / OpenAI-Compatible |
| **终端** | Termux + ADB + Scrcpy |

---

## 文档

| 文档 | 说明 |
|------|------|
| [部署指南](docs/DEPLOYMENT.md) | 完整的部署步骤 |
| [自托管模型](docs/SELF_HOSTED_MODEL.md) | 本地部署模型配置 |
| [多设备管理](docs/MULTI_DEVICE_MANAGEMENT.md) | 集群部署指南 |

---

## 开源协议

本项目采用 **AGPL-3.0** 许可证，基于 [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)（Apache 2.0）开发。

**简单来说**：

- ✅ 你可以免费使用、修改、分发这个项目
- ✅ 个人使用、企业内部使用完全自由
- 📤 **唯一的要求**：如果你修改了代码并向用户提供网络服务，请把改进开源回馈社区

这就是开源的意义——**分享让所有人受益**。

详见 [LICENSE](LICENSE) 和 [第三方许可证声明](LICENSES_THIRD_PARTY.md)。

---

## 贡献

欢迎通过 GitHub Issues 提交问题和建议，也欢迎提交 Pull Request。

---

## 致谢

本项目站在巨人的肩膀上：

- **[Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)** - 本项目的核心基础，感谢智谱团队的开源贡献
- **[智谱 AI](https://open.bigmodel.cn/)** - 提供免费的 autoglm-phone 模型
- **[Scrcpy](https://github.com/Genymobile/scrcpy/)** - Android 屏幕镜像
- **[FRP](https://github.com/fatedier/frp)** - 内网穿透
- **[YADB](https://github.com/ysbing/YADB)** - ADB 增强（中文输入、强制截图）
- **[Vue.js](https://vuejs.org/)** / **[FastAPI](https://fastapi.tiangolo.com/)** / **[Element Plus](https://element-plus.org/)** - Web 技术栈

感谢所有开源贡献者。
