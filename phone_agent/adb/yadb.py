#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0
#
# This module uses yadb binary from official repository (LGPL-3.0)
# Repository: https://github.com/ysbing/YADB
# Author: ysbing
#
# YADB is called as an independent tool via subprocess (dynamic linking),
# so PhoneAgent code remains independent and is NOT subject to LGPL copyleft.

"""
YADB utilities for enhanced Android device control.

Key features (official yadb support):
- Chinese text input (no APK required)
- Force screenshot (bypass FLAG_SECURE)
- Clipboard operations
- Long press simulation

Note: yadb does NOT support UI layout dump. Use uiautomator for that.
"""

import base64
import hashlib
import logging
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Optional

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)

# yadb 文件的 MD5 校验值（官方版本）
YADB_MD5 = "29a0cd3b3adea92350dd5a25594593df"

# yadb 在本地的路径
YADB_LOCAL_PATH = Path(__file__).parent.parent / "yadb" / "yadb"

# yadb 在设备上的路径
YADB_DEVICE_PATH = "/data/local/tmp/yadb"


def _check_md5(file_path: Path) -> str:
    """Calculate MD5 hash of a file."""
    if not file_path.exists():
        return ""

    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def _build_adb_cmd(device_id: str = None, adb_host: str = None, adb_port: int = None) -> list:
    """
    Build ADB command prefix.

    Args:
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)

    Returns:
        ADB command prefix list
    """
    cmd = ["adb"]

    # FRP 隧道模式（优先）
    if adb_host and adb_port:
        cmd.extend(["-H", adb_host, "-P", str(adb_port)])
    # 直接连接模式
    elif device_id:
        cmd.extend(["-s", device_id])

    return cmd


def is_yadb_installed(device_id: str = None, adb_host: str = None, adb_port: int = None) -> bool:
    """
    Check if yadb is installed on the device.

    Args:
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)

    Returns:
        True if yadb is installed and has correct MD5, False otherwise.
    """
    cmd = _build_adb_cmd(device_id, adb_host, adb_port)

    try:
        # 检查 MD5
        result = subprocess.run(
            cmd + ["shell", "md5sum", YADB_DEVICE_PATH], capture_output=True, text=True, timeout=10
        )

        return YADB_MD5 in result.stdout

    except Exception as e:
        logger.debug(f"yadb check failed: {e}")
        return False


def install_yadb(device_id: str = None, adb_host: str = None, adb_port: int = None) -> bool:
    """
    Push yadb binary to the device.

    Args:
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)

    Returns:
        True if installation successful, False otherwise.
    """
    if not YADB_LOCAL_PATH.exists():
        logger.error(f"yadb binary not found at {YADB_LOCAL_PATH}")
        logger.info("Please download yadb from: https://github.com/ysbing/YADB/blob/master/yadb")
        return False

    # 验证本地文件的 MD5
    local_md5 = _check_md5(YADB_LOCAL_PATH)
    if local_md5 != YADB_MD5:
        logger.warning(f"Local yadb file MD5 mismatch: {local_md5} != {YADB_MD5}")
        logger.warning("This might be a different version, continuing anyway...")

    cmd = _build_adb_cmd(device_id, adb_host, adb_port)

    try:
        # 推送文件（增加超时时间到60秒）
        push_cmd = cmd + ["push", str(YADB_LOCAL_PATH), YADB_DEVICE_PATH]
        logger.info(f"Pushing yadb to device with command: {' '.join(push_cmd)}")
        result = subprocess.run(
            push_cmd, capture_output=True, text=True, timeout=60  # 增加超时时间从30秒到60秒
        )

        if result.returncode != 0:
            logger.error(f"Failed to push yadb (exit code {result.returncode})")
            logger.error(f"  stderr: {result.stderr}")
            logger.error(f"  stdout: {result.stdout}")
            return False

        logger.info(f"yadb push command succeeded: {result.stdout.strip()}")

        # 验证推送后的文件
        if is_yadb_installed(device_id, adb_host, adb_port):
            logger.info("yadb successfully installed")
            return True
        else:
            logger.error("yadb installation verification failed")
            return False

    except subprocess.TimeoutExpired:
        logger.error("yadb installation timeout")
        return False
    except Exception as e:
        logger.error(f"yadb installation error: {e}")
        return False


