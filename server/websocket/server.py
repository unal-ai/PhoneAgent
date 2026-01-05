#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""
WebSocket Server for Device Communication
设备通信 WebSocket 服务器 - 实时控制和监控通道
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Set

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """设备信息"""

    device_id: str
    device_name: str
    model: str
    android_version: str
    screen_resolution: str
    frp_port: int
    connected_at: datetime
    last_heartbeat: datetime
    status: str = "online"  # online, offline, busy
    battery: int = 100
    network: str = "unknown"
    frp_connected: bool = False
    ws_connected: bool = False  # WebSocket连接状态


class DeviceManager:
    """设备连接管理器"""

    def __init__(self):
        # WebSocket 连接: device_id -> WebSocket
        self.connections: Dict[str, WebSocket] = {}

        # 设备信息: device_id -> DeviceInfo
        self.devices: Dict[str, DeviceInfo] = {}

        # 任务分配: device_id -> Set[task_id]
        self.device_tasks: Dict[str, Set[str]] = {}

        self._lock = asyncio.Lock()

    async def _is_frp_port_listening(self, frp_port: int) -> bool:
        """异步检查 FRP 端口是否在监听，避免阻塞事件循环"""

        def _check_port():
            try:
                result = subprocess.run(
                    ["netstat", "-tln"], capture_output=True, text=True, timeout=1
                )
                if f":{frp_port}" in result.stdout:
                    logger.info(f"FRP port {frp_port} is listening")
                    return True
            except Exception as e:
                logger.warning(f"Failed to check FRP status: {e}")
            return False

        return await asyncio.to_thread(_check_port)

    async def register_device(self, device_id: str, websocket: WebSocket, info: dict):
        """注册设备并初始化"""
        frp_connected = False
        frp_port = info.get("frp_port", 0)
        if frp_port:
            frp_connected = await self._is_frp_port_listening(frp_port)

        async with self._lock:
            self.connections[device_id] = websocket

            # 如果设备已存在（重新连接），更新状态而不是创建新对象
            if device_id in self.devices:
                # 设备重连，更新状态
                device = self.devices[device_id]
                device.connected_at = datetime.now(timezone.utc)
                device.last_heartbeat = datetime.now(timezone.utc)
                device.status = "online"  # ← 关键：重连时设置为online
                device.frp_connected = frp_connected
                device.ws_connected = True  # WebSocket已连接
                device.battery = info.get("battery", device.battery)
                device.network = info.get("network", device.network)
                logger.info(
                    f"Device reconnected: {device_id}, status set to online, FRP: {frp_connected}"
                )

                # 设备重连时也执行初始化（确保 yadb 等工具就绪）
                if frp_connected and frp_port:
                    asyncio.create_task(self._initialize_device_background(device_id, frp_port))
            else:
                # 新设备注册
                self.devices[device_id] = DeviceInfo(
                    device_id=device_id,
                    device_name=info.get("device_name", device_id),
                    model=info.get("model", "unknown"),
                    android_version=info.get("android_version", "unknown"),
                    screen_resolution=info.get("screen_resolution", "unknown"),
                    frp_port=frp_port,
                    connected_at=datetime.now(timezone.utc),
                    last_heartbeat=datetime.now(timezone.utc),
                    status="online",  # ← 新设备也是online
                    battery=info.get("battery", 100),
                    network=info.get("network", "unknown"),
                    frp_connected=frp_connected,
                    ws_connected=True,  # WebSocket已连接
                )
                logger.info(
                    f"Device registered: {device_id} ({self.devices[device_id].device_name}), FRP: {frp_connected}"
                )

                # 新设备注册时执行初始化
                if frp_connected and frp_port:
                    asyncio.create_task(self._initialize_device_background(device_id, frp_port))

            # 初始化任务集合
            if device_id not in self.device_tasks:
                self.device_tasks[device_id] = set()

    async def _initialize_device_background(self, device_id: str, frp_port: int):
        """
        后台初始化设备（异步任务）

        在设备注册后立即执行：
        - 推送 yadb 工具到设备
        - 其他初始化操作
        """
        try:
            from phone_agent.core.device_init import initialize_device

            logger.info(f"⏳ Starting background initialization for {device_id}...")

            success = await initialize_device(
                device_id=device_id,
                adb_host="localhost",
                adb_port=frp_port,
                push_yadb=True,  # 自动推送 yadb
            )

            if success:
                logger.info(f"Background initialization completed for {device_id}")
            else:
                logger.warning(f" Background initialization had warnings for {device_id}")

        except Exception as e:
            logger.error(f"Background initialization failed for {device_id}: {e}", exc_info=True)

    async def unregister_device(self, device_id: str):
        """注销设备"""
        async with self._lock:
            if device_id in self.connections:
                del self.connections[device_id]

            if device_id in self.devices:
                self.devices[device_id].status = "offline"
                self.devices[device_id].ws_connected = False  # WebSocket已断开
                logger.info(f"Device unregistered: {device_id}")

            # 清理任务分配
            if device_id in self.device_tasks:
                del self.device_tasks[device_id]

    async def send_command(self, device_id: str, command: dict):
        """向设备发送命令"""
        if device_id not in self.connections:
            logger.warning(f"Device not connected: {device_id}")
            return False

        try:
            websocket = self.connections[device_id]
            await websocket.send_json(command)
            logger.info(f"Command sent to {device_id}: {command['type']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send command to {device_id}: {e}")
            return False

    async def broadcast(self, message: dict, exclude: Set[str] = None):
        """广播消息"""
        exclude = exclude or set()
        tasks = []

        for device_id, websocket in self.connections.items():
            if device_id not in exclude:
                tasks.append(websocket.send_json(message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_device_info(self, device_id: str) -> Optional[DeviceInfo]:
        """获取设备信息"""
        return self.devices.get(device_id)

    def list_devices(self, status: Optional[str] = None) -> list:
        """列出设备"""
        devices = list(self.devices.values())

        if status:
            devices = [d for d in devices if d.status == status]

        return devices

    def get_available_device(self) -> Optional[DeviceInfo]:
        """获取可用设备"""
        for device in self.devices.values():
            if device.status == "online" and device.frp_connected:
                # 检查是否空闲（没有任务）
                if len(self.device_tasks.get(device.device_id, set())) == 0:
                    return device
        return None

    async def assign_task(self, device_id: str, task_id: str):
        """分配任务"""
        async with self._lock:
            if device_id in self.device_tasks:
                self.device_tasks[device_id].add(task_id)
                self.devices[device_id].status = "busy"

    async def complete_task(self, device_id: str, task_id: str):
        """完成任务"""
        async with self._lock:
            if device_id in self.device_tasks:
                self.device_tasks[device_id].discard(task_id)

                # 如果没有任务了，标记为在线
                if len(self.device_tasks[device_id]) == 0:
                    self.devices[device_id].status = "online"


# 创建全局设备管理器
device_manager = DeviceManager()


def get_device_manager() -> DeviceManager:
    """获取设备管理器单例（供其他模块使用）"""
    return device_manager


# 创建 FastAPI 应用
app = FastAPI(title="PhoneAgent WebSocket Server", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/device/{frp_port}")
async def device_websocket(websocket: WebSocket, frp_port: int):
    """
    设备 WebSocket 连接端点

    使用 frp_port 作为唯一标识，确保与 FRP 扫描器同步
    """

    await websocket.accept()
    logger.info(f"WebSocket connection established: frp_port={frp_port}")

    try:
        # 等待设备上线消息
        data = await websocket.receive_json()

        if data.get("type") != "device_online":
            logger.warning(f"Invalid first message from port {frp_port}: {data}")
            await websocket.close(code=1008, reason="Invalid first message")
            return

        # 从 specs 中获取设备信息
        specs = data.get("specs", {})
        # 确保 frp_port 一致
        specs["frp_port"] = frp_port
        # 统一 device_id 格式：device_{frp_port}
        device_id = f"device_{frp_port}"
        specs["device_id"] = device_id

        # 注册设备
        await device_manager.register_device(device_id=device_id, websocket=websocket, info=specs)

        # 发送确认消息
        await websocket.send_json(
            {
                "type": "registered",
                "device_id": device_id,
                "frp_port": frp_port,
                "message": "Device registered successfully",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        logger.info(
            f"Device registered: {device_id} (port: {frp_port}, name: {specs.get('device_name', 'unknown')})"
        )

        # 消息循环（V2: 移除了心跳处理，只处理任务相关消息）
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            # 处理不同类型的消息
            if message_type == "task_progress":
                # 转发任务进度（给 API 服务器）
                logger.info(f"Task progress from {device_id} (port: {frp_port}): {data}")
                # TODO: 推送到任务管理系统

            elif message_type == "log":
                # 记录设备日志
                logger.info(f"[{device_id}] {data.get('message')}")

            elif message_type == "task_complete":
                # 任务完成
                task_id = data.get("task_id")
                await device_manager.complete_task(device_id, task_id)
                logger.info(f"Task {task_id} completed on {device_id} (port: {frp_port})")

            else:
                logger.warning(f"Unknown message type from {device_id}: {message_type}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {device_id} (port: {frp_port})")

    except Exception as e:
        logger.error(f"WebSocket error for {device_id}: {e}")

    finally:
        await device_manager.unregister_device(device_id)


@app.get("/")
async def root():
    """根路径"""
    return {"service": "PhoneAgent WebSocket Server", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "connected_devices": len(device_manager.connections),
        "online_devices": len([d for d in device_manager.devices.values() if d.status == "online"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/devices")
async def get_devices():
    """获取WebSocket连接的设备列表"""
    devices = []

    for device_id, device_info in device_manager.devices.items():
        device_data = {
            "device_id": device_info.device_id,
            "device_name": device_info.device_name,
            "model": device_info.model,
            "android_version": device_info.android_version,
            "screen_resolution": device_info.screen_resolution,
            "battery": device_info.battery,
            "network": device_info.network,
            "status": device_info.status,
            "frp_connected": device_info.frp_connected,
            "ws_connected": device_info.ws_connected,
            "connected_at": (
                device_info.connected_at.isoformat() if device_info.connected_at else None
            ),
            "last_heartbeat": (
                device_info.last_heartbeat.isoformat() if device_info.last_heartbeat else None
            ),
            "frp_port": device_info.frp_port,
        }
        devices.append(device_data)

    return {
        "devices": devices,
        "count": len(devices),
        "connected_count": len(device_manager.connections),
    }


@app.get("/devices/{device_id}")
async def get_device(device_id: str):
    """获取特定设备的详细信息"""
    if device_id not in device_manager.devices:
        raise HTTPException(status_code=404, detail="Device not found")

    device_info = device_manager.devices[device_id]
    is_connected = device_id in device_manager.connections

    return {
        "device_id": device_info.device_id,
        "device_name": device_info.device_name,
        "model": device_info.model,
        "android_version": device_info.android_version,
        "screen_resolution": device_info.screen_resolution,
        "battery": device_info.battery,
        "network": device_info.network,
        "status": device_info.status,
        "frp_connected": device_info.frp_connected,
        "ws_connected": device_info.ws_connected,
        "is_connected": is_connected,
        "connected_at": device_info.connected_at.isoformat() if device_info.connected_at else None,
        "last_heartbeat": (
            device_info.last_heartbeat.isoformat() if device_info.last_heartbeat else None
        ),
        "frp_port": device_info.frp_port,
        "current_tasks": len(device_manager.device_tasks.get(device_id, set())),
    }


@app.post("/devices/{device_id}/command")
async def send_command(device_id: str, command: dict):
    """向设备发送命令"""
    success = await device_manager.send_command(device_id, command)
    if success:
        return {"status": "sent", "device_id": device_id}
    raise HTTPException(status_code=500, detail="Failed to send command")


@app.post("/broadcast")
async def broadcast_message(message: dict):
    """广播消息"""
    await device_manager.broadcast(message)
    return {"status": "broadcasted", "recipients": len(device_manager.connections)}


@app.get("/connections")
async def get_connections():
    """获取当前WebSocket连接状态"""
    connections = {}

    for device_id, websocket in device_manager.connections.items():
        connections[device_id] = {
            "connected": True,
            "connection_time": "unknown",  # WebSocket对象没有连接时间信息
        }

    return {"connections": connections, "count": len(connections)}


async def auto_connect_devices():
    """服务启动时自动连接已知设备"""
    logger.info("开始自动连接ADB设备...")

    # 扫描 FRP 端口 6100-6110
    connected_count = 0
    for port in range(6100, 6111):
        try:
            # 检查端口是否有FRP监听
            result = subprocess.run(["netstat", "-tlnp"], capture_output=True, text=True, timeout=2)

            if f":{port}" in result.stdout:
                # 尝试连接
                device_addr = f"localhost:{port}"
                logger.info(f"尝试连接设备: {device_addr}")

                connect_result = subprocess.run(
                    ["adb", "connect", device_addr], capture_output=True, text=True, timeout=5
                )

                output = connect_result.stdout.lower()
                if "connected" in output or "already connected" in output:
                    logger.info(f"设备连接成功: {device_addr}")
                    connected_count += 1
                else:
                    logger.warning(f"设备连接失败: {device_addr} - {connect_result.stdout}")

        except Exception as e:
            logger.debug(f"端口 {port} 检查失败: {e}")
            continue

    if connected_count > 0:
        logger.info(f"自动连接了 {connected_count} 个设备")
    else:
        logger.info("没有检测到可连接的设备")


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    # V2: 不再需要心跳超时检测，WebSocket 使用原生 ping/pong 机制
    logger.info("WebSocket 服务器启动完成（使用原生 ping/pong 机制，ping_interval=30s）")


if __name__ == "__main__":
    import asyncio

    # 启动时自动连接设备
    try:
        asyncio.run(auto_connect_devices())
    except Exception as e:
        logger.error(f"自动连接设备失败: {e}")

    # 启动服务器
    uvicorn.run(app, host="0.0.0.0", port=9999, log_level="info", access_log=True)
