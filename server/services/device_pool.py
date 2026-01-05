#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""
DevicePool - 设备池管理

职责：
1. 设备注册和发现
2. FRP + WebSocket 双通道管理
3. 健康检查和心跳监控
4. 负载均衡（选择空闲设备）
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class DeviceStatus(Enum):
    """设备状态"""

    OFFLINE = "offline"  # 离线
    ONLINE = "online"  # 在线空闲
    BUSY = "busy"  # 执行任务中
    ERROR = "error"  # 错误状态


@dataclass
class Device:
    """
    设备信息

    双通道设计:
    - FRP 通道: ADB 数据传输（截图、操作）
    - WebSocket 通道: 实时控制和监控
    """

    # 基本信息
    device_id: str  # 设备唯一 ID
    device_name: str  # 设备名称

    # FRP 通道 (ADB)
    frp_port: int  # 服务器上的 FRP 端口（如 6100）
    frp_connected: bool = False  # FRP 连接状态

    # WebSocket 通道
    ws_connected: bool = False  # WebSocket 连接状态
    ws_last_heartbeat: Optional[datetime] = None  # 最后心跳时间

    # 设备规格
    model: str = "unknown"  # 设备型号
    android_version: str = "unknown"  # Android 版本
    screen_resolution: str = "unknown"  # 屏幕分辨率
    battery: int = 100  # 电池电量

    # 状态
    status: DeviceStatus = DeviceStatus.OFFLINE  # 设备状态
    current_task: Optional[str] = None  # 当前任务 ID

    # 统计
    total_tasks: int = 0  # 总任务数
    success_tasks: int = 0  # 成功任务数
    failed_tasks: int = 0  # 失败任务数

    # 应用缓存
    installed_apps: List[str] = field(default_factory=list)  # 已安装应用列表

    # 元数据
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

    @property
    def adb_address(self) -> str:
        """ADB 连接地址"""
        return f"localhost:{self.frp_port}"

    @property
    def is_available(self) -> bool:
        """是否可用（双通道都连接 + 在线状态 + 无任务）"""
        return (
            self.frp_connected
            and self.ws_connected
            and self.status == DeviceStatus.ONLINE
            and self.current_task is None
        )

    @property
    def success_rate(self) -> float:
        """任务成功率"""
        if self.total_tasks == 0:
            return 0.0
        return self.success_tasks / self.total_tasks * 100


