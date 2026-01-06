# PhoneAgent

PhoneAgent is a complete Android Agent solution based on Open-AutoGLM.

It enhances the original Open-AutoGLM project with a Web UI, multi-device management, and real-time screen preview capabilities, making it a production-ready infrastructure for Android automation.

## Features

- **Web Interface**: Modern Vue 3 based UI for easy interaction without writing code.
- **Multi-Device Management**: Manage multiple devices simultaneously from a single dashboard.
- **Real-time Preview**: Integrated Scrcpy for low-latency (<150ms) screen mirroring.
- **Multi-Model Support**: Supports GLM-4.6v series and any OpenAI-compatible vision models.

## Quick Start

### Requirements

- **Server**: Ubuntu 20.04+ or Debian 11+, 2 cores, 4GB RAM, Public IP.
- **Android Device**: Android 7.0+, USB debugging enabled.

### Deployment

1.  **Clone Repository**

    ```bash
    git clone https://github.com/unal-ai/PhoneAgent.git
    cd PhoneAgent
    ```

2.  **Configure Environment**

    ```bash
    cp env.example .env
    # Edit .env and fill in ZHIPU_API_KEY
    ```

3.  **Install Server**

    ```bash
    sudo bash scripts/install/install_server.sh
    ```

4.  **Install Client (Termux)**

    Run this command in Termux on your Android device:

    ```bash
    bash <(curl -s https://cdn.jsdelivr.net/gh/unal-ai/PhoneAgent@main/client/install_termux.sh)
    ```

5.  **Start Frontend**

    ```bash
    cd web
    npm install && npm run dev -- --host 0.0.0.0
    ```

    Access via `http://SERVER_IP:5173`.

For detailed instructions, refer to the [Deployment Guide](docs/DEPLOYMENT.md).

## Architecture

PhoneAgent employs a dual WebSocket architecture:

-   **API Server (Port 8000)**: Handles REST API, frontend WebSocket, and Scrcpy video streams.
-   **WebSocket Server (Port 9999)**: Manages device connections and state synchronization.
-   **FRP Server (Port 7000)**: Provides NAT traversal for devices.

## License

This project is licensed under the **AGPL-3.0 License**.

It is based on [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM), which is licensed under Apache 2.0.

We believe in the spirit of open source. You are free to use, modify, and distribute this software. If you deploy a modified version as a network service, you are required to make your source code available to the community.

See [LICENSE](LICENSE) and [Third-Party Licenses](LICENSES_THIRD_PARTY.md) for full details.

## Acknowledgements

-   **Open-AutoGLM**: The core foundation of this project.
-   **Zhipu AI**: Provider of the underlying AI models.
-   **Scrcpy**: High-performance screen mirroring solution.
-   **FRP**: Fast reverse proxy.
-   **YADB**: Android debugging bridge enhancement.
