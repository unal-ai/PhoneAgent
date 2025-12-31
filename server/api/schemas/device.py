"""
设备相关的 API 数据模型
"""

from typing import Optional

from pydantic import BaseModel


class DeviceResponse(BaseModel):
    """设备响应"""

    device_id: str
    device_name: str
    frp_port: int
    adb_address: str
    status: str
    frp_connected: bool
    ws_connected: bool
    current_task: Optional[str]
    model: str
    android_version: str
    screen_resolution: str
    battery: int
    total_tasks: int
    success_tasks: int
    failed_tasks: int
    success_rate: float
    registered_at: str
    last_active: str
