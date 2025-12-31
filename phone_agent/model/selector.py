#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""
模型选择策略管理器

根据执行内核（XML/Vision）自动选择最优模型：
- XML Kernel → GLM-4-1V-Thinking-Flash（64k上下文，免费，适合长任务）
- Vision Kernel → AutoGLM-Phone（官方推荐，针对视觉任务优化）

支持环境变量配置和运行时动态切换。
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class KernelType(Enum):
    """内核类型"""

    XML = "xml"  # XML内核（基于UI树）
    VISION = "vision"  # Vision内核（基于截图）
    PLANNING = "planning"  # 规划模式
    AUTO = "auto"  # 自动选择


@dataclass
class ModelPreset:
    """模型预设配置"""

    model_name: str
    description: str
    context_length: int
    free: bool
    recommended_for: list[str]

    def __str__(self):
        free_tag = "🆓免费" if self.free else "💰付费"
        return f"{self.model_name} ({free_tag}, {self.context_length//1000}k上下文)"


# ============================================
# 可用模型预设
# ============================================

AVAILABLE_MODELS = {
    # ============================================
    # AutoGLM 官方模型
    # ============================================
    "autoglm-phone": ModelPreset(
        model_name="autoglm-phone",
        description="AutoGLM官方Phone模型，针对手机自动化优化",
        context_length=25_480,  # 未官方披露，保守估计
        free=True,
        recommended_for=["vision"],
    ),
    # ============================================
    # GLM-4.6v 系列（最新旗舰视觉模型）
    # ============================================
    "glm-4.6v": ModelPreset(
        model_name="glm-4.6v",
        description="GLM-4.6视觉旗舰模型，最强视觉理解能力（付费）",
        context_length=8_000,
        free=False,
        recommended_for=["vision", "planning"],
    ),
    "glm-4.6v-flash": ModelPreset(
        model_name="glm-4.6v-flash",
        description="GLM-4.6视觉Flash版，免费，高性价比",
        context_length=8_000,
        free=True,
        recommended_for=["vision", "planning"],
    ),
    "glm-4.6v-flashx": ModelPreset(
        model_name="glm-4.6v-flashx",
        description="GLM-4.6视觉FlashX版，极速响应（付费）",
        context_length=8_000,
        free=False,
        recommended_for=["vision"],
    ),
    # ============================================
    # GLM-4.1v 系列（旧版，保留用于兼容）
    # ============================================
    "glm-4.1v-thinking-flash": ModelPreset(
        model_name="glm-4.1v-thinking-flash",
        description="GLM-4.1视觉推理模型Flash版，免费，64k上下文",
        context_length=64_000,
        free=True,
        recommended_for=["xml", "planning", "auto"],
    ),
}


# ============================================
# 默认策略配置
# ============================================

DEFAULT_MODEL_STRATEGY = {
    # Warning: XML内核已废弃，默认fallback到vision
    KernelType.XML: "autoglm-phone",
    # Vision内核使用AutoGLM官方Phone模型（推荐）
    KernelType.VISION: "autoglm-phone",
    # 规划模式使用autoglm-phone（针对手机优化）
    KernelType.PLANNING: "autoglm-phone",
    # 自动模式使用autoglm-phone
    KernelType.AUTO: "autoglm-phone",
}