def ensure_yadb_ready(device_id: str = None, adb_host: str = None, adb_port: int = None) -> bool:
    """
    Ensure yadb is installed and ready to use.

    Args:
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)

    Returns:
        True if yadb is ready, False otherwise.
    """
    if is_yadb_installed(device_id, adb_host, adb_port):
        logger.debug("yadb already installed")
        return True

    logger.info("yadb not found, installing...")
    return install_yadb(device_id, adb_host, adb_port)


def type_text(text: str, device_id: str = None, adb_host: str = None, adb_port: int = None) -> bool:
    """
    Type text into the currently focused input field using yadb.

    Args:
        text: The text to type (supports Chinese, Emoji, etc.)
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)

    Returns:
        True if successful, False otherwise.

    Example:
        >>> type_text("你好，世界！", device_id="device_6100")
        True
    """
    # 确保 yadb 已安装
    if not ensure_yadb_ready(device_id, adb_host, adb_port):
        logger.error("yadb not ready")
        return False

    cmd = _build_adb_cmd(device_id, adb_host, adb_port)

    # 预处理文本：空格需要转义
    processed_text = text.replace(" ", "\\ ")

    # 构建 yadb 命令
    cmd.extend(
        [
            "shell",
            "app_process",
            "-Djava.class.path=/data/local/tmp/yadb",
            "/data/local/tmp",
            "com.ysbing.yadb.Main",
            "-keyboard",
            processed_text,
        ]
    )

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            logger.debug(f"Typed text via yadb: {text[:50]}...")
            return True
        else:
            logger.error(f"yadb type_text failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("yadb type_text timeout")
        return False
    except Exception as e:
        logger.error(f"yadb type_text error: {e}")
        return False


def force_screenshot(
    device_id: str = None, adb_host: str = None, adb_port: int = None, return_pil: bool = False
) -> Optional[bytes | tuple]:
    """
    Capture screenshot using yadb (bypasses FLAG_SECURE).

    **Key Feature**: This method can screenshot sensitive apps
    (banking, payment, etc.) that normally block screenshots.

    Args:
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)
        return_pil: If True, returns (image_bytes, PIL.Image), else just bytes

    Returns:
        PNG image bytes if successful, None if failed.
        If return_pil=True: (bytes, PIL.Image) tuple

    Example:
        >>> # Standard usage
        >>> png_data = force_screenshot(device_id="device_6100")
        >>> with open("screenshot.png", "wb") as f:
        ...     f.write(png_data)

        >>> # Get both bytes and PIL Image
        >>> png_data, img = force_screenshot(device_id="device_6100", return_pil=True)
        >>> print(f"Size: {img.width}x{img.height}")
    """
    if not ensure_yadb_ready(device_id, adb_host, adb_port):
        logger.error("yadb not ready for screenshot")
        return None

    cmd = _build_adb_cmd(device_id, adb_host, adb_port)

    # 构建 yadb 截图命令
    cmd.extend(
        [
            "shell",
            "app_process",
            "-Djava.class.path=/data/local/tmp/yadb",
            "/data/local/tmp",
            "com.ysbing.yadb.Main",
            "-screenshot",
        ]
    )

    try:
        logger.debug("Executing yadb force screenshot...")
        result = subprocess.run(cmd, capture_output=True, timeout=30)

        if result.returncode != 0:
            logger.error(
                f"yadb screenshot failed: {result.stderr.decode('utf-8', errors='ignore')}"
            )
            return None

        # PNG 数据直接从 stdout 输出
        png_data = result.stdout

        if not png_data or len(png_data) < 100:
            logger.error(f"Screenshot data too small: {len(png_data)} bytes")
            return None

        logger.info(f"Force screenshot captured: {len(png_data)} bytes")

        # 如果需要返回 PIL Image
        if return_pil and PIL_AVAILABLE:
            try:
                img = Image.open(BytesIO(png_data))
                return (png_data, img)
            except Exception as e:
                logger.warning(f"Failed to create PIL Image: {e}, returning bytes only")
                return png_data

        return png_data

    except subprocess.TimeoutExpired:
        logger.error("yadb screenshot timeout")
        return None
    except Exception as e:
        logger.error(f"yadb screenshot error: {e}")
        return None


def force_screenshot_base64(
    device_id: str = None,
    adb_host: str = None,
    adb_port: int = None,
    include_dimensions: bool = False,
) -> Optional[str | dict]:
    """
    Capture screenshot using yadb and return base64 encoded data.

    This is a convenience wrapper around force_screenshot() that returns
    base64 data ready for API responses or AI vision models.

    Args:
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)
        include_dimensions: If True, returns dict with base64 + width/height

    Returns:
        Base64 string if include_dimensions=False
        Dict with {base64_data, width, height} if include_dimensions=True
        None if screenshot failed

    Example:
        >>> # Simple usage
        >>> b64 = force_screenshot_base64(device_id="device_6100")
        >>> print(f"data:image/png;base64,{b64}")

        >>> # With dimensions
        >>> data = force_screenshot_base64(device_id="device_6100", include_dimensions=True)
        >>> print(f"Size: {data['width']}x{data['height']}")
    """
    result = force_screenshot(
        device_id, adb_host, adb_port, return_pil=PIL_AVAILABLE and include_dimensions
    )

    if result is None:
        return None

    # 处理返回值
    if isinstance(result, tuple):
        png_data, img = result
        base64_data = base64.b64encode(png_data).decode("utf-8")

        if include_dimensions:
            return {
                "base64_data": base64_data,
                "width": img.width,
                "height": img.height,
                "is_sensitive": False,  # yadb 绕过了限制
            }
        return base64_data
    else:
        # 只有 bytes
        base64_data = base64.b64encode(result).decode("utf-8")

        if include_dimensions and PIL_AVAILABLE:
            try:
                img = Image.open(BytesIO(result))
                return {
                    "base64_data": base64_data,
                    "width": img.width,
                    "height": img.height,
                    "is_sensitive": False,
                }
            except Exception:
                pass

        return base64_data


def long_press(
    x: int,
    y: int,
    duration_ms: int = 2000,
    device_id: str = None,
    adb_host: str = None,
    adb_port: int = None,
) -> bool:
    """
    Perform a long press at the specified coordinates using yadb.

    Args:
        x: X coordinate
        y: Y coordinate
        duration_ms: Duration in milliseconds (default: 2000)
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)

    Returns:
        True if successful, False otherwise.
    """
    if not ensure_yadb_ready(device_id, adb_host, adb_port):
        return False

    cmd = _build_adb_cmd(device_id, adb_host, adb_port)

    cmd.extend(
        [
            "shell",
            "app_process",
            "-Djava.class.path=/data/local/tmp/yadb",
            "/data/local/tmp",
            "com.ysbing.yadb.Main",
            "-touch",
            str(x),
            str(y),
            str(duration_ms),
        ]
    )

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"yadb long_press error: {e}")
        return False


