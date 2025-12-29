#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0
#
# This file incorporates code from Android Action Kernel (MIT License)
# Copyright (c) 2024 Action State Labs
# Original: https://github.com/actionstatelabs/android-action-kernel
# Files: kernel.py

"""
XML Kernel Agent - 基于UI树的智能体

⚠️ **DEPRECATED - 已废弃**
此模块已被废弃，不建议在新代码中使用。
请使用 Vision Kernel (PhoneAgent) 替代，它更稳定且经过充分测试。

废弃原因:
- 依赖 uiautomator 稳定性差，某些界面经常获取失败
- WebView、动态内容、复杂界面支持有限
- 维护成本高，与 Vision Kernel 功能重叠

迁移指南:
>>> # 旧代码 (废弃)
>>> from phone_agent.kernel import XMLKernelAgent
>>> agent = XMLKernelAgent(model_config)
>>>
>>> # 新代码 (推荐)
>>> from phone_agent import PhoneAgent
>>> agent = PhoneAgent(model_config)

核心逻辑集成自 Android Action Kernel (MIT License)
"""

import warnings
warnings.warn(
    "XMLKernelAgent 已废弃，请使用 PhoneAgent (Vision Kernel) 替代。"
    "详见 PROJECT_ASSESSMENT.md 和 ROADMAP.md",
    DeprecationWarning,
    stacklevel=2
)

import json
import time
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

from phone_agent.adb import tap, back, home, swipe, long_press, double_tap
from phone_agent.adb.device import run_adb_command, launch_app
from phone_agent.adb.xml_tree import (
    format_elements_for_llm,
    UIElement
)
# 🆕 使用鲁棒的UI层级获取
from phone_agent.adb.ui_hierarchy import get_ui_hierarchy_robust as get_ui_hierarchy
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.kernel.callback import StepCallback, NoOpCallback


logger = logging.getLogger(__name__)


@dataclass
class XMLKernelConfig:
    """XML Kernel 配置"""
    max_steps: int = 50  # 最大步骤数
    max_elements: int = 50  # 每次发送给LLM的最大元素数
    step_delay: float = 0.3  # ✅ 优化: 缩短到0.3秒 (原1.5秒, 节省80%)
    device_id: str | None = None
    verbose: bool = True
    max_context_turns: int = 5  # 🆕 最大上下文轮数，防止token超限