class ModelSelector:
    """
    模型选择器

    根据执行内核类型自动选择最优模型。
    支持环境变量配置覆盖默认策略。

    Environment Variables:
        VISION_KERNEL_MODEL: Vision内核使用的模型（默认: glm-4.6v-flash）
        PLANNING_KERNEL_MODEL: 规划模式使用的模型（默认: glm-4.6v-flash）
        CUSTOM_MODEL_NAME: 强制所有模式使用同一模型（推荐：glm-4.6v, glm-4.6v-flash, glm-4.6v-flashx）

    Example:
        >>> selector = ModelSelector()
        >>> model = selector.select_model(KernelType.XML)
        >>> print(model)  # glm-4.1v-thinking-flash

        >>> model = selector.select_model(KernelType.VISION)
        >>> print(model)  # autoglm-phone
    """

    def __init__(self):
        self.strategy = self._load_strategy()
        self._log_strategy()

    def _load_strategy(self) -> Dict[KernelType, str]:
        """从环境变量加载策略（支持多平台）"""
        strategy = DEFAULT_MODEL_STRATEGY.copy()

        # 优先检查 MODEL_PROVIDER 和 CUSTOM_MODEL_NAME
        # 如果设置了自定义模型，所有内核都使用它
        custom_model = os.getenv("CUSTOM_MODEL_NAME")
        if custom_model:
            logger.info(f"🌍 使用自定义模型: {custom_model} (所有内核)")
            return {
                KernelType.XML: custom_model,
                KernelType.VISION: custom_model,
                KernelType.PLANNING: custom_model,
                KernelType.AUTO: custom_model,
            }

        # 检查是否强制使用单一模型（向后兼容）
        force_model = os.getenv("FORCE_SINGLE_MODEL")
        if force_model:
            logger.info(f"🔒 强制所有内核使用模型: {force_model}")
            for kernel_type in KernelType:
                strategy[kernel_type] = force_model
            return strategy

        # 从环境变量加载各内核的模型配置
        xml_model = os.getenv("XML_KERNEL_MODEL")
        if xml_model:
            strategy[KernelType.XML] = xml_model
            logger.info(f"XML内核模型（环境变量）: {xml_model}")

        vision_model = os.getenv("VISION_KERNEL_MODEL")
        if vision_model:
            strategy[KernelType.VISION] = vision_model
            logger.info(f"Vision内核模型（环境变量）: {vision_model}")

        planning_model = os.getenv("PLANNING_KERNEL_MODEL")
        if planning_model:
            strategy[KernelType.PLANNING] = planning_model
            logger.info(f"规划模式模型（环境变量）: {planning_model}")

        return strategy

    def _log_strategy(self):
        """打印当前策略"""
        logger.info("📋 模型选择策略:")
        for kernel_type, model_name in self.strategy.items():
            preset = AVAILABLE_MODELS.get(model_name)
            if preset:
                logger.info(f"  • {kernel_type.value:12} → {preset}")
            else:
                logger.warning(f"  • {kernel_type.value:12} → {model_name} (未知模型)")

    def select_model(self, kernel_type: KernelType, override_model: Optional[str] = None) -> str:
        """
        选择模型

        Args:
            kernel_type: 内核类型
            override_model: 强制指定的模型（优先级最高）

        Returns:
            模型名称
        """
        # 优先使用强制指定的模型
        if override_model:
            logger.info(f"🎯 使用强制指定模型: {override_model}")
            return override_model

        # 使用策略选择
        model_name = self.strategy.get(kernel_type, DEFAULT_MODEL_STRATEGY[KernelType.AUTO])

        preset = AVAILABLE_MODELS.get(model_name)
        if preset:
            logger.debug(f"{kernel_type.value} 内核 → {preset}")
        else:
            logger.warning(f"未知模型: {model_name}")

        return model_name

    def get_model_info(self, model_name: str) -> Optional[ModelPreset]:
        """获取模型信息"""
        return AVAILABLE_MODELS.get(model_name)

    def list_available_models(self) -> Dict[str, ModelPreset]:
        """列出所有可用模型"""
        return AVAILABLE_MODELS.copy()

    def validate_model(self, model_name: str) -> bool:
        """验证模型是否可用"""
        return model_name in AVAILABLE_MODELS


# ============================================
# 全局单例
# ============================================

_model_selector: Optional[ModelSelector] = None


def get_model_selector() -> ModelSelector:
    """获取全局模型选择器单例"""
    global _model_selector
    if _model_selector is None:
        _model_selector = ModelSelector()
    return _model_selector


