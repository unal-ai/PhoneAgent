#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0
#
# Inspired by Android Action Kernel (MIT License)
# Copyright (c) 2024 Action State Labs
# Original: https://github.com/actionstatelabs/android-action-kernel

"""
混合智能体 - 自动选择最优执行模式

⚠️ **DEPRECATED - 已废弃**
此模块已被废弃，不建议在新代码中使用。
请直接使用 PhoneAgent (Vision Kernel)，它更稳定且经过充分测试。

废弃原因:
- XML Kernel 稳定性不足，导致混合模式不可靠
- 自动切换逻辑增加复杂性，难以调试
- Vision Kernel 已足够满足绝大多数场景

迁移指南:
>>> # 旧代码 (废弃)
>>> from phone_agent.kernel import HybridAgent, ExecutionMode
>>> agent = HybridAgent(model_config, config=HybridConfig(mode=ExecutionMode.AUTO))
>>>
>>> # 新代码 (推荐)
>>> from phone_agent import PhoneAgent
>>> agent = PhoneAgent(model_config)
"""

import warnings
warnings.warn(
    "HybridAgent 已废弃，请直接使用 PhoneAgent (Vision Kernel)。\n"
    "详见 PROJECT_ASSESSMENT.md 和 ROADMAP.md",
    DeprecationWarning,
    stacklevel=2
)

import logging
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass

from phone_agent.model import ModelConfig
from phone_agent.kernel.xml_agent import XMLKernelAgent, XMLKernelConfig
from phone_agent.kernel.callback import StepCallback, NoOpCallback
from phone_agent.agent import PhoneAgent, AgentConfig


logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """执行模式枚举"""
    XML = "xml"  # XML树模式（快速、便宜）
    VISION = "vision"  # 视觉模式（兜底）
    AUTO = "auto"  # 自动选择


@dataclass
class HybridConfig:
    """混合智能体配置
    
    推荐：生产环境使用 mode=ExecutionMode.VISION
    """
    mode: ExecutionMode = ExecutionMode.VISION  # ✅ 改为默认 Vision（稳定）
    device_id: str | None = None
    max_steps: int = 50
    verbose: bool = True
    
    # XML模式配置
    xml_max_elements: int = 50
    xml_step_delay: float = 0.3  # ✅ 优化: 缩短到0.3秒 (原1.5秒)
    
    # Vision模式配置
    vision_system_prompt: str | None = None