def read_clipboard(
    device_id: str = None, adb_host: str = None, adb_port: int = None
) -> Optional[str]:
    """
    Read clipboard content from device using yadb.

    Args:
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)

    Returns:
        Clipboard content or None if failed.
    """
    if not ensure_yadb_ready(device_id, adb_host, adb_port):
        return None

    cmd = _build_adb_cmd(device_id, adb_host, adb_port)

    cmd.extend(
        [
            "shell",
            "app_process",
            "-Djava.class.path=/data/local/tmp/yadb",
            "/data/local/tmp",
            "com.ysbing.yadb.Main",
            "-readClipboard",
        ]
    )

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception as e:
        logger.error(f"yadb read_clipboard error: {e}")
        return None


def write_clipboard(
    text: str, device_id: str = None, adb_host: str = None, adb_port: int = None
) -> bool:
    """
    Write text to device clipboard using yadb.

    Args:
        text: Text to write
        device_id: Device serial number
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)

    Returns:
        True if successful, False otherwise.
    """
    if not ensure_yadb_ready(device_id, adb_host, adb_port):
        return False

    cmd = _build_adb_cmd(device_id, adb_host, adb_port)

    cmd.extend(
        [
            "shell",
            "app_process",
            "-Djava.class.path=/data/local/tmp/yadb",
            "/data/local/tmp",
            "com.ysbing.yadb.Main",
            "-writeClipboard",
            text,
        ]
    )

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"yadb write_clipboard error: {e}")
        return False


# REMOVED: dump_layout() function
# Reason: Official yadb does NOT support `-layout` parameter
# This function never worked and always failed silently
# Use uiautomator dump instead (see ui_hierarchy.py)
