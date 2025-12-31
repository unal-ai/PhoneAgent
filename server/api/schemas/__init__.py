"""
API Schemas - Pydantic 数据模型
用于定义 API 请求和响应的数据结构
"""

from server.api.schemas.device import DeviceResponse
from server.api.schemas.task import CreateTaskRequest, TaskResponse

__all__ = [
    "CreateTaskRequest",
    "TaskResponse",
    "DeviceResponse",
]