class DevicePool:
    """
    设备池管理器

    功能:
    1. 设备注册和管理
    2. 健康检查和心跳监控
    3. 负载均衡（选择最优设备）
    """

    # 配置常量
    HEARTBEAT_TIMEOUT_MINUTES = 2  # 心跳超时时间（分钟）

    def __init__(self, max_devices: int = 100):
        """
        初始化设备池

        Args:
            max_devices: 最大设备数量，默认支持100台设备
        """
        self.max_devices = max_devices
        self.devices: dict[str, Device] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None

    async def register_device(self, device: Device) -> bool:
        """
        注册设备

        Args:
            device: 设备对象

        Returns:
            是否注册成功
        """
        async with self._lock:
            # 检查设备数量限制
            if len(self.devices) >= self.max_devices:
                logger.error(
                    f"Device limit reached ({self.max_devices}). "
                    f"Cannot register device: {device.device_id}"
                )
                return False

            # 注册设备
            self.devices[device.device_id] = device
            logger.info(
                f"Device registered: {device.device_id} "
                f"(FRP port: {device.frp_port}, "
                f"Total: {len(self.devices)}/{self.max_devices})"
            )

            return True

    async def unregister_device(self, device_id: str) -> bool:
        """
        注销设备

        Args:
            device_id: 设备 ID

        Returns:
            是否注销成功
        """
        async with self._lock:
            if device_id in self.devices:
                del self.devices[device_id]
                logger.info(f"Device unregistered: {device_id}")
                return True
            else:
                logger.warning(f"Device not found: {device_id}")
                return False

    async def get_device(self, device_id: str) -> Optional[Device]:
        """
        获取设备（异步版本，带并发锁保护）

        从 WebSocket Server 实时查询设备信息

        🔒 并发安全：使用锁保护缓存读写，防止数据竞争

        Args:
            device_id: 设备 ID

        Returns:
            设备对象（如果不存在则返回 None）
        """
        # 🔒 加锁保护：防止并发访问导致的数据竞争
        async with self._lock:
            # 优先从本地缓存获取
            if device_id in self.devices:
                return self.devices.get(device_id)

        # 从 WebSocket Server 查询（不持有锁，避免阻塞）
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:9999/devices/{device_id}", timeout=2.0
                )
                response.raise_for_status()
                device_data = response.json()

            # 转换为 Device 对象
            if device_data and "device_id" in device_data:
                device = Device(
                    device_id=device_data["device_id"],
                    device_name=device_data["device_name"],
                    frp_port=device_data["frp_port"],
                    frp_connected=device_data.get("frp_connected", False),
                    ws_connected=True,  # 能查询到说明已连接
                    model=device_data.get("model", "unknown"),
                    android_version=device_data.get("android_version", "unknown"),
                    screen_resolution=device_data.get("screen_resolution", "unknown"),
                    battery=device_data.get("battery", 100),
                    status=(
                        DeviceStatus.ONLINE
                        if device_data.get("status") == "online"
                        else DeviceStatus.OFFLINE
                    ),
                )

                # 🔒 加锁保护：缓存更新
                async with self._lock:
                    self.devices[device_id] = device

                logger.info(f"Device {device_id} loaded from WebSocket Server")
                return device

        except Exception as e:
            logger.warning(f"Failed to query device {device_id} from WebSocket Server: {e}")

        return None

    def list_devices(self, status: Optional[DeviceStatus] = None) -> List[Device]:
        """
        列出设备

        Args:
            status: 筛选状态（可选）

        Returns:
            设备列表
        """
        devices = list(self.devices.values())

        if status:
            devices = [d for d in devices if d.status == status]

        return devices

    async def get_available_device(self) -> Optional[Device]:
        """
        获取可用设备（负载均衡）

        策略:
        1. 筛选可用设备（双通道连接 + 在线 + 无任务）
        2. 按成功率排序（优先使用稳定设备）
        3. 返回最优设备

        Returns:
            可用设备（如果没有则返回 None）
        """
        async with self._lock:
            # 筛选可用设备
            available_devices = [device for device in self.devices.values() if device.is_available]

            if not available_devices:
                logger.warning("No available devices")
                return None

            # 检查心跳是否过期
            valid_devices = []
            for device in available_devices:
                if device.ws_last_heartbeat:
                    age = datetime.utcnow() - device.ws_last_heartbeat
                    if age > timedelta(minutes=self.HEARTBEAT_TIMEOUT_MINUTES):
                        logger.warning(f"Device {device.device_id} heartbeat expired")
                        device.ws_connected = False
                        device.status = DeviceStatus.OFFLINE
                        continue

                valid_devices.append(device)

            if not valid_devices:
                logger.warning("No valid devices (heartbeat check failed)")
                return None

            # 按成功率排序（稳定性优先）
            valid_devices.sort(key=lambda d: d.success_rate, reverse=True)

            selected = valid_devices[0]
            logger.info(
                f"Selected device: {selected.device_id} "
                f"(success rate: {selected.success_rate:.1f}%)"
            )

            return selected

    async def update_device_status(
        self,
        device_id: str,
        frp_connected: Optional[bool] = None,
        ws_connected: Optional[bool] = None,
        ws_heartbeat: Optional[datetime] = None,
        battery: Optional[int] = None,
        status: Optional[DeviceStatus] = None,
    ) -> bool:
        """
        更新设备状态

        Args:
            device_id: 设备 ID
            frp_connected: FRP 连接状态
            ws_connected: WebSocket 连接状态
            ws_heartbeat: 心跳时间
            battery: 电池电量
            status: 设备状态

        Returns:
            是否更新成功
        """
        async with self._lock:
            device = self.devices.get(device_id)
            if not device:
                logger.warning(f"Device not found: {device_id}")
                return False

            # 更新字段
            if frp_connected is not None:
                device.frp_connected = frp_connected

            if ws_connected is not None:
                device.ws_connected = ws_connected

            if ws_heartbeat is not None:
                device.ws_last_heartbeat = ws_heartbeat

            if battery is not None:
                device.battery = battery

            if status is not None:
                device.status = status

            # 更新最后活跃时间
            device.last_active = datetime.utcnow()

            # 自动更新整体状态
            if device.frp_connected and device.ws_connected:
                if device.current_task is None and device.status != DeviceStatus.ERROR:
                    device.status = DeviceStatus.ONLINE
                    # 如果应用列表为空，触发一次发现
                    if not device.installed_apps:
                        asyncio.create_task(self._refresh_installed_apps(device_id))
            else:
                device.status = DeviceStatus.OFFLINE

            return True

    async def _refresh_installed_apps(self, device_id: str):
        """刷新已安装应用列表"""
        try:
            from phone_agent.adb.app_discovery import get_third_party_packages

            device = self.devices.get(device_id)
            if device:
                apps = await get_third_party_packages(device_id)
                device.installed_apps = apps
                logger.info(f"Discovered {len(apps)} apps for {device_id}")
        except Exception as e:
            logger.error(f"Failed to discover apps for {device_id}: {e}")

    async def assign_task(self, device_id: str, task_id: str) -> bool:
        """
        分配任务

        Args:
            device_id: 设备 ID
            task_id: 任务 ID

        Returns:
            是否分配成功
        """
        async with self._lock:
            device = self.devices.get(device_id)
            if not device:
                logger.warning(f"Device not found: {device_id}")
                return False

            if not device.is_available:
                logger.warning(f"Device not available: {device_id}")
                return False

            device.current_task = task_id
            device.status = DeviceStatus.BUSY
            device.total_tasks += 1
            logger.info(f"Task assigned: {task_id} -> {device_id}")

            return True

    async def complete_task(self, device_id: str, success: bool = True) -> bool:
        """
        完成任务

        Args:
            device_id: 设备 ID
            success: 任务是否成功

        Returns:
            是否操作成功
        """
        async with self._lock:
            device = self.devices.get(device_id)
            if not device:
                logger.warning(f"Device not found: {device_id}")
                return False

            task_id = device.current_task
            device.current_task = None
            device.status = DeviceStatus.ONLINE

            if success:
                device.success_tasks += 1
                logger.info(f"Task completed: {task_id} on {device_id}")
            else:
                device.failed_tasks += 1
                logger.warning(f"Task failed: {task_id} on {device_id}")

            return True

    async def check_device_health(self, device_id: str) -> bool:
        """
        检查设备健康状态

        Args:
            device_id: 设备 ID

        Returns:
            是否健康
        """
        device = self.devices.get(device_id)
        if not device:
            return False

        # 简化健康检查：只检查 WebSocket 心跳
        # FRP 连接状态由客户端上报，不在服务端主动检查
        if device.ws_last_heartbeat:
            age = datetime.utcnow() - device.ws_last_heartbeat
            if age > timedelta(minutes=self.HEARTBEAT_TIMEOUT_MINUTES):
                await self.update_device_status(device_id, ws_connected=False, status="offline")
                return False

        return device.ws_connected

    async def start_health_check(self, interval: int = 60):
        """
        启动健康检查循环

        Args:
            interval: 检查间隔（秒）
        """
        if self._health_check_task:
            logger.warning("Health check already running")
            return

        async def health_check_loop():
            logger.info(f"Health check started (interval: {interval}s)")
            while True:
                try:
                    await asyncio.sleep(interval)

                    # 检查所有设备
                    device_ids = list(self.devices.keys())
                    for device_id in device_ids:
                        await self.check_device_health(device_id)

                except Exception as e:
                    logger.error(f"Health check error: {e}")

        self._health_check_task = asyncio.create_task(health_check_loop())

    async def stop_health_check(self):
        """停止健康检查循环"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Health check stopped")

    def get_stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计数据字典
        """
        total_devices = len(self.devices)
        online_devices = len([d for d in self.devices.values() if d.status == DeviceStatus.ONLINE])
        busy_devices = len([d for d in self.devices.values() if d.status == DeviceStatus.BUSY])
        offline_devices = len(
            [d for d in self.devices.values() if d.status == DeviceStatus.OFFLINE]
        )

        total_tasks = sum(d.total_tasks for d in self.devices.values())
        success_tasks = sum(d.success_tasks for d in self.devices.values())
        failed_tasks = sum(d.failed_tasks for d in self.devices.values())

        return {
            "max_devices": self.max_devices,
            "total_devices": total_devices,
            "online_devices": online_devices,
            "busy_devices": busy_devices,
            "offline_devices": offline_devices,
            "total_tasks": total_tasks,
            "success_tasks": success_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": success_tasks / total_tasks * 100 if total_tasks > 0 else 0.0,
        }


