<div align="center">

# PhoneAgent

### Complete AI Phone Assistant Solution, Ready to Use

**Web Interface + Backend + Terminal | One-Click Deploy | Multi-Device | Live Preview**

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D?style=for-the-badge&logo=vue.js&logoColor=white)](https://vuejs.org/)

<br>

[中文](README.md) | English

</div>

---

## Why PhoneAgent?

> **Built on Open-AutoGLM, completing the last mile of engineering**

[Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) is an excellent open-source phone Agent project, but only provides CLI tools. **PhoneAgent** adds Web interface, multi-device support, live preview and other capabilities, making it truly **ready to use**.

| Comparison | Open-AutoGLM | PhoneAgent |
|------------|--------------|------------|
| **Interface** | ❌ CLI only | ✅ Modern Web UI |
| **Usage** | ❌ Requires coding | ✅ Natural language + Voice |
| **Devices** | ❌ Single device | ✅ Multi-device pool |
| **Models** | ❌ Single model | ✅ GLM-4.6v series + Multi-platform |
| **Deployment** | ❌ Manual config | ✅ One-click script |
| **Preview** | ❌ None | ✅ Scrcpy live stream |
| **Protection** | ❌ None | ✅ Anti-detection system |

---

## Project Features

### 1. Smart Execution Engine + Dual Mode Support

PhoneAgent uses advanced visual understanding technology with two execution modes:

```
┌─────────────────────────────────────────────────────┐
│            PhoneAgent Smart Execution Engine         │
│                                                       │
│  ┌────────────────────────────────────────────┐    │
│  │       Step-by-Step Mode (Recommended)      │    │
│  │                                              │    │
│  │  • Stable & Reliable - AI thinks each step │    │
│  │  • Vision Understanding - GLM-4.6v series   │    │
│  │  • Complete Logs - JSONL format, traceable │    │
│  │  • Real-time Feedback - WebSocket progress │    │
│  └────────────────────────────────────────────┘    │
│                                                       │
│  ┌────────────────────────────────────────────┐    │
│  │    Smart Planning Mode (⚠️ Beta - Unstable) │    │
│  │                                              │    │
│  │  • Pre-planning - AI generates full plan    │    │
│  │  • Batch Execution - 70% faster, 70% cheaper│    │
│  │  ⚠️ Low Success Rate - Not for production   │    │
│  │  ⚠️ Only for simple task testing            │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Execution Modes**:
- **Step-by-Step (✅ Recommended)**: AI decides each step, suitable for all tasks, highly stable
- **Smart Planning (⚠️ Beta, Unstable)**: Pre-plans complete steps, faster, but low success rate, only for simple testing

### 2. Real-time Screen Preview

- Integrated Scrcpy, view device screen in real-time, <150ms latency
- H.264 video stream, efficient compression, supports remote operation
- Task execution visualization, manual takeover on errors

### 3. Multi-Device Pool Management

- Manage multiple devices simultaneously
- FRP port scanning, auto-discover online devices
- WebSocket real-time device status sync

### 4. Complete Anti-Detection System

- Time Randomization - Simulate human operation rhythm
- Coordinate Randomization - Random click position offset
- Bezier Curve Sliding - Natural sliding trajectory
- App Whitelist - Restrict operable app range

---

## System Architecture

PhoneAgent uses **Dual WebSocket Service** architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Frontend (Vue 3)                      │
│         https://your-domain.com or http://SERVER_IP:5173    │
└────────────┬────────────────────────────────────────────────┘
             │
             ├─────────────────┬──────────────────┬───────────┐
             ↓                 ↓                  ↓           ↓
    ┌────────────────┐ ┌─────────────────┐ ┌──────────┐ ┌──────────┐
    │  API Server     │ │ WebSocket Server│ │FRP Server│ │  Device  │
    │   (Port 8000)   │ │   (Port 9999)   │ │(Port 7000)│ │ (Termux) │
    │                 │ │                 │ │          │ │          │
    │ • REST API      │ │ • Device Mgmt   │ │ • ADB Fwd│ │ • ADB Run│
    │ • Frontend WS   │ │ • Task Dispatch │ │ • Port   │ │ • Status │
    │   /api/v1/ws    │ │ • Status Sync   │ │   Tunnel │ │ • Scrcpy │
    │ • Scrcpy WS     │ │   /ws/device/*  │ │          │ │          │
    └────────────────┘ └─────────────────┘ └──────────┘ └──────────┘
```

**Three Key WebSockets**:
1. **Frontend WebSocket** (Port `8000` `/api/v1/ws`) - Real-time frontend status push
2. **Device WebSocket** (Port `9999` `/ws/device/{frp_port}`) - Device connection management
3. **Scrcpy WebSocket** (Port `8000` `/api/v1/scrcpy/stream/{device_id}`) - Video stream transmission

---

## Project Showcase

### Web Management Interface

<div align="center">
<img src="assets/images/首页.jpg" alt="Dashboard" width="800">
<p><em>Dashboard - Multi-device Management & Task Monitoring</em></p>
</div>

<div align="center">
<img src="assets/images/设备管理.jpg" alt="Device Management" width="800">
<p><em>Device Management - Real-time Multi-device Pool Status</em></p>
</div>

<div align="center">
<img src="assets/images/防风控配置.jpg" alt="Anti-Detection Config" width="800">
<p><em>Anti-Detection Config - Time Randomization & Trajectory Optimization</em></p>
</div>

<div align="center">
<img src="assets/images/性能诊断.jpg" alt="Performance Diagnostics" width="800">
<p><em>Performance Diagnostics - System Resources & Task Execution Monitoring</em></p>
</div>

---

## Use Cases

### Personal

- **Driving** - Voice messaging, navigation, music
- **Exercise** - Control music, check messages
- **Work** - Set reminders, quick replies

### Enterprise

- **App Automated Testing** - 100 devices in parallel, 10 minutes = 2 days work
- **Content Batch Operations** - Multi-account auto-posting, anti-detection mechanism
- **Data Collection** - Automated information gathering and organization

---

## Core Features

### Tasks & Interaction

- ✅ **Natural Language Tasks** - Describe tasks in plain language, AI executes automatically
- ✅ **Voice Input** - Web voice recording + STT recognition (requires HTTPS)
- ✅ **Quick Commands** - Preset common operations, one-click execution
- ✅ **Task Interruption** - Support manual intervention and takeover
- ✅ **Smart Planning** - Pre-plan steps, batch execution (Beta)

### Device Management

- ✅ **Multi-Device Pool** - Manage 100+ devices simultaneously
- ✅ **Auto Discovery** - FRP port scanning, auto-identify online devices
- ✅ **Real-time Monitoring** - WebSocket real-time device status sync

### Live Preview

- ✅ **Scrcpy Integration** - View device screen in real-time, <150ms latency
- ✅ **H.264 Video Stream** - Efficient compression, bandwidth-saving
- ✅ **Manual Control** - Direct click to operate device

### Security & Protection

- ✅ **Time Randomization** - Simulate human operation rhythm
- ✅ **Coordinate Randomization** - Random click position offset
- ✅ **Bezier Curve Sliding** - Natural sliding trajectory
- ✅ **App Whitelist** - Restrict operable app range

---


## Quick Start

### Requirements

**Server**:
- Ubuntu 20.04+ / Debian 11+, 2-core 4GB+
- Public IP (required for FRP tunneling)
- Open ports:
  - `7000` - FRP Server
  - `8000` - API Server (includes Frontend WS and Scrcpy WS)
  - `9999` - Device WebSocket Server
  - `6100-6199` - FRP client port range (1 port per device)

**Android Device**:
- Android 7.0+, USB debugging enabled
- Termux installed (from [F-Droid](https://f-droid.org/packages/com.termux/))

### 10-Minute Deployment

#### 1️⃣ Server

```bash
git clone https://github.com/unal-ai/PhoneAgent.git
cd PhoneAgent

# Configure API key
cp env.example .env
nano .env  # Fill in ZHIPU_API_KEY

# One-click install (will prompt for FRP_TOKEN during installation)
sudo bash scripts/install/install_server.sh
```

#### 2️⃣ Client (Termux)

```bash
bash <(curl -s https://cdn.jsdelivr.net/gh/unal-ai/PhoneAgent@main/client/install_termux.sh)
```

**Installation requires 4 parameters**:
1. Backend server IP
2. FRP Token (same as server)
3. Connection mode (1=Direct IP / 2=Domain proxy)
4. Frontend access address (IP or domain)

**⚠️ Important First-Time Setup** (Must execute, otherwise unable to connect):

After deployment script completes, **need to execute the following commands on your computer** to make the phone's ADB daemon listen on TCP port:

**Prerequisites**: Computer needs to have ADB tools installed first

<details>
<summary>📦 Computer ADB Installation (Click to expand)</summary>

**Windows**:
```bash
# Method 1: Use Chocolatey (Recommended)
choco install adb

# Method 2: Manual download
# Visit https://developer.android.com/tools/releases/platform-tools
# Download platform-tools, extract and add to system PATH
```

**macOS**:
```bash
# Use Homebrew
brew install android-platform-tools
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt update
sudo apt install adb
```

Verify installation:
```bash
adb version
```

</details>

**Execute ADB TCP Configuration**:

```bash
# Method 1: Execute via USB connection to computer (Recommended)
# 1. Connect phone to computer via USB
# 2. Run in computer terminal:
adb tcpip 5555

# Method 2: If phone has enabled wireless debugging (Android 11+)
# Get pairing code in phone Settings → Developer options → Wireless debugging
# Then run in computer terminal: adb pair <IP>:<port>
```

**Notes**:
- This configuration **will reset after phone reboot**, need to re-execute
- If not executed, server will show device `offline`

#### 3️⃣ Frontend

**Simple Mode (IP direct, 2 minutes)**:
```bash
cd web
npm install && npm run dev -- --host 0.0.0.0
# Access: http://SERVER_IP:5173
```

**Complete Mode (Domain+SSL, voice support)**: See [Deployment Guide](docs/DEPLOYMENT.md)

### Get Zhipu AI API Key

Visit [Zhipu AI Platform](https://open.bigmodel.cn/) → Register → Create API Key → Fill in `.env`

---

## Documentation

| Document | Description |
|----------|-------------|
| **[Deployment Guide](docs/DEPLOYMENT.md)** | Complete deployment steps and configuration |
| **[Project Assessment](docs/PROJECT_ASSESSMENT.md)** | Project completion assessment and technical analysis |
| **[Implementation Roadmap](docs/ROADMAP.md)** | Upgrade guide from prototype to production |
| **[Comparison Analysis](docs/COMPARISON_MIDSCENE.md)** | Comparison with Midscene.js and key takeaways |
| **[Self-Hosted Model](docs/SELF_HOSTED_MODEL.md)** | Local AutoGLM model deployment guide |
| **[Multi-Device Management](docs/MULTI_DEVICE_MANAGEMENT.md)** | Multi-device centralized management and cluster deployment |

**Two Deployment Modes**:
- **Simple Mode**: IP direct, 10 minutes, suitable for quick experience and testing
- **Complete Mode**: Domain+SSL+Reverse Proxy, 30 minutes, supports voice input and full features

---

## AI Model Support

### Default Models (Zhipu AI)

| Model | Type | Features | Recommended Scenario |
|------|------|----------|---------------------|
| `autoglm-phone` | 🆓 Free | Official Phone model, optimized for phones | **Default Recommended** ⭐ |
| `glm-4.6v-flash` | 🆓 Free | Latest vision model, high cost-performance | General vision tasks |
| `glm-4.6v` | 💰 Paid | Flagship vision model, strongest understanding | Complex tasks, high precision |
| `glm-4.6v-flashx` | 💰 Paid | Ultra-fast response version | Real-time interaction |

**Out of the Box**: Uses `autoglm-phone` by default (free, optimized for phones), no configuration needed.

**Switch to Other Models**:
```bash
# .env file
CUSTOM_MODEL_NAME=glm-4.6v-flash  # Latest free model
CUSTOM_MODEL_NAME=glm-4.6v  # Paid flagship model
CUSTOM_MODEL_NAME=glm-4.6v-flashx  # Paid ultra-fast model
```

### Multi-Platform Support

PhoneAgent supports any OpenAI-compatible vision model:

```bash
# Switch to OpenAI GPT-4o
MODEL_PROVIDER=openai
CUSTOM_API_KEY=sk-proj-xxxxx
CUSTOM_MODEL_NAME=gpt-4o

# Switch to Google Gemini
MODEL_PROVIDER=gemini
CUSTOM_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXX
CUSTOM_MODEL_NAME=gemini-2.0-flash

# Switch to Qwen
MODEL_PROVIDER=qwen
CUSTOM_API_KEY=sk-xxxxx
CUSTOM_MODEL_NAME=qwen-vl-plus
```

See configuration guide (Environment Variables Configuration section)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Vue 3 + Vite + Element Plus + Pinia |
| **Backend** | FastAPI + SQLite + WebSocket + FRP |
| **AI** | AutoGLM-Phone / GLM-4.6v series / OpenAI-Compatible |
| **Terminal** | Termux + ADB + Scrcpy |
| **Execution Engine** | Step-by-Step + Smart Planning (Beta) |

---

## License

Based on [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) (Apache 2.0) with deep refactoring, open-sourced under **AGPL 3.0**.

### Usage Scope

| Use Case | Allowed |
|----------|---------|
| ✅ Personal learning and research | Free to use |
| ✅ Internal enterprise use | Free to use |
| ✅ Modify code for internal use | Free to use |
| ⚠️ Provide modified services externally | Must open source modified code |
| ⚠️ Integrate into product for sale | Must open source modified code |

**AGPL 3.0 Core**: When modifying code and providing services over a network, must disclose source code. See [LICENSE](LICENSE) file for details.

**Third-Party Licenses**: This project uses code from multiple open-source projects, see [LICENSES_THIRD_PARTY.md](LICENSES_THIRD_PARTY.md)

### ⚠️ Usage Restrictions & Responsibilities

**Please Read**: [Privacy & Security Policy](privacy_policy.txt)

PhoneAgent can control your Android device for automation. Please understand the following before use:

**Allowed Use Cases**:
- ✅ Personal device automation
- ✅ Testing and development environments
- ✅ Learning and research purposes
- ✅ Legal business process automation

**Strictly Prohibited**:
- ❌ Fake data operations (fake orders, likes, comments, etc.)
- ❌ Batch account registration, device control farms
- ❌ Violating third-party app terms of service
- ❌ Privacy invasion, account theft
- ❌ Any illegal activities

**High-Risk Operation Warnings**:
- ⚠️ Payment and transfer operations require manual review
- ⚠️ Protect sensitive information like passwords
- ⚠️ Monitor important operations manually

**Disclaimer**:
- This software is provided "as is" without warranty
- Users are fully responsible for their operations
- Developers are not liable for any losses caused by using this software
- Please comply with local laws and third-party service terms

For details, see: [privacy_policy.txt](privacy_policy.txt)

---

## Contributing

Welcome to submit issues and suggestions via GitHub Issues.

---

## Acknowledgments

This project is developed based on the following open-source projects, with sincere thanks.

### Core Technology Source

**[Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM)** (Apache 2.0)

The core execution engine of this project comes from this excellent phone Agent research project. I have made engineering transformations on top of it, adding Web interface, multi-device management, smart planning and other features.

**[Zhipu AI](https://open.bigmodel.cn/)**

Thanks for providing free autoglm-phone vision model and voice recognition services.

### Technical Infrastructure

The following open-source projects provide technical support for this project:

- **[Scrcpy](https://github.com/Genymobile/scrcpy/)** - Android screen mirroring
- **[FRP](https://github.com/fatedier/frp)** - Intranet penetration
- **[YADB](https://github.com/ysbing/YADB)** - ADB enhancement (Chinese input, forced screenshot)
- **[Vue.js](https://vuejs.org/)** - Frontend framework
- **[FastAPI](https://fastapi.tiangolo.com/)** - Backend framework
- **[Element Plus](https://element-plus.org/)** - UI component library
- **[Termux](https://termux.dev/)** - Android terminal

Thanks to all open-source contributors.