class XMLKernelAgent:
    """
    基于XML树的智能体
    
    工作流程：
    1. 抓取UI XML树
    2. 解析出交互元素（文本+坐标）
    3. 发送给LLM推理（纯文本，Token少）
    4. 执行动作
    5. 重复
    
    Example:
        >>> from phone_agent.kernel import XMLKernelAgent, XMLKernelConfig
        >>> from phone_agent.model import ModelConfig
        >>> 
        >>> model_config = ModelConfig(
        ...     api_key="your-api-key",
        ...     base_url="https://open.bigmodel.cn/api/paas/v4/",
        ...     model_name="glm-4"
        ... )
        >>> 
        >>> agent = XMLKernelAgent(
        ...     model_config=model_config,
        ...     config=XMLKernelConfig(device_id="localhost:6100")
        ... )
        >>> 
        >>> result = agent.run("打开大麦，搜索演唱会")
    """
    
    def __init__(
        self,
        model_config: ModelConfig,
        config: Optional[XMLKernelConfig] = None,
        step_callback: Optional[StepCallback] = None
    ):
        self.model_config = model_config
        self.config = config or XMLKernelConfig()
        self.step_callback = step_callback or NoOpCallback()
        
        # ⚠️ Beta 警告
        if self.config.verbose:
            logger.warning("⚠️  XML Kernel is in BETA. For production, use Vision Kernel.")
            logger.info("💡 Switch to Vision: Use HybridAgent with mode=ExecutionMode.VISION")
        
        self.model_client = ModelClient(model_config)
        self._context: List[Dict[str, Any]] = []
        self._step_count = 0
    
    def run(self, goal: str) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            goal: 任务目标（自然语言）
        
        Returns:
            执行结果字典
        """
        if self.config.verbose:
            logger.info(f"🚀 XML Kernel Agent 启动")
            logger.info(f"📋 目标: {goal}")
        
        self._context = []
        self._step_count = 0
        
        # 初始化系统prompt
        system_prompt = self._build_system_prompt()
        self._context.append({
            "role": "system",
            "content": system_prompt
        })
        
        # 主循环
        for step in range(self.config.max_steps):
            self._step_count = step + 1
            
            if self.config.verbose:
                logger.info(f"📍 步骤 {self._step_count}/{self.config.max_steps}")
            
            try:
                # 1. 感知：获取UI元素
                if self.config.verbose:
                    logger.info("👀 正在扫描屏幕...")
                
                try:
                    elements = get_ui_hierarchy(self.config.device_id)
                except Exception as e:
                    logger.error(f"❌ UI获取失败: {e}")
                    # 尝试重置策略并重试一次
                    from phone_agent.adb.xml_tree import reset_device_strategy
                    reset_device_strategy(self.config.device_id)
                    logger.info("🔄 已重置UI获取策略，等待1秒后重试...")
                    time.sleep(1)
                    
                    # 重试一次
                    try:
                        elements = get_ui_hierarchy(self.config.device_id)
                    except Exception as retry_e:
                        logger.error(f"❌ UI获取重试失败: {retry_e}")
                        # 连续失败，需要降级（由外层HybridAgent处理）
                        return {
                            "success": False,
                            "steps": self._step_count,
                            "message": f"UI获取失败: {str(e)}",
                            "reason": "ui_unavailable",
                            "should_fallback": True  # 🆕 建议降级到Vision
                        }
                
                if not elements:
                    logger.warning(f"⚠️ 未找到UI元素 (步骤{self._step_count}/{self.config.max_steps})")
                    logger.warning("可能原因: 1) 界面加载中 2) 所有元素无文本标识 3) dump失败")
                    
                    # 🆕 连续2次获取不到UI元素，建议降级（优化阈值）
                    if not hasattr(self, '_empty_ui_count'):
                        self._empty_ui_count = 0
                    self._empty_ui_count += 1
                    
                    if self._empty_ui_count >= 2:
                        logger.error("❌ 连续2次未获取到UI元素，建议降级到Vision Kernel")
                        return {
                            "success": False,
                            "steps": self._step_count,
                            "message": "连续多次无法获取UI元素",
                            "reason": "ui_consistently_empty",
                            "should_fallback": True  # 🆕 建议降级到Vision
                        }
                    
                    logger.info("💡 等待2秒后重试...")
                    time.sleep(2)
                    continue
                
                # 重置空UI计数器
                self._empty_ui_count = 0
                
                if self.config.verbose:
                    logger.info(f"✅ 找到 {len(elements)} 个UI元素")
                
                # 2. 推理：LLM决策
                if self.config.verbose:
                    logger.info("🧠 AI正在思考...")
                
                decision = self._get_llm_decision(goal, elements, is_first=(step == 0))
                
                if self.config.verbose:
                    logger.info(f"💡 决策: {decision.get('reason', '无原因')}")
                    logger.info(f"🎯 动作: {decision.get('action')}")
                
                # 🆕 通知步骤开始（同步调用，传递完整信息）
                import json
                step_info = {
                    "thinking": decision.get("reason", ""),
                    "action": json.dumps(decision, ensure_ascii=False)
                }
                self.step_callback.on_step_start(
                    self._step_count,
                    json.dumps(step_info, ensure_ascii=False)
                )
                
                # 3. 执行动作
                result = self._execute_action(decision)
                
                # 🆕 通知步骤完成（同步调用）
                self.step_callback.on_step_complete(
                    self._step_count,
                    result["success"],
                    thinking=decision.get("reason", ""),
                    observation=f"Action: {decision.get('action')} | Result: {result.get('message', 'OK')}"
                )
                
                if not result["success"]:
                    logger.error(f"❌ 动作执行失败: {result.get('error')}")
                    
                    # ✅ 记录连续失败次数
                    if not hasattr(self, '_consecutive_failures'):
                        self._consecutive_failures = 0
                    self._consecutive_failures += 1
                    
                    # ✅ 连续3次失败，建议降级
                    if self._consecutive_failures >= 3:
                        logger.error("❌ 连续3次动作失败，建议降级到Vision Kernel")
                        return {
                            "success": False,
                            "steps": self._step_count,
                            "message": "连续多次动作失败",
                            "reason": "action_consistently_failing",
                            "should_fallback": True
                        }
                    
                    continue
                
                # ✅ 成功时重置失败计数器
                self._consecutive_failures = 0
                
                # 4. 检查是否完成
                if decision.get("action") == "done":
                    if self.config.verbose:
                        logger.info(f"\n{'🎉 '*25}")
                        logger.info(f"✅ 任务完成: {decision.get('reason')}")
                        logger.info(f"{'🎉 '*25}\n")
                    
                    return {
                        "success": True,
                        "steps": self._step_count,
                        "message": decision.get("reason", "任务完成")
                    }
                
                # 等待UI更新
                time.sleep(self.config.step_delay)
                
            except KeyboardInterrupt:
                # 用户中断，立即退出
                logger.info("⚠️ 用户中断执行")
                raise
            except SystemExit:
                # 系统退出，不捕获
                raise
            except Exception as e:
                logger.error(f"❌ 步骤 {self._step_count} 出错: {e}", exc_info=True)
                
                # 🆕 通知错误（同步调用）
                self.step_callback.on_error(f"Step {self._step_count} error: {str(e)}")
                
                # ✅ 检查是否为严重错误
                if isinstance(e, (MemoryError, OSError)):
                    logger.critical(f"严重错误，终止执行: {e}")
                    return {
                        "success": False,
                        "steps": self._step_count,
                        "message": f"Critical error: {e}",
                        "reason": "critical_error"
                    }
                
                # ✅ 用户取消不计入异常次数
                error_msg = str(e).lower()
                if "cancelled by user" in error_msg or "user interrupt" in error_msg:
                    logger.info("⚠️ 任务被用户取消，不计入异常")
                    return {
                        "success": False,
                        "steps": self._step_count,
                        "message": "Task cancelled by user",
                        "reason": "user_cancelled"
                    }
                
                # ✅ 记录异常次数（仅真实错误）
                if not hasattr(self, '_exception_count'):
                    self._exception_count = 0
                self._exception_count += 1
                
                # ✅ 连续5次异常，建议降级
                if self._exception_count >= 5:
                    logger.error("❌ 连续5次异常，建议降级到Vision Kernel")
                    return {
                        "success": False,
                        "steps": self._step_count,
                        "message": "连续多次异常",
                        "reason": "too_many_exceptions",
                        "should_fallback": True
                    }
                
                continue
        
        # 达到最大步骤数
        logger.warning(f"⚠️ 达到最大步骤数 ({self.config.max_steps})，任务未完成")
        logger.warning("可能原因: 1) 任务过于复杂 2) UI元素识别困难 3) 界面复杂度高")
        
        # 🆕 通知错误（同步调用）
        self.step_callback.on_error(f"达到最大步骤数 ({self.config.max_steps})，任务未完成")
        
        return {
            "success": False,
            "steps": self._step_count,
            "message": "达到最大步骤数，任务未完成",
            "reason": "max_steps_reached",
            "should_fallback": True  # ✅ 建议降级到Vision
        }
    
    def _build_system_prompt(self) -> str:
        """
        构建系统prompt
        
        整合自 Android Action Kernel (MIT License)
        增强: 添加中文支持、Launch动作、更详细的指导
        
        注意: 提示词已迁移到 phone_agent/config/prompts.py 统一管理
        """
        from phone_agent.config.prompts import XML_KERNEL_SYSTEM_PROMPT
        return XML_KERNEL_SYSTEM_PROMPT
    
    def _get_llm_decision(
        self,
        goal: str,
        elements: List[UIElement],
        is_first: bool = False
    ) -> Dict[str, Any]:
        """
        获取LLM决策
        
        Args:
            goal: 任务目标
            elements: UI元素列表
            is_first: 是否第一步
        
        Returns:
            决策字典
        """
        # 🆕 动态上下文窗口管理
        # 当上下文过长时，保留system prompt、首轮任务目标和最近N轮对话
        if len(self._context) > (self.config.max_context_turns * 2 + 1):  # system + N*(user+assistant)
            logger.info(f"🔄 上下文窗口已达到 {len(self._context)} 条，进行压缩...")
            
            system_prompt = self._context[0]  # 保留system prompt
            
            # 🆕 保留第一轮对话（包含原始任务目标）
            first_user_message = None
            first_assistant_message = None
            if len(self._context) >= 3:
                first_user_message = self._context[1]  # 首个user消息
                first_assistant_message = self._context[2]  # 首个assistant响应
            
            # 保留最近N-1轮（因为已经保留了第一轮）
            recent_messages = self._context[-(self.config.max_context_turns * 2 - 2):]  # 保留最近N-1轮
            
            # 重组上下文: system + 第一轮 + 最近N-1轮
            if first_user_message and first_assistant_message:
                self._context = [
                    system_prompt, 
                    first_user_message,
                    first_assistant_message
                ] + recent_messages
            else:
                self._context = [system_prompt] + recent_messages
            
            logger.info(f"✅ 上下文压缩完成，保留 {len(self._context)} 条消息（含原始任务目标）")
        
        # 格式化元素为文本
        elements_text = format_elements_for_llm(elements, self.config.max_elements)
        
        # 构建用户消息
        if is_first:
            user_message = f"""目标: {goal}

