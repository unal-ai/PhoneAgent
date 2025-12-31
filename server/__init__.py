#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""
PhoneAgent Server - Web API and Device Management

Enterprise-grade web service layer providing:
- REST API for task and device management
- WebSocket server for real-time device communication
- Device pool management with health monitoring
- AI-powered task execution service

Architecture:
- api/: FastAPI REST endpoints
- core/: Core services (AgentService, DevicePool)
- ws/: WebSocket server for device connections
- models/: Data models and database
- utils/: Utility functions
"""

__version__ = "1.0.0"

# Services exports
from server.config import Config
from server.services.agent_service import AgentService, get_agent_service
from server.services.device_pool import Device, DevicePool, get_device_pool

__all__ = [
    "AgentService",
    "DevicePool",
    "Device",
    "Config",
    "get_agent_service",
    "get_device_pool",
    "__version__",
]
