"""Screenshot utilities for capturing Android device screen."""

import base64
import logging
import subprocess
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

# 尝试导入 yadb（强制截图功能）
try:
    from . import yadb

    YADB_AVAILABLE = True
except ImportError:
    YADB_AVAILABLE = False

logger = logging.getLogger(__name__)

# 配置：是否尝试使用 yadb 强制截图
USE_YADB_FORCE_SCREENSHOT = True


@dataclass
class Screenshot:
    """Represents a captured screenshot."""

    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False
    forced: bool = False  # 新增：是否使用强制截图


def get_screenshot(
    device_id: str | None = None,
    timeout: int = 30,
    adb_host: str | None = None,
    adb_port: int | None = None,
    force_yadb: bool = False,
) -> Screenshot:
    """
    Capture a screenshot from the connected Android device.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        timeout: Timeout in seconds for screenshot operations.
        adb_host: ADB server host (for FRP tunneling)
        adb_port: ADB server port (for FRP tunneling)
        force_yadb: Force use yadb even if standard method succeeds

    Returns:
        Screenshot object containing base64 data and dimensions.

    Note:
        Tries standard screencap first. If it fails (e.g., on sensitive screens
        like payment apps with FLAG_SECURE), automatically falls back to yadb
        force screenshot which bypasses these restrictions.
    """
    # 如果强制使用 yadb
    if force_yadb and YADB_AVAILABLE and USE_YADB_FORCE_SCREENSHOT:
        logger.info("Using yadb force screenshot (forced mode)")
        return _get_screenshot_yadb(device_id, adb_host, adb_port)

    # 尝试标准截图
    screenshot = _get_screenshot_standard(device_id, timeout, adb_host, adb_port)

    # 如果标准截图失败，尝试 yadb 强制截图
    if screenshot.is_sensitive and YADB_AVAILABLE and USE_YADB_FORCE_SCREENSHOT:
        logger.info("Standard screenshot failed, trying yadb force screenshot...")
        yadb_screenshot = _get_screenshot_yadb(device_id, adb_host, adb_port)

        if yadb_screenshot and not yadb_screenshot.is_sensitive:
            logger.info("yadb force screenshot succeeded!")
            return yadb_screenshot
        else:
            logger.warning("yadb force screenshot also failed, returning fallback")

    return screenshot


def _get_screenshot_standard(
    device_id: str | None = None,
    timeout: int = 30,
    adb_host: str | None = None,
    adb_port: int | None = None,
) -> Screenshot:
    """
    Standard screenshot using adb screencap.

    This is the default method, but will fail on apps with FLAG_SECURE.
    """
    adb_prefix = _get_adb_prefix(device_id, adb_host, adb_port)

    try:
        # 使用 exec-out 直接获取截图数据（不需要在手机上写文件）
        # 这种方法更适合远程 FRP 环境
        result = subprocess.run(
            adb_prefix + ["exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=timeout,
        )

        # 检查是否成功
        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="ignore")
            logger.warning(f"Standard screenshot failed: {error_msg}")

            # 检测是否是敏感页面（FLAG_SECURE）
            is_sensitive = "Status: -1" in error_msg or "FLAG_SECURE" in error_msg
            return _create_fallback_screenshot(is_sensitive=is_sensitive)

        # 直接从 stdout 获取 PNG 数据
        image_data = result.stdout

        if not image_data or len(image_data) < 100:
            logger.warning(f"Screenshot data too small: {len(image_data)} bytes")
            # 修复：数据过小也可能是敏感屏幕
            return _create_fallback_screenshot(is_sensitive=True)

        # 使用 BytesIO 从内存中加载图片
        img = Image.open(BytesIO(image_data))

        # 🆕 调整图片大小，防止 API 报错 (Code 1210)
        # 限制最大边长为 1080px
        max_dimension = 1080
        if max(img.size) > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            # 重新保存到 BytesIO
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            image_data = buffer.getvalue()

        width, height = img.size

        # 新增：检测是否是全黑或几乎全黑的图片（可能是敏感屏幕）
        # 计算平均亮度
        grayscale = img.convert("L")  # 转为灰度
        pixels = list(grayscale.getdata())
        avg_brightness = sum(pixels) / len(pixels)

        # 如果平均亮度低于10（几乎全黑），标记为敏感
        if avg_brightness < 10:
            logger.warning(
                f"Screenshot is almost black (brightness: {avg_brightness:.1f}), marking as sensitive"
            )
            return _create_fallback_screenshot(is_sensitive=True)

        # 直接对原始数据进行 base64 编码
        base64_data = base64.b64encode(image_data).decode("utf-8")

        return Screenshot(
            base64_data=base64_data, width=width, height=height, is_sensitive=False, forced=False
        )

    except subprocess.TimeoutExpired:
        logger.error(f"Screenshot timeout after {timeout}s")
        return _create_fallback_screenshot(is_sensitive=True)  # 超时也标记为敏感
    except Exception as e:
        logger.error(f"Screenshot error: {e}", exc_info=True)
        return _create_fallback_screenshot(is_sensitive=True)  # 异常也标记为敏感


def _get_screenshot_yadb(
    device_id: str | None = None, adb_host: str | None = None, adb_port: int | None = None
) -> Screenshot:
    """
    Force screenshot using yadb (bypasses FLAG_SECURE).

    This method can capture screenshots even on sensitive apps like banking
    and payment apps that normally block screenshots.
    """
    try:
        result = yadb.force_screenshot_base64(
            device_id=device_id, adb_host=adb_host, adb_port=adb_port, include_dimensions=True
        )

        if result and isinstance(result, dict):
            base64_data = result["base64_data"]
            width = result["width"]
            height = result["height"]

            # 🆕 调整图片大小，防止 API 报错 (Code 1210)
            max_dimension = 1080
            if max(width, height) > max_dimension:
                try:
                    # 解码
                    image_data = base64.b64decode(base64_data)
                    img = Image.open(BytesIO(image_data))
                    # 调整大小
                    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                    # 重新编码
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    width, height = img.size
                except Exception as e:
                    logger.warning(f"Failed to resize yadb screenshot: {e}")

            return Screenshot(
                base64_data=base64_data,
                width=width,
                height=height,
                is_sensitive=False,
                forced=True,  # 标记为强制截图
            )
        else:
            logger.error("yadb force screenshot returned invalid data")
            return _create_fallback_screenshot(is_sensitive=True)

    except Exception as e:
        logger.error(f"yadb force screenshot error: {e}", exc_info=True)
        return _create_fallback_screenshot(is_sensitive=True)


def _get_adb_prefix(
    device_id: str | None, adb_host: str | None = None, adb_port: int | None = None
) -> list:
    """Get ADB command prefix with optional device specifier."""
    cmd = ["adb"]

    # FRP 隧道模式（优先）
    if adb_host and adb_port:
        cmd.extend(["-H", adb_host, "-P", str(adb_port)])
    # 直接连接模式
    elif device_id:
        cmd.extend(["-s", device_id])

    return cmd


def _create_fallback_screenshot(is_sensitive: bool) -> Screenshot:
    """Create a black fallback image when screenshot fails."""
    default_width, default_height = 1080, 2400

    black_img = Image.new("RGB", (default_width, default_height), color="black")
    buffered = BytesIO()
    black_img.save(buffered, format="PNG")
    base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return Screenshot(
        base64_data=base64_data,
        width=default_width,
        height=default_height,
        is_sensitive=is_sensitive,
    )
