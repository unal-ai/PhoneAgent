<div align="center">

# PhoneAgent

### A Complete Android Agent Solution Based on Open-AutoGLM

**Web UI + Backend + Terminal | One-Click Deploy | Multi-Device | Real-time Preview**

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D?style=for-the-badge&logo=vue.js&logoColor=white)](https://vuejs.org/)

<br>

[中文](README.md) | [English](README_EN.md)

</div>

---

## What is this?

PhoneAgent is a community-enhanced version of [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM).

Open-AutoGLM is an excellent Android Agent project open-sourced by the Zhipu team, providing CLI tools and APIs. We've added engineering features on top to make it production-ready:

- **Web UI** - Modern interface, no coding required
- **Multi-Device Management** - Manage multiple devices simultaneously
- **Real-time Screen Preview** - Integrated Scrcpy, <150ms latency
- **Multi-Model Support** - GLM-4.6v series + third-party APIs

---

## Screenshots

<div align="center">
<img src="assets/images/首页.jpg" alt="Home" width="800">
<p><em>Home - Multi-device management and task monitoring</em></p>
</div>

<div align="center">
<img src="assets/images/设备管理.jpg" alt="Device Management" width="800">
<p><em>Device Management - Real-time device pool monitoring</em></p>
</div>

---

## Key Features

### Task Execution

- **Natural Language Tasks** - Describe tasks in plain language, AI executes automatically
- **Voice Input** - Web voice recording + STT (requires HTTPS)
- **Real-time Feedback** - WebSocket pushes progress for each step

### Device Management

- **Device Pool** - Manage 100+ devices simultaneously
- **Auto Discovery** - FRP port scanning, automatic device detection
- **State Sync** - WebSocket real-time device state synchronization

### Live Preview

- **Scrcpy Integration** - Real-time device screen viewing
- **H.264 Streaming** - Efficient compression, bandwidth-friendly

---

## Quick Start

### Requirements

**Server**: Ubuntu 20.04+ / Debian 11+, 2 cores / 4GB+, public IP

**Android Device**: Android 7.0+, USB debugging enabled

### 10-Minute Deployment

#### 1️⃣ Server

```bash
git clone https://github.com/unal-ai/PhoneAgent.git
cd PhoneAgent

# Configure API key
cp env.example .env
nano .env  # Fill in ZHIPU_API_KEY

# One-click install
sudo bash scripts/install/install_server.sh
```

#### 2️⃣ Client (Termux)

```bash
bash <(curl -s https://cdn.jsdelivr.net/gh/unal-ai/PhoneAgent@main/client/install_termux.sh)
```

#### 3️⃣ Frontend

```bash
cd web
npm install && npm run dev -- --host 0.0.0.0
# Access: http://SERVER_IP:5173
```

For detailed steps, see [Deployment Guide](docs/DEPLOYMENT.md).

### Get API Key

Visit [Zhipu AI Platform](https://open.bigmodel.cn/) → Register → Create API Key → Add to `.env`

---

## AI Model Support

### Default Models (Zhipu AI)

| Model | Type | Description |
|-------|------|-------------|
| `autoglm-phone` | 🆓 Free | Official Phone model, mobile-optimized |
| `glm-4.6v-flash` | 🆓 Free | Latest vision model, cost-effective |
| `glm-4.6v` | 💰 Paid | Flagship vision model |

### Multi-Platform Support

Any OpenAI-compatible vision model works:

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

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Frontend (Vue 3)                       │
└────────────┬────────────────────────────────────────────────┘
             │
             ├─────────────────┬──────────────────┬───────────┐
             ↓                 ↓                  ↓           ↓
    ┌────────────────┐ ┌─────────────────┐ ┌──────────┐ ┌──────────┐
    │  API Server    │ │ WebSocket Server│ │FRP Server│ │  Device  │
    │   (port 8000)  │ │   (port 9999)   │ │(port 7000)│ │ (Termux) │
    └────────────────┘ └─────────────────┘ └──────────┘ └──────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Vue 3 + Vite + Element Plus |
| **Backend** | FastAPI + SQLite + WebSocket |
| **AI** | AutoGLM-Phone / GLM-4.6v / OpenAI-Compatible |
| **Device** | Termux + ADB + Scrcpy |

---

## Documentation

| Doc | Description |
|-----|-------------|
| [Deployment Guide](docs/DEPLOYMENT.md) | Complete deployment steps |
| [Self-Hosted Model](docs/SELF_HOSTED_MODEL.md) | Local model deployment |
| [Multi-Device Management](docs/MULTI_DEVICE_MANAGEMENT.md) | Cluster deployment guide |

---

## License

This project is licensed under **AGPL-3.0**, based on [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) (Apache 2.0).

**In simple terms**:

- ✅ You can freely use, modify, and distribute this project
- ✅ Personal use and internal enterprise use are completely free
- 📤 **The only requirement**: If you modify the code and provide network services to users, please open-source your improvements back to the community

That's what open source is about — **sharing benefits everyone**.

See [LICENSE](LICENSE) and [Third-Party Licenses](LICENSES_THIRD_PARTY.md) for details.

---

## Contributing

Feel free to submit issues and suggestions via GitHub Issues, and pull requests are welcome.

---

## Acknowledgements

This project stands on the shoulders of giants:

- **[Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)** - The core foundation of this project. Thanks to Zhipu team for their open-source contribution
- **[Zhipu AI](https://open.bigmodel.cn/)** - For providing the free autoglm-phone model
- **[Scrcpy](https://github.com/Genymobile/scrcpy/)** - Android screen mirroring
- **[FRP](https://github.com/fatedier/frp)** - NAT traversal
- **[YADB](https://github.com/ysbing/YADB)** - ADB enhancements (Chinese input, force screenshot)
- **[Vue.js](https://vuejs.org/)** / **[FastAPI](https://fastapi.tiangolo.com/)** / **[Element Plus](https://element-plus.org/)** - Web tech stack

Thanks to all open-source contributors.