class HybridAgent:
    """
    混合智能体 - 融合XML和Vision两种内核
    
    工作流程：
    1. 根据mode选择执行内核
    2. XML模式失败时自动降级到Vision模式
    3. 记录性能指标，优化后续选择
    
    Example:
        >>> from phone_agent.kernel import HybridAgent, ExecutionMode
        >>> from phone_agent.model import ModelConfig
        >>> 
        >>> model_config = ModelConfig(
        ...     api_key="your-api-key",
        ...     base_url="https://open.bigmodel.cn/api/paas/v4/",
        ...     model_name="autoglm-phone"
        ... )
        >>> 
        >>> # 方式1: 使用XML模式（推荐）
        >>> agent = HybridAgent(
        ...     model_config=model_config,
        ...     config=HybridConfig(mode=ExecutionMode.XML)
        ... )
        >>> 
        >>> # 方式2: 自动模式（智能选择）
        >>> agent = HybridAgent(
        ...     model_config=model_config,
        ...     config=HybridConfig(mode=ExecutionMode.AUTO)
        ... )
        >>> 
        >>> result = agent.run("打开大麦，搜索演唱会")
    """
    
    def __init__(
        self,
        model_config: ModelConfig,
        config: Optional[HybridConfig] = None,
        step_callback: Optional[StepCallback] = None
    ):
        self.model_config = model_config
        self.config = config or HybridConfig()
        self.step_callback = step_callback or NoOpCallback()
        
        # 初始化两个内核（延迟创建）
        self._xml_agent: Optional[XMLKernelAgent] = None
        self._vision_agent: Optional[PhoneAgent] = None
        
        # 性能统计
        self._stats = {
            "xml_success": 0,
            "xml_failure": 0,
            "vision_success": 0,
            "vision_failure": 0
        }
    
    def run(self, task: str) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            task: 任务描述（自然语言）
        
        Returns:
            执行结果字典，包含：
            - success: 是否成功
            - mode: 使用的模式
            - steps: 步骤数
            - message: 结果消息
            - cost_estimate: 成本估算（美元）
        """
        if self.config.verbose:
            logger.info(f"🤖 混合智能体启动")
            logger.info(f"📋 任务: {task}")
            logger.info(f"⚙️ 模式: {self.config.mode.value}")
        
        # 根据模式选择执行策略
        if self.config.mode == ExecutionMode.XML:
            return self._run_xml_mode(task)
        
        elif self.config.mode == ExecutionMode.VISION:
            return self._run_vision_mode(task)
        
        elif self.config.mode == ExecutionMode.AUTO:
            return self._run_auto_mode(task)
        
        else:
            raise ValueError(f"未知的执行模式: {self.config.mode}")
    
    def _run_xml_mode(self, task: str) -> Dict[str, Any]:
        """
        XML模式执行
        
        优势：
        - 速度快 10-20倍
        - 成本低 95%
        - 精度高 99%+
        """
        if self.config.verbose:
            logger.info("🚀 使用 XML Kernel 模式")
        
        try:
            # 延迟创建XML agent
            if not self._xml_agent:
                self._xml_agent = XMLKernelAgent(
                    model_config=self.model_config,
                    config=XMLKernelConfig(
                        device_id=self.config.device_id,
                        max_steps=self.config.max_steps,
                        max_elements=self.config.xml_max_elements,
                        step_delay=self.config.xml_step_delay,
                        verbose=self.config.verbose
                    ),
                    step_callback=self.step_callback  # 🆕 传递回调
                )
            
            # 执行
            result = self._xml_agent.run(task)
            
            # 更新统计
            if result.get("success"):
                self._stats["xml_success"] += 1
            else:
                self._stats["xml_failure"] += 1
            
            # 添加成本估算
            steps = result.get("steps", 0)
            result["cost_estimate"] = steps * 0.01  # $0.01/步
            result["mode"] = "xml"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ XML模式执行失败: {e}", exc_info=True)
            self._stats["xml_failure"] += 1
            
            return {
                "success": False,
                "mode": "xml",
                "steps": 0,
                "message": f"XML模式失败: {str(e)}",
                "cost_estimate": 0
            }
    
    def _run_vision_mode(self, task: str) -> Dict[str, Any]:
        """
        Vision模式执行
        
        优势：
        - 适用于所有界面
        - 可处理复杂图形
        - 兜底方案
        
        劣势：
        - 速度慢
        - 成本高
        - 精度相对较低
        """
        if self.config.verbose:
            logger.info("🚀 使用 Vision Kernel 模式")
        
        try:
            # 延迟创建Vision agent
            if not self._vision_agent:
                agent_config = AgentConfig(
                    device_id=self.config.device_id,
                    max_steps=self.config.max_steps,
                    verbose=self.config.verbose
                )
                
                if self.config.vision_system_prompt:
                    agent_config.system_prompt = self.config.vision_system_prompt
                
                self._vision_agent = PhoneAgent(
                    model_config=self.model_config,
                    agent_config=agent_config
                )
            
            # 执行
            message = self._vision_agent.run(task)
            
            # 更新统计
            success = "完成" in message or "成功" in message
            if success:
                self._stats["vision_success"] += 1
            else:
                self._stats["vision_failure"] += 1
            
            # 添加成本估算
            steps = self._vision_agent.step_count
            cost_estimate = steps * 0.15  # $0.15/步（视觉Token多）
            
            return {
                "success": success,
                "mode": "vision",
                "steps": steps,
                "message": message,
                "cost_estimate": cost_estimate
            }
            
        except Exception as e:
            logger.error(f"❌ Vision模式执行失败: {e}", exc_info=True)
            self._stats["vision_failure"] += 1
            
            return {
                "success": False,
                "mode": "vision",
                "steps": 0,
                "message": f"Vision模式失败: {str(e)}",
                "cost_estimate": 0
            }
    
    def _run_auto_mode(self, task: str) -> Dict[str, Any]:
        """
        自动模式 - 智能选择最优内核
        
        策略：
        1. 优先尝试XML模式（快速、便宜）
        2. XML失败且建议降级时，自动切换到Vision模式
        3. 记录性能，优化后续选择
        
        🆕 降级触发条件:
        - UI获取持续失败
        - 连续多次无法获取UI元素
        - XML Agent明确返回should_fallback=True
        """
        if self.config.verbose:
            logger.info("🤖 自动模式：优先尝试 XML Kernel")
        
        # 1. 尝试XML模式
        xml_result = self._run_xml_mode(task)
        
        if xml_result.get("success"):
            if self.config.verbose:
                logger.info("✅ XML模式成功完成")
            return xml_result
        
        # 2. 检查是否应该降级
        should_fallback = xml_result.get("should_fallback", False)
        reason = xml_result.get("reason", "unknown")
        
        if should_fallback:
            if self.config.verbose:
                logger.warning(f"⚠️ XML模式失败 (原因: {reason})，自动降级到 Vision Kernel")
                logger.info("🔄 Vision Kernel可以处理更复杂的界面...")
            
            # 降级到Vision模式
            vision_result = self._run_vision_mode(task)
            
            # 标记为auto模式降级
            vision_result["mode"] = "auto (xml→vision)"
            vision_result["degraded"] = True
            vision_result["degradation_reason"] = reason
            
            return vision_result
        else:
            # XML失败但不建议降级（可能是任务本身的问题）
            if self.config.verbose:
                logger.error("❌ XML模式失败，且未建议降级到Vision")
            
            xml_result["mode"] = "xml (failed)"
            return xml_result
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取性能统计
        
        Returns:
            统计信息字典
        """
        total_xml = self._stats["xml_success"] + self._stats["xml_failure"]
        total_vision = self._stats["vision_success"] + self._stats["vision_failure"]
        
        return {
            "xml": {
                "success": self._stats["xml_success"],
                "failure": self._stats["xml_failure"],
                "total": total_xml,
                "success_rate": self._stats["xml_success"] / total_xml if total_xml > 0 else 0
            },
            "vision": {
                "success": self._stats["vision_success"],
                "failure": self._stats["vision_failure"],
                "total": total_vision,
                "success_rate": self._stats["vision_success"] / total_vision if total_vision > 0 else 0
            }
        }
    
    def reset(self):
        """重置所有agent状态"""
        if self._xml_agent:
            self._xml_agent.reset()
        if self._vision_agent:
            self._vision_agent.reset()


# 使用示例
if __name__ == "__main__":
    from phone_agent.model import ModelConfig
    
    # 配置模型
    model_config = ModelConfig(
        api_key="your-api-key",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="autoglm-phone"
    )
    
    # 创建混合agent
    agent = HybridAgent(
        model_config=model_config,
        config=HybridConfig(
            mode=ExecutionMode.AUTO,  # 自动选择
            device_id="localhost:6100",
            verbose=True
        )
    )
    
    # 执行任务
    result = agent.run("打开大麦，搜索周杰伦演唱会")
    
    print(f"\n{'='*50}")
    print(f"执行结果:")
    print(f"  成功: {result['success']}")
    print(f"  模式: {result['mode']}")
    print(f"  步骤: {result['steps']}")
    print(f"  成本: ${result['cost_estimate']:.2f}")
    print(f"  消息: {result['message']}")
    print(f"{'='*50}\n")
    
    # 查看统计
    stats = agent.get_stats()
    print(f"性能统计:")
    print(f"  XML: {stats['xml']['success']}/{stats['xml']['total']} ({stats['xml']['success_rate']:.1%})")
    print(f"  Vision: {stats['vision']['success']}/{stats['vision']['total']} ({stats['vision']['success_rate']:.1%})")

