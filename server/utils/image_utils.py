"""
图片处理工具 - 截图压缩优化

支持多级压缩：
- AI识别用：1280x720, JPEG 85%
- 前端展示用：640x360, JPEG 75%

性能优化：
- 异步压缩（不阻塞主线程）
- 批量处理（多级别并行）
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)

# 线程池（用于图片处理）
_image_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="image-worker")


class ImageCompressor:
    """图片压缩器"""

    # 压缩级别配置
    LEVELS = {
        "ai": {"size": (1280, 720), "quality": 85, "suffix": "_ai"},
        "medium": {"size": (960, 540), "quality": 80, "suffix": "_medium"},
        "small": {"size": (640, 360), "quality": 75, "suffix": "_small"},
        "thumbnail": {"size": (320, 180), "quality": 70, "suffix": "_thumb"},
    }

    @staticmethod
    def compress_image(
        input_path: str,
        output_path: Optional[str] = None,
        level: str = "medium",
        max_size: Optional[Tuple[int, int]] = None,
        quality: Optional[int] = None,
    ) -> str:
        """
        压缩图片

        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径（None则自动生成）
            level: 压缩级别（ai/medium/small/thumbnail）
            max_size: 自定义最大尺寸，覆盖level配置
            quality: 自定义质量，覆盖level配置

        Returns:
            输出文件路径
        """
        try:
            # 获取压缩配置
            config = ImageCompressor.LEVELS.get(level, ImageCompressor.LEVELS["medium"])
            target_size = max_size or config["size"]
            target_quality = quality or config["quality"]

            # 生成输出路径
            if output_path is None:
                base, ext = os.path.splitext(input_path)
                output_path = f"{base}{config['suffix']}.jpg"

            # 打开并压缩图片
            with Image.open(input_path) as img:
                # 转换为RGB（处理RGBA等格式）
                if img.mode in ("RGBA", "LA", "P"):
                    # 创建白色背景
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(
                        img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
                    )
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                # 获取原始尺寸
                original_size = img.size

                # 计算缩放后的尺寸（保持宽高比）
                img.thumbnail(target_size, Image.Resampling.LANCZOS)

                # 保存压缩后的图片
                img.save(
                    output_path,
                    "JPEG",
                    quality=target_quality,
                    optimize=True,
                    progressive=True,  # 渐进式JPEG
                )

                # 获取压缩后的文件大小
                original_kb = os.path.getsize(input_path) / 1024
                compressed_kb = os.path.getsize(output_path) / 1024
                compression_ratio = (1 - compressed_kb / original_kb) * 100

                logger.info(
                    f"图片压缩成功: {original_size} -> {img.size}, "
                    f"{original_kb:.1f}KB -> {compressed_kb:.1f}KB "
                    f"(节省 {compression_ratio:.1f}%)"
                )

                return output_path

        except Exception as e:
            logger.error(f"图片压缩失败: {e}")
            raise

    @staticmethod
    def compress_multiple_levels(
        input_path: str, output_dir: Optional[str] = None, levels: Optional[list] = None
    ) -> dict:
        """
        一次性生成多个压缩级别的图片

        Args:
            input_path: 输入图片路径
            output_dir: 输出目录（None则使用输入文件所在目录）
            levels: 压缩级别列表（默认生成ai, medium, small）

        Returns:
            各级别的输出路径字典
        """
        if output_dir is None:
            output_dir = os.path.dirname(input_path)

        if levels is None:
            levels = ["ai", "medium", "small"]

        results = {}
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        for level in levels:
            try:
                config = ImageCompressor.LEVELS[level]
                output_path = os.path.join(output_dir, f"{base_name}{config['suffix']}.jpg")

                compressed_path = ImageCompressor.compress_image(
                    input_path, output_path, level=level
                )

                results[level] = compressed_path

            except Exception as e:
                logger.error(f"压缩级别 {level} 失败: {e}")
                results[level] = None

        return results

    @staticmethod
    def get_image_info(image_path: str) -> dict:
        """获取图片信息"""
        try:
            with Image.open(image_path) as img:
                return {
                    "size": img.size,
                    "width": img.size[0],
                    "height": img.size[1],
                    "format": img.format,
                    "mode": img.mode,
                    "file_size_kb": os.path.getsize(image_path) / 1024,
                }
        except Exception as e:
            logger.error(f"获取图片信息失败: {e}")
            return {}


def compress_screenshot(
    screenshot_path: str, output_dir: Optional[str] = None, for_ai: bool = True
) -> dict:
    """
    快捷函数：压缩截图（同步版本，兼容旧代码）

    Args:
        screenshot_path: 截图路径
        output_dir: 输出目录
        for_ai: 是否生成AI识别用的版本

    Returns:
        压缩结果字典
    """
    levels = ["ai", "medium", "small"] if for_ai else ["medium", "small"]
    return ImageCompressor.compress_multiple_levels(screenshot_path, output_dir, levels)


async def compress_screenshot_async(
    screenshot_path: str, output_dir: Optional[str] = None, for_ai: bool = True
) -> dict:
    """
    异步压缩截图（推荐使用）

    Args:
        screenshot_path: 截图路径
        output_dir: 输出目录
        for_ai: 是否生成AI识别用的版本

    Returns:
        压缩结果字典

    性能优势:
    - 不阻塞事件循环
    - 多级别并行处理
    - 适合高并发场景
    """

    def _compress():
        levels = ["ai", "medium", "small"] if for_ai else ["medium", "small"]
        return ImageCompressor.compress_multiple_levels(screenshot_path, output_dir, levels)

    # 在线程池中执行（不阻塞事件循环）
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_image_executor, _compress)


async def compress_image_async(
    input_path: str, output_path: Optional[str] = None, level: str = "medium"
) -> str:
    """
    异步压缩单张图片

    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        level: 压缩级别

    Returns:
        输出文件路径
    """

    def _compress():
        return ImageCompressor.compress_image(input_path, output_path, level)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_image_executor, _compress)


# 导出
__all__ = [
    "ImageCompressor",
    "compress_screenshot",
    "compress_screenshot_async",  # 新增: 异步版本
    "compress_image_async",  # 新增: 异步版本
]