# 全局实例
_device_pool: Optional[DevicePool] = None


def get_device_pool(max_devices: int = 1) -> DevicePool:
    """
    获取全局 DevicePool 实例

    Args:
        max_devices: 最大设备数量（首次初始化时设置）

    Returns:
        DevicePool 实例
    """
    global _device_pool
    if _device_pool is None:
        _device_pool = DevicePool(max_devices=max_devices)
    return _device_pool


if __name__ == "__main__":
    # 测试
    async def test():
        pool = DevicePool(max_devices=5)

        # 注册设备
        device1 = Device(device_id="device_1", device_name="Test Device 1", frp_port=6100)
        await pool.register_device(device1)

        device2 = Device(device_id="device_2", device_name="Test Device 2", frp_port=6101)
        await pool.register_device(device2)

        # 更新状态
        await pool.update_device_status(
            "device_1", frp_connected=True, ws_connected=True, ws_heartbeat=datetime.utcnow()
        )

        # 获取可用设备
        device = await pool.get_available_device()
        if device:
            print(f"Available device: {device.device_id}")

            # 分配任务
            await pool.assign_task(device.device_id, "task_123")

            # 完成任务
            await asyncio.sleep(1)
            await pool.complete_task(device.device_id, success=True)

        # 获取统计信息
        stats = pool.get_stats()
        print(f"Stats: {stats}")

    asyncio.run(test())

    async def get_installed_apps(self, device_id: str) -> List[dict]:
        """
        获取设备已安装的应用列表

        Args:
            device_id: 设备ID

        Returns:
            应用列表 [{"name": "WeChat", "package": "com.tencent.mm"}, ...]
        """
        device = self.get_device(device_id)
        if not device:
            return []

        try:
            # 临时构建 ApplicationScanner (因为它目前设计为独立使用)
            from phone_agent.adb.app_discovery import ApplicationScanner
            from phone_agent.adb.connection import ADBConnection

            # 使用现有设备的连接信息
            connection = ADBConnection(device.adb_address)
            scanner = ApplicationScanner(connection)

            # 获取应用列表
            apps = scanner.get_installed_apps()

            # 转换为简单字典格式
            return [{"name": app.name, "package": app.package} for app in apps]
        except Exception as e:
            logger.error(f"Failed to get installed apps for {device_id}: {e}")
            return []
