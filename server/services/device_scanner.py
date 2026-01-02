"""
设备扫描服务 - 修复版
核心修复：
1. 使用ADB序列号作为唯一device_id
2. 支持设备名称自定义
3. 端口管理集成
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Set

from server.services.port_manager import get_port_manager

logger = logging.getLogger(__name__)


@dataclass
class ScannedDevice:
    """扫描到的设备信息"""

    device_id: str  # 唯一标识（基于ADB序列号生成）
    device_name: str  # 用户自定义名称
    frp_port: int
    adb_address: str
    adb_serial: str  # ADB原始序列号
    discovered_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    is_online: bool = True

    # 设备规格
    model: Optional[str] = None
    android_version: Optional[str] = None
    screen_resolution: Optional[str] = None
    battery: Optional[int] = None
    memory_total: Optional[str] = None
    memory_available: Optional[str] = None
    storage_total: Optional[str] = None
    storage_available: Optional[str] = None


class DeviceScanner:
    """设备扫描器 - 主动发现在线设备"""

    def __init__(self, port_range_start: int = 6100, port_range_end: int = 6199):
        self.port_range_start = port_range_start
        self.port_range_end = port_range_end

        # 已发现的设备 {device_id: ScannedDevice}
        self.devices: Dict[str, ScannedDevice] = {}

        # 端口到设备ID的映射 {port: device_id}
        self.port_to_device: Dict[int, str] = {}

        # 扫描任务
        self.scan_task: Optional[asyncio.Task] = None
        self.is_running = False

        # 扫描间隔
        self.scan_interval = 10  # 每10秒扫描一次

        logger.info(f"[DeviceScanner] 初始化完成，端口范围: {port_range_start}-{port_range_end}")

    def generate_device_id(self, frp_port: int) -> str:
        """
        基于 FRP 端口生成唯一的 device_id

        使用 frp_port 作为唯一标识，确保与 WebSocket 客户端同步
        格式：device_{frp_port}

        Args:
            frp_port: FRP 远程端口（如 6100）

        Returns:
            device_id: 如 "device_6100"
        """
        return f"device_{frp_port}"

    async def check_port_listening(self, port: int) -> bool:
        """检查端口是否有进程监听（跨平台支持）"""
        import platform

        try:
            if platform.system() == "Darwin":  # macOS
                # macOS 使用 lsof
                result = subprocess.run(
                    ["lsof", "-i", f":{port}", "-sTCP:LISTEN"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                return bool(result.stdout.strip())
            else:  # Linux
                result = subprocess.run(
                    ["netstat", "-tlnp"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                for line in result.stdout.split("\n"):
                    if f":{port}" in line and "LISTEN" in line:
                        return True
                return False

        except Exception as e:
            logger.debug(f"[DeviceScanner] 检查端口{port}失败: {e}")
            return False

    async def try_adb_connect(self, port: int) -> Optional[str]:
        """
        尝试通过ADB连接设备

        Returns:
            ADB序列号（如 "localhost:6100"）或 None
        """
        adb_address = f"localhost:{port}"

        try:
            # 尝试连接
            result = subprocess.run(
                ["adb", "connect", adb_address], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                # 验证连接
                result = subprocess.run(
                    ["adb", "-s", adb_address, "shell", "echo", "test"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )

                if result.returncode == 0 and "test" in result.stdout:
                    logger.debug(f"[DeviceScanner] ADB连接成功: {adb_address}")
                    return adb_address

            return None

        except Exception as e:
            logger.debug(f"[DeviceScanner] ADB连接失败 {adb_address}: {e}")
            return None

    async def get_device_specs(self, adb_address: str) -> dict:
        """获取设备规格信息"""
        specs = {
            "model": None,
            "android_version": None,
            "screen_resolution": None,
            "battery": None,
            "memory_total": None,
            "memory_available": None,
            "storage_total": None,
            "storage_available": None,
        }

        try:
            # 获取型号
            result = subprocess.run(
                ["adb", "-s", adb_address, "shell", "getprop", "ro.product.model"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                specs["model"] = result.stdout.strip()

            # 获取Android版本
            result = subprocess.run(
                ["adb", "-s", adb_address, "shell", "getprop", "ro.build.version.release"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                specs["android_version"] = result.stdout.strip()

            # 获取屏幕分辨率
            result = subprocess.run(
                ["adb", "-s", adb_address, "shell", "wm", "size"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and ":" in result.stdout:
                resolution = result.stdout.split(":")[-1].strip()
                if resolution:
                    specs["screen_resolution"] = resolution

            # 获取电池电量
            result = subprocess.run(
                ["adb", "-s", adb_address, "shell", "dumpsys", "battery"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "level:" in line:
                        try:
                            specs["battery"] = int(line.split(":")[1].strip())
                        except:
                            pass
                        break

            # 获取内存信息
            result = subprocess.run(
                ["adb", "-s", adb_address, "shell", "cat", "/proc/meminfo"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "MemTotal:" in line:
                        try:
                            kb = int(line.split()[1])
                            gb = round(kb / 1024 / 1024, 1)
                            specs["memory_total"] = f"{gb}GB"
                        except:
                            pass
                    elif "MemAvailable:" in line:
                        try:
                            kb = int(line.split()[1])
                            gb = round(kb / 1024 / 1024, 1)
                            specs["memory_available"] = f"{gb}GB"
                        except:
                            pass

            # 获取存储信息
            result = subprocess.run(
                ["adb", "-s", adb_address, "shell", "df", "/data"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 4:
                        try:
                            total_kb = int(parts[1].replace("K", ""))
                            used_kb = int(parts[2].replace("K", ""))
                            avail_kb = int(parts[3].replace("K", ""))

                            total_gb = round(total_kb / 1024 / 1024, 1)
                            avail_gb = round(avail_kb / 1024 / 1024, 1)

                            specs["storage_total"] = f"{total_gb}GB"
                            specs["storage_available"] = f"{avail_gb}GB"
                        except:
                            pass

        except Exception as e:
            logger.warning(f"[DeviceScanner] 获取设备规格失败 {adb_address}: {e}")

        return specs

    def get_default_device_name(self, device_id: str, model: Optional[str], port: int) -> str:
        """
        生成默认设备名称

        格式：型号-端口 或 device-端口
        """
        if model:
            # 清理型号名称
            clean_model = model.replace(" ", "-")
            return f"{clean_model}-{port}"
        else:
            return f"device-{port}"

    async def scan_once(self):
        """执行一次完整扫描（并发优化版本）"""
        logger.info(
            f"[DeviceScanner] 开始扫描端口 {self.port_range_start}-{self.port_range_end}..."
        )

        found_devices: Set[str] = set()
        port_manager = get_port_manager()

        # 并发扫描所有端口（每次10个并发）
        async def scan_port(port: int):
            """扫描单个端口"""
            try:
                # 检查端口是否监听
                if not await self.check_port_listening(port):
                    return None

                # 尝试ADB连接
                adb_serial = await self.try_adb_connect(port)
                if not adb_serial:
                    return None

                # 生成唯一device_id（基于frp_port，确保与WebSocket客户端同步）
                device_id = self.generate_device_id(port)
                return (port, device_id, adb_serial)
            except Exception as e:
                logger.debug(f"[DeviceScanner] 扫描端口{port}失败: {e}")
                return None

        # 分批并发扫描（每批10个端口）
        batch_size = 10
        ports = list(range(self.port_range_start, self.port_range_end + 1))

        for i in range(0, len(ports), batch_size):
            batch = ports[i : i + batch_size]
            results = await asyncio.gather(*[scan_port(port) for port in batch])

            # 处理结果
            for result in results:
                if result is None:
                    continue

                port, device_id, adb_serial = result
                found_devices.add(device_id)

                logger.info(
                    f"[DeviceScanner] 发现设备: port={port}, serial={adb_serial}, id={device_id}"
                )

                # 检查是否是新设备
                if device_id not in self.devices:
                    # 尝试分配端口
                    success, message = await port_manager.allocate_port(
                        device_id=device_id,
                        requested_port=port,
                        device_name=device_id,  # 临时使用device_id作为名称
                        force=False,
                    )

                    if not success:
                        logger.error(f"[DeviceScanner] 端口{port}分配失败: {message}")
                        logger.error(f"[DeviceScanner] 设备{device_id}无法上线")

                        # 断开ADB连接
                        try:
                            subprocess.run(
                                ["adb", "disconnect", adb_serial], capture_output=True, timeout=2
                            )
                            logger.info(f"[DeviceScanner] 🔌 已断开冲突设备: {adb_serial}")
                        except:
                            pass

                        continue

                    logger.info(f"[DeviceScanner] 端口{port}已分配给设备{device_id}")

                    # 获取设备规格
                    specs = await self.get_device_specs(adb_serial)

                    # 生成默认设备名称
                    default_name = self.get_default_device_name(device_id, specs["model"], port)

                    # 添加新设备
                    self.devices[device_id] = ScannedDevice(
                        device_id=device_id,
                        device_name=default_name,  # 使用默认名称
                        frp_port=port,
                        adb_address=adb_serial,
                        adb_serial=adb_serial,
                        model=specs["model"],
                        android_version=specs["android_version"],
                        screen_resolution=specs["screen_resolution"],
                        battery=specs.get("battery"),
                        memory_total=specs.get("memory_total"),
                        memory_available=specs.get("memory_available"),
                        storage_total=specs.get("storage_total"),
                        storage_available=specs.get("storage_available"),
                    )

                    self.port_to_device[port] = device_id

                    logger.info(
                        f"[DeviceScanner] 🆕 新设备上线: {device_id} ({default_name}) @ {adb_serial}"
                    )
                    logger.info(
                        f"[DeviceScanner]    型号: {specs['model']}, Android: {specs['android_version']}, 电池: {specs.get('battery', 'N/A')}%"
                    )

                else:
                    # 更新已有设备
                    device = self.devices[device_id]
                    device.last_seen = datetime.now()
                    if not device.is_online:
                        device.is_online = True
                        logger.info(
                            f"[DeviceScanner] 🔄 设备重新上线: {device_id} ({device.device_name})"
                        )

        # 标记离线设备并释放端口
        for device_id, device in self.devices.items():
            if device_id not in found_devices and device.is_online:
                device.is_online = False
                # 释放端口
                await port_manager.release_port(device_id=device_id)
                if device.frp_port in self.port_to_device:
                    del self.port_to_device[device.frp_port]
                logger.info(
                    f"[DeviceScanner] 📴 设备离线: {device_id} ({device.device_name})，端口已释放"
                )

        online_count = sum(1 for d in self.devices.values() if d.is_online)
        logger.info(f"[DeviceScanner] 扫描完成，在线设备: {online_count}/{len(self.devices)}")

    async def scan_loop(self):
        """扫描循环"""
        logger.info(f"[DeviceScanner] 🔍 开始自动扫描（间隔{self.scan_interval}秒）...")

        while self.is_running:
            try:
                await self.scan_once()
                await asyncio.sleep(self.scan_interval)

            except Exception as e:
                logger.error(f"[DeviceScanner] 扫描出错: {e}", exc_info=True)
                await asyncio.sleep(self.scan_interval)

    async def start(self):
        """启动扫描服务"""
        if self.is_running:
            logger.warning("[DeviceScanner] 扫描服务已在运行")
            return

        self.is_running = True
        self.scan_task = asyncio.create_task(self.scan_loop())
        logger.info("[DeviceScanner] 扫描服务已启动")

    async def stop(self):
        """停止扫描服务"""
        if not self.is_running:
            return

        self.is_running = False

        if self.scan_task:
            self.scan_task.cancel()
            try:
                await self.scan_task
            except asyncio.CancelledError:
                pass

        logger.info("[DeviceScanner] 扫描服务已停止")

    def get_scanned_devices(self) -> Dict[str, ScannedDevice]:
        """获取所有扫描到的设备"""
        return self.devices

    def get_online_devices(self) -> Dict[str, ScannedDevice]:
        """获取在线设备"""
        return {k: v for k, v in self.devices.items() if v.is_online}

    async def update_device_name(self, device_id: str, new_name: str) -> bool:
        """
        更新设备名称

        Args:
            device_id: 设备ID
            new_name: 新名称

        Returns:
            是否成功
        """
        if device_id not in self.devices:
            return False

        old_name = self.devices[device_id].device_name
        self.devices[device_id].device_name = new_name

        logger.info(f"[DeviceScanner] ✏️  设备重命名: {device_id} '{old_name}' → '{new_name}'")
        return True


# 全局单例
_device_scanner: Optional[DeviceScanner] = None


def get_device_scanner() -> DeviceScanner:
    """获取设备扫描器单例"""
    global _device_scanner
    if _device_scanner is None:
        _device_scanner = DeviceScanner()
    return _device_scanner