当前屏幕的UI元素:
{elements_text}

请分析并决定下一步操作。"""
        else:
            user_message = f"""当前屏幕的UI元素:
{elements_text}

请继续执行目标，决定下一步操作。"""
        
        self._context.append({
            "role": "user",
            "content": user_message
        })
        
        # 调用LLM（使用统一的 ModelClient）
        try:
            # ✅ 使用项目统一的 ModelClient.request_json
            response = self.model_client.request_json(
                messages=self._context,
                temperature=0.1  # 降低随机性，提高稳定性
            )
            
            # 🆕 处理空响应
            if not response.raw_content or not response.raw_content.strip():
                logger.warning("⚠️ LLM返回空响应")
                
                # 连续空响应计数
                if not hasattr(self, '_empty_llm_count'):
                    self._empty_llm_count = 0
                self._empty_llm_count += 1
                
                if self._empty_llm_count >= 2:
                    logger.error("❌ LLM连续2次返回空响应，可能模型异常")
                    raise Exception("LLM连续返回空响应")
                
                return {
                    "action": "wait",
                    "reason": "LLM返回空响应，等待重试"
                }
            
            # 解析JSON响应
            try:
                # ✅ 清理 JSON 中的注释（LLM 有时会返回带注释的 JSON）
                cleaned_content = self._clean_json_comments(response.raw_content)
                decision = json.loads(cleaned_content)
            except json.JSONDecodeError as je:
                logger.error(f"JSON解析失败，原始内容: {response.raw_content[:200]}")
                # ✅ 尝试提取 JSON 对象（可能被包裹在其他文本中）
                try:
                    decision = self._extract_json_from_text(response.raw_content)
                except Exception:
                    return {
                        "action": "wait",
                        "reason": f"JSON解析失败: {str(je)}"
                    }
            
            # 重置空响应计数
            if hasattr(self, '_empty_llm_count'):
                self._empty_llm_count = 0
            
            # 🆕 验证decision格式
            if isinstance(decision, list):
                logger.warning(f"⚠️ decision是list而非dict: {decision}")
                # 尝试提取第一个元素
                if decision and isinstance(decision[0], dict):
                    decision = decision[0]
                else:
                    return {
                        "action": "wait",
                        "reason": "LLM返回了数组格式，无法解析"
                    }
            
            if not isinstance(decision, dict):
                logger.error(f"❌ decision格式错误: {type(decision)}")
                return {
                    "action": "wait",
                    "reason": f"decision格式错误: {type(decision)}"
                }
            
            # 验证必需字段
            if "action" not in decision:
                logger.warning(f"⚠️ decision缺少action字段: {decision}")
                return {
                    "action": "wait",
                    "reason": "LLM响应缺少action字段"
                }
            
            # 记录助手回复
            self._context.append({
                "role": "assistant",
                "content": response.raw_content
            })
            
            # 记录Token使用（如果有）
            if response.usage:
                if self.config.verbose:
                    logger.info(
                        f"📊 Token使用: "
                        f"输入={response.usage['prompt_tokens']}, "
                        f"输出={response.usage['completion_tokens']}, "
                        f"总计={response.usage['total_tokens']}"
                    )
            
            return decision
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}", exc_info=True)
            # 降级：返回等待动作
            return {
                "action": "wait",
                "reason": f"LLM调用失败: {str(e)}"
            }
    
    def _execute_action(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行动作
        
        Args:
            decision: LLM决策
        
        Returns:
            执行结果
        """
        action = decision.get("action")
        
        try:
            if action == "tap":
                coords = decision.get("coordinates")
                if not coords or len(coords) != 2:
                    return {"success": False, "error": "无效的坐标"}
                
                x, y = coords
                if self.config.verbose:
                    logger.info(f"👉 点击: ({x}, {y})")
                
                tap(x, y, self.config.device_id)
                return {"success": True}
            
            elif action == "type":
                text = decision.get("text")
                if not text:
                    return {"success": False, "error": "无文本"}
                
                if self.config.verbose:
                    logger.info(f"⌨️ 输入: {text}")
                
                # ✅ 输入前先点击当前焦点位置，确保输入框获得焦点
                # 如果 LLM 提供了坐标，先点击；否则点击屏幕中心
                coords = decision.get("coordinates") or decision.get("coords")
                if coords and len(coords) == 2:
                    if self.config.verbose:
                        logger.info(f"👉 先点击输入框: ({coords[0]}, {coords[1]})")
                    tap(coords[0], coords[1], self.config.device_id)
                    time.sleep(0.5)  # 等待输入框获得焦点和键盘弹出
                
                # ✅ 使用智能输入（优先yadb，兜底ADB Keyboard）
                from phone_agent.adb.smart_input import smart_type_text
                
                success = smart_type_text(text, self.config.device_id)
                
                if success:
                    # ✅ 输入后自动关闭键盘，避免遮挡其他UI元素
                    time.sleep(0.5)  # 等待输入完成
                    back(self.config.device_id)  # 关闭键盘
                    time.sleep(0.3)  # 等待键盘关闭动画
                    
                    if self.config.verbose:
                        logger.info("⌨️ 已关闭软键盘")
                    
                    return {"success": True, "message": f"输入文本并关闭键盘: {text}"}
                else:
                    return {"success": False, "error": "文本输入失败"}
            
            elif action == "launch":
                app_name = decision.get("app")
                if not app_name:
                    return {"success": False, "error": "无应用名称"}
                
                if self.config.verbose:
                    logger.info(f"🚀 启动应用: {app_name}")
                
                success = launch_app(app_name, self.config.device_id)
                if not success:
                    return {"success": False, "error": f"应用 '{app_name}' 启动失败"}
                return {"success": True}
            
            elif action == "swipe":
                start_coords = decision.get("start")
                end_coords = decision.get("end")
                if not start_coords or len(start_coords) != 2:
                    return {"success": False, "error": "无效的起始坐标"}
                if not end_coords or len(end_coords) != 2:
                    return {"success": False, "error": "无效的结束坐标"}
                
                x1, y1 = start_coords
                x2, y2 = end_coords
                if self.config.verbose:
                    logger.info(f"👆 滑动: ({x1}, {y1}) -> ({x2}, {y2})")
                
                swipe(x1, y1, x2, y2, self.config.device_id)
                return {"success": True}
            
            elif action == "long_press":
                coords = decision.get("coordinates")
                duration = decision.get("duration", 3000)  # 默认3秒
                if not coords or len(coords) != 2:
                    return {"success": False, "error": "无效的坐标"}
                
                x, y = coords
                if self.config.verbose:
                    logger.info(f"👇 长按: ({x}, {y}), {duration}ms")
                
                long_press(x, y, duration, self.config.device_id)
                return {"success": True}
            
            elif action == "double_tap":
                coords = decision.get("coordinates")
                if not coords or len(coords) != 2:
                    return {"success": False, "error": "无效的坐标"}
                
                x, y = coords
                if self.config.verbose:
                    logger.info(f"👆👆 双击: ({x}, {y})")
                
                double_tap(x, y, self.config.device_id)
                return {"success": True}
            
            elif action == "back":
                if self.config.verbose:
                    logger.info("🔙 返回")
                
                back(self.config.device_id)
                return {"success": True}
            
            elif action == "home":
                if self.config.verbose:
                    logger.info("🏠 主页")
                
                home(self.config.device_id)
                return {"success": True}
            
            elif action == "wait":
                if self.config.verbose:
                    logger.info("⏳ 等待...")
                
                time.sleep(2)
                return {"success": True}
            
            elif action == "note":
                message = decision.get("message", "")
                if self.config.verbose:
                    logger.info(f"📝 记录: {message}")
                
                return {"success": True}
            
            elif action == "call_api":
                instruction = decision.get("instruction", "")
                if self.config.verbose:
                    logger.info(f"🔌 API调用: {instruction}")
                
                return {"success": True}
            
            elif action == "interact":
                message = decision.get("message", "需要用户交互")
                if self.config.verbose:
                    logger.info(f"👤 交互请求: {message}")
                
                return {"success": True, "needs_interaction": True}
            
            elif action == "take_over":
                message = decision.get("message", "需要人工介入")
                if self.config.verbose:
                    logger.info(f"🤝 接管请求: {message}")
                
                return {"success": True, "takeover_message": message}
            
            elif action == "done":
                if self.config.verbose:
                    logger.info("✅ 完成")
                
                return {"success": True}
            
            else:
                return {"success": False, "error": f"未知动作: {action}"}
        
        except Exception as e:
            logger.error(f"动作执行失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _clean_json_comments(self, json_str: str) -> str:
        """
        清理 JSON 字符串中的注释
        
        LLM 有时会返回带注释的 JSON，如：
        {
            "action": "tap",
            "coordinates": [720, 865], // 这是一个注释
            "reason": "点击按钮"
        }
        """
        import re
        # 移除单行注释 // ...
        json_str = re.sub(r'//.*?(?=\n|$)', '', json_str)
        # 移除多行注释 /* ... */
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        return json_str
    
    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        从文本中提取 JSON 对象
        
        LLM 有时会返回包裹在其他文本中的 JSON，如：
        这是我的分析...
        {
            "action": "tap",
            "coordinates": [720, 865]
        }
        让我解释一下...
        """
        import re
        # 尝试找到 JSON 对象
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            # 清理注释
            json_str = self._clean_json_comments(json_str)
            return json.loads(json_str)
        raise ValueError("无法从文本中提取 JSON")
    
    def reset(self):
        """重置agent状态"""
        self._context = []
        self._step_count = 0


# 使用示例
if __name__ == "__main__":
    from phone_agent.model import ModelConfig
    
    # 配置模型
    model_config = ModelConfig(
        api_key="your-api-key",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_name="glm-4"
    )
    
    # 创建agent
    agent = XMLKernelAgent(
        model_config=model_config,
        config=XMLKernelConfig(
            device_id="localhost:6100",
            verbose=True
        )
    )
    
    # 执行任务
    result = agent.run("打开设置，找到关于手机")
    print(f"\n最终结果: {result}")

