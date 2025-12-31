"""
WebSocket 连接管理器 - 用于 API 层的实时通信

提供全局的 WebSocket 连接管理和广播功能
"""

import logging
from typing import List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected: {websocket.client}")

    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        if not self.active_connections:
            logger.debug("No active WebSocket connections to broadcast to")
            return

        logger.info(
            f"📡 Broadcasting to {len(self.active_connections)} connections: type={message.get('type')}"
        )

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error to {connection.client}: {e}")


# 全局单例
_connection_manager = None


def get_connection_manager() -> ConnectionManager:
    """获取 WebSocket 连接管理器单例"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
