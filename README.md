# PhoneAgent

PhoneAgent 是基于 Open-AutoGLM 的 Android Agent 完整解决方案。

它在 Open-AutoGLM 的基础上增加了 Web 交互界面、多设备管理和实时屏幕预览功能，旨在提供一套成熟可用的 Android 自动化基础设施。

## 主要功能

- **Web 交互界面**: 基于 Vue 3 的现代化界面，无需编写代码即可使用。
- **多设备管理**: 支持在同一后台管理多台设备。
- **实时屏幕预览**: 集成 Scrcpy，提供低延迟（<150ms）的屏幕镜像。
- **多模型支持**: 支持 GLM-4.6v 系列及所有兼容 OpenAI 接口的视觉模型。

## 快速开始

### 系统要求

- **服务器**: Ubuntu 20.04+ 或 Debian 11+，2核 CPU，4GB 内存，公网 IP。
- **Android 设备**: Android 7.0+，已开启 USB 调试。

### 部署步骤

1.  **克隆仓库**

    ```bash
    git clone https://github.com/unal-ai/PhoneAgent.git
    cd PhoneAgent
    ```

2.  **配置环境**

    ```bash
    cp env.example .env
    # 编辑 .env 文件并填入 ZHIPU_API_KEY
    ```

3.  **安装服务端**

    ```bash
    sudo bash scripts/install/install_server.sh
    ```

4.  **安装客户端 (Termux)**

    在 Android 设备的 Termux 中运行以下命令：

    ```bash
    bash <(curl -s https://cdn.jsdelivr.net/gh/unal-ai/PhoneAgent@main/client/install_termux.sh)
    ```

5.  **启动前端**

    ```bash
    cd web
    npm install && npm run dev -- --host 0.0.0.0
    ```

    通过浏览器访问 `http://SERVER_IP:5173`。

详细部署说明请参考 [部署指南](docs/DEPLOYMENT.md)。

## 系统架构

PhoneAgent 采用双 WebSocket 架构：

-   **API 服务器 (端口 8000)**: 处理 REST API、前端 WebSocket 和 Scrcpy 视频流。
-   **WebSocket 服务器 (端口 9999)**: 管理设备连接和状态同步。
-   **FRP 服务器 (端口 7000)**: 提供设备内网穿透服务。

## 开源协议

本项目采用 **AGPL-3.0 许可证**。

项目基于 [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM) 开发（Apache 2.0 协议）。

我们推崇开源精神。您可以自由使用、修改和分发本软件。如果您将修改后的版本作为网络服务部署，需要向社区公开您的源代码。

详见 [LICENSE](LICENSE) 和 [第三方许可证声明](LICENSES_THIRD_PARTY.md)。

## 致谢

-   **Open-AutoGLM**: 本项目的核心基础。
-   **智谱 AI**: 提供底层 AI 模型支持。
-   **Scrcpy**: 高性能屏幕镜像方案。
-   **FRP**: 高性能反向代理。
-   **YADB**: Android 调试桥增强工具。
