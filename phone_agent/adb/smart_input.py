#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""
智能文本输入模块 - 优先yadb，ADB Keyboard兜底

策略:
1. 优先使用yadb（支持中文，无需安装APK，速度快）
2. yadb不可用时降级到ADB Keyboard（需要安装APK）
3. 自动缓存设备的可用方案

使用方法:
    from phone_agent.adb.smart_input import smart_type_text

    success = smart_type_text("你好，世界！", device_id="localhost:6100")
"""

import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 全局缓存：记录每个设备的最佳输入方案
_device_input_methods: Dict[str, str] = {}  # device_id -> "yadb" or "adb_keyboard"


def smart_type_text(
    text: str, device_id: Optional[str] = None, force_method: Optional[str] = None
) -> bool:
    """
    智能文本输入（优先yadb，兜底ADB Keyboard）

    Args:
        text: 要输入的文本（支持中文、Emoji等）
        device_id: 设备ID
        force_method: 强制使用的方法 ("yadb" or "adb_keyboard")

    Returns:
        是否成功

    Example:
        >>> smart_type_text("你好，世界！", device_id="device_6100")
        True
    """
    device_key = device_id or "default"

    # 如果强制指定方法
    if force_method:
        return _execute_input(text, device_id, force_method)

    # 如果已知有效方法，优先使用
    if device_key in _device_input_methods:
        method = _device_input_methods[device_key]
        logger.debug(f"使用已知输入方法: {method}")

        success = _execute_input(text, device_id, method)
        if success:
            return True

        # 失败了，重新探测
        logger.warning(f"已知方法 {method} 失败，重新探测...")
        del _device_input_methods[device_key]

    # 尝试不同方法
    methods = ["yadb", "adb_keyboard"]

    for method in methods:
        logger.info(f"🔄 尝试输入方法: {method}")
        success = _execute_input(text, device_id, method)

        if success:
            # 成功！记住这个方法
            _device_input_methods[device_key] = method
            logger.info(f"{method} 成功，已缓存")
            return True

        logger.debug(f"{method} 失败，尝试下一个...")

    # 所有方法都失败
    logger.error("所有输入方法都失败")
    return False


def _execute_input(text: str, device_id: Optional[str], method: str) -> bool:
    """执行特定方法的输入"""

    if method == "yadb":
        return _try_yadb_input(text, device_id)

    elif method == "adb_keyboard":
        return _try_adb_keyboard_input(text, device_id)

    else:
        raise ValueError(f"未知输入方法: {method}")


def _try_yadb_input(text: str, device_id: Optional[str]) -> bool:
    """尝试使用yadb输入"""
    try:
        from phone_agent.adb.yadb import ensure_yadb_ready
        from phone_agent.adb.yadb import type_text as yadb_type_text

        # 确保yadb就绪
        if not ensure_yadb_ready(device_id):
            logger.debug("yadb未就绪")
            return False

        # 执行输入
        success = yadb_type_text(text, device_id)

        if success:
            logger.debug(f"yadb输入成功: {text[:30]}...")
            return True

        return False

    except ImportError:
        logger.debug("yadb模块不可用")
        return False
    except Exception as e:
        logger.debug(f"yadb输入失败: {e}")
        return False


def _try_adb_keyboard_input(text: str, device_id: Optional[str]) -> bool:
    """尝试使用ADB Keyboard输入"""
    try:
        from phone_agent.adb.input import (
            clear_text,
            detect_and_set_adb_keyboard,
            restore_keyboard,
        )
        from phone_agent.adb.input import (
            type_text as adb_type_text,
        )

        # 切换到ADB Keyboard
        original_ime = detect_and_set_adb_keyboard(device_id)
        time.sleep(0.3)  # 缩短延迟 (原1秒)

        # 清空文本
        clear_text(device_id)
        time.sleep(0.2)  # 缩短延迟 (原1秒)

        # 输入文本
        adb_type_text(text, device_id)
        time.sleep(0.5)  # 缩短延迟 (原1秒)

        # 恢复键盘
        restore_keyboard(original_ime, device_id)
        time.sleep(0.2)  # 缩短延迟 (原1秒)

        logger.debug(f"ADB Keyboard输入成功: {text[:30]}...")
        return True

    except Exception as e:
        logger.debug(f"ADB Keyboard输入失败: {e}")
        return False


def reset_input_method(device_id: Optional[str] = None):
    """重置设备的输入方法缓存"""
    device_key = device_id or "default"
    if device_key in _device_input_methods:
        del _device_input_methods[device_key]
        logger.info(f"已重置 {device_key} 的输入方法")


def get_input_method(device_id: Optional[str] = None) -> Optional[str]:
    """获取设备当前使用的输入方法"""
    device_key = device_id or "default"
    return _device_input_methods.get(device_key)


__all__ = ["smart_type_text", "reset_input_method", "get_input_method"]