def select_model_for_kernel(kernel_mode: str, override_model: Optional[str] = None) -> str:
    """
    为内核选择模型（便捷函数）

    Args:
        kernel_mode: 内核模式字符串（"xml", "vision", "auto"等）
        override_model: 强制指定的模型

    Returns:
        模型名称

    Example:
        >>> model = select_model_for_kernel("xml")
        >>> print(model)  # glm-4.1v-thinking-flash
    """
    selector = get_model_selector()

    # 转换字符串为枚举
    try:
        kernel_type = KernelType(kernel_mode.lower())
    except ValueError:
        logger.warning(f"未知内核模式: {kernel_mode}，使用AUTO")
        kernel_type = KernelType.AUTO

    return selector.select_model(kernel_type, override_model)


# ============================================
# Task Complexity Evaluation (Phase 3)
# ============================================


def evaluate_task_complexity(instruction: str) -> str:
    """
    Evaluate task complexity and return recommended model tier.

    Args:
        instruction: User instruction text

    Returns:
        "simple" or "complex"

    Simple tasks (use glm-4.6v-flash):
    - Single-step operations (open app, go back, screenshot)
    - Short instructions (< 20 chars)
    - Common app operations

    Complex tasks (use glm-4.6v):
    - Multi-step operations (with 然后, 并且, and, then)
    - Long instructions (> 50 chars)
    - Search/purchase/form-filling operations
    """
    instruction = instruction.strip().lower()

    # Check for complexity indicators
    complex_patterns = [
        "然后",
        "接着",
        "之后",
        "并且",
        "同时",
        "and then",
        "after that",
        "搜索",
        "查找",
        "购买",
        "下单",
        "填写",
        "输入",
        "发送",
        "分析",
    ]

    # Simple if short and no complex patterns
    if len(instruction) < 20:
        for pattern in complex_patterns:
            if pattern in instruction:
                return "complex"
        return "simple"

    # Complex if long or contains complex patterns
    if len(instruction) > 50:
        return "complex"

    for pattern in complex_patterns:
        if pattern in instruction:
            return "complex"

    return "simple"


def select_model_by_complexity(
    instruction: str,
    kernel_mode: str = "vision",
    override_model: Optional[str] = None,
) -> str:
    """
    Select model based on task complexity for cost optimization.

    Args:
        instruction: User instruction
        kernel_mode: Kernel mode string
        override_model: Force specific model

    Returns:
        Model name optimized for cost/performance
    """
    if override_model:
        return override_model

    complexity = evaluate_task_complexity(instruction)

    if complexity == "simple":
        # Use free/cheap model for simple tasks
        logger.info(f"Task complexity: simple → using glm-4.6v-flash")
        return "glm-4.6v-flash"
    else:
        # Use standard model for complex tasks
        logger.info(f"Task complexity: complex → using autoglm-phone")
        return "autoglm-phone"


# ============================================
# CLI工具（用于测试和配置）
# ============================================

if __name__ == "__main__":

    # 配置日志
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    print("\n" + "=" * 60)
    print("📱 PhoneAgent 模型选择器")
    print("=" * 60 + "\n")

    selector = ModelSelector()

    print("📋 可用模型列表:\n")
    for name, preset in selector.list_available_models().items():
        print(f"  • {preset}")
        print(f"    描述: {preset.description}")
        print(f"    推荐: {', '.join(preset.recommended_for)}")
        print()

    print("=" * 60)
    print("🎯 当前策略测试:\n")

    test_cases = [
        ("xml", "XML内核（长任务，需要大上下文）"),
        ("vision", "Vision内核（视觉理解）"),
        ("planning", "规划模式"),
        ("auto", "自动模式"),
    ]

    for kernel_mode, description in test_cases:
        model = select_model_for_kernel(kernel_mode)
        preset = selector.get_model_info(model)
        print(f"  • {description}")
        print(f"    内核: {kernel_mode}")
        print(f"    模型: {preset if preset else model}")
        print()

    print("=" * 60)
    print("提示:")
    print("  1. 设置 FORCE_SINGLE_MODEL=glm-4.1v-thinking-flash 统一使用大模型")
    print("  2. 设置 XML_KERNEL_MODEL=xxx 单独配置XML内核模型")
    print("  3. 设置 VISION_KERNEL_MODEL=xxx 单独配置Vision内核模型")
    print("=" * 60 + "\n")
