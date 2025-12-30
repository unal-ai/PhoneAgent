"""
端口管理器 - 防止端口冲突
确保同一时间一个端口只能被一个设备使用
"""
import asyncio
import logging
from typing import Dict, Optional, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PortManager:
    """端口管理器 - 单例模式"""
    
    _instance: Optional['PortManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self.port_allocations: Dict[int, dict] = {}  # port -> {device_id, allocated_at, device_name}
        self.device_ports: Dict[str, int] = {}  # device_id -> port
        self._lock = asyncio.Lock()
        
        logger.info("🔒 PortManager initialized")
    
    async def allocate_port(
        self, 
        device_id: str, 
        requested_port: int,
        device_name: Optional[str] = None,
        force: bool = False
    ) -> tuple[bool, str]:
        """
        分配端口
        
        Args:
            device_id: 设备ID
            requested_port: 请求的端口
            device_name: 设备名称（可选）
            force: 是否强制分配（踢掉已占用的设备）
        
        Returns:
            (success, message)
        """
        async with self._lock:
            # 检查设备是否已有端口
            if device_id in self.device_ports:
                old_port = self.device_ports[device_id]
                if old_port == requested_port:
                    logger.info(f"Device {device_id} already owns port {requested_port}")
                    return True, f"Port {requested_port} already allocated to this device"
                else:
                    # 设备重新连接，释放旧端口
                    logger.info(f"🔄 Device {device_id} switching from port {old_port} to {requested_port}")
                    await self._release_port_internal(old_port)
            
            # 检查端口是否被占用
            if requested_port in self.port_allocations:
                existing = self.port_allocations[requested_port]
                existing_device = existing['device_id']
                
                if force:
                    # 强制分配，踢掉原设备
                    logger.warning(f" Force allocating port {requested_port}: kicking out device {existing_device}")
                    await self._release_port_internal(requested_port)
                else:
                    # 拒绝分配
                    allocated_at = existing['allocated_at']
                    elapsed = (datetime.now() - allocated_at).total_seconds()
                    logger.warning(
                        f"Port {requested_port} is occupied by device {existing_device} "
                        f"(allocated {elapsed:.0f}s ago)"
                    )
                    return False, (
                        f"Port {requested_port} is already occupied by device {existing_device}. "
                        f"Use force=True to kick out the existing device."
                    )
            
            # 分配端口
            self.port_allocations[requested_port] = {
                'device_id': device_id,
                'device_name': device_name or device_id,
                'allocated_at': datetime.now()
            }
            self.device_ports[device_id] = requested_port
            
            logger.info(f"Allocated port {requested_port} to device {device_id} ({device_name})")
            return True, f"Port {requested_port} successfully allocated"
    
    async def release_port(self, device_id: Optional[str] = None, port: Optional[int] = None) -> bool:
        """
        释放端口
        
        Args:
            device_id: 设备ID（device_id或port必须提供一个）
            port: 端口号
        
        Returns:
            是否成功释放
        """
        async with self._lock:
            if device_id:
                if device_id not in self.device_ports:
                    logger.debug(f"Device {device_id} has no allocated port")
                    return False
                
                port = self.device_ports[device_id]
                return await self._release_port_internal(port)
            
            elif port:
                return await self._release_port_internal(port)
            
            else:
                logger.error("Must provide either device_id or port")
                return False
    
    async def _release_port_internal(self, port: int) -> bool:
        """内部释放端口方法（不加锁）"""
        if port in self.port_allocations:
            allocation = self.port_allocations[port]
            device_id = allocation['device_id']
            
            del self.port_allocations[port]
            
            if device_id in self.device_ports:
                del self.device_ports[device_id]
            
            logger.info(f"🔓 Released port {port} (was allocated to device {device_id})")
            return True
        
        return False
    
    async def get_port_status(self, port: int) -> Optional[dict]:
        """获取端口状态"""
        async with self._lock:
            return self.port_allocations.get(port)
    
    async def get_device_port(self, device_id: str) -> Optional[int]:
        """获取设备的端口"""
        async with self._lock:
            return self.device_ports.get(device_id)
    
    async def list_allocations(self) -> Dict[int, dict]:
        """列出所有端口分配"""
        async with self._lock:
            return self.port_allocations.copy()
    
    async def find_available_port(self, start: int = 6100, end: int = 6199) -> Optional[int]:
        """查找可用端口"""
        async with self._lock:
            for port in range(start, end + 1):
                if port not in self.port_allocations:
                    return port
            return None
    
    async def cleanup_stale_allocations(self, max_age_seconds: int = 3600):
        """清理超时的端口分配（超过1小时未活动）"""
        async with self._lock:
            now = datetime.now()
            stale_ports = []
            
            for port, allocation in self.port_allocations.items():
                allocated_at = allocation['allocated_at']
                age = (now - allocated_at).total_seconds()
                
                if age > max_age_seconds:
                    stale_ports.append(port)
            
            for port in stale_ports:
                await self._release_port_internal(port)
                logger.warning(f"🧹 Cleaned up stale port allocation: {port}")
            
            if stale_ports:
                logger.info(f"🧹 Cleaned up {len(stale_ports)} stale port allocations")


# 全局单例
_port_manager: Optional[PortManager] = None


def get_port_manager() -> PortManager:
    """获取端口管理器单例"""
    global _port_manager
    if _port_manager is None:
        _port_manager = PortManager()
    return _port_manager

