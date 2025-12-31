#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""
设备初始化模块

在设备首次连接或重新连接时执行初始化任务：
- 推送 yadb 工具
- 设置屏幕常亮（可选）
- 其他初始化操作
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def initialize_device(
    device_id: str,
    adb_host: str = "localhost",
    adb_port: int = None,
    push_yadb: bool = True,
    **kwargs,
) -> bool:
    """
    初始化设备（异步）

    Args:
        device_id: 设备 ID (如 device_6100)
        adb_host: ADB 服务器地址（FRP 隧道）
        adb_port: ADB 服务器端口（FRP 端口）
        push_yadb: 是否推送 yadb 工具
        **kwargs: 其他初始化选项

    Returns:
        True if initialization successful, False otherwise
    """
    logger.info(f"🔧 Initializing device {device_id}...")

    success = True

    # 1. 推送 yadb 工具
    if push_yadb:
        yadb_success = await _init_yadb(device_id, adb_host, adb_port)
        if yadb_success:
            logger.info(f"  yadb ready on {device_id}")
        else:
            logger.warning(f"   yadb installation failed on {device_id}")
            success = False

    # 2. 其他初始化任务（未来扩展）
    # - 设置屏幕常亮
    # - 禁用自动锁屏
    # - 设置系统语言

    if success:
        logger.info(f"Device {device_id} initialized successfully")
    else:
        logger.warning(f" Device {device_id} initialization completed with warnings")

    return success


async def _init_yadb(device_id: str, adb_host: str, adb_port: int) -> bool:
    """
    初始化 yadb（在线程中执行以避免阻塞）

    Args:
        device_id: 设备 ID
        adb_host: ADB 服务器地址
        adb_port: ADB 服务器端口

    Returns:
        True if yadb is ready, False otherwise
    """
    try:
        from phone_agent.adb import yadb

        # 在线程中执行（避免阻塞事件循环）
        result = await asyncio.to_thread(
            yadb.ensure_yadb_ready, device_id=device_id, adb_host=adb_host, adb_port=adb_port
        )

        return result

    except ImportError:
        logger.error("yadb module not available")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize yadb: {e}")
        return False


def initialize_device_sync(
    device_id: str,
    adb_host: str = "localhost",
    adb_port: int = None,
    push_yadb: bool = True,
    **kwargs,
) -> bool:
    """
    初始化设备（同步版本，用于非异步环境）

    Args:
        device_id: 设备 ID
        adb_host: ADB 服务器地址
        adb_port: ADB 服务器端口
        push_yadb: 是否推送 yadb 工具
        **kwargs: 其他初始化选项

    Returns:
        True if initialization successful, False otherwise
    """
    logger.info(f"🔧 Initializing device {device_id} (sync mode)...")

    success = True

    # 1. 推送 yadb 工具
    if push_yadb:
        try:
            from phone_agent.adb import yadb

            yadb_success = yadb.ensure_yadb_ready(
                device_id=device_id, adb_host=adb_host, adb_port=adb_port
            )

            if yadb_success:
                logger.info(f"  yadb ready on {device_id}")
            else:
                logger.warning(f"   yadb installation failed on {device_id}")
                success = False

        except ImportError:
            logger.error("yadb module not available")
            success = False
        except Exception as e:
            logger.error(f"Failed to initialize yadb: {e}")
            success = False

    if success:
        logger.info(f"Device {device_id} initialized successfully")
    else:
        logger.warning(f" Device {device_id} initialization completed with warnings")

    return success
