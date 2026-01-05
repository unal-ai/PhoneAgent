#!/usr/bin/env python3
# Original: Copyright (c) 2024 ZAI Organization (Apache-2.0)
# Modified: Copyright (C) 2025 PhoneAgent Contributors (AGPL-3.0)
# Based on: https://github.com/zai-org/Open-AutoGLM

"""Main PhoneAgent class for orchestrating phone automation."""

import base64
import io
import json
import logging
import traceback
from dataclasses import dataclass
from typing import Any, Callable

from PIL import Image

from phone_agent.actions import ActionHandler
from phone_agent.actions.handler import finish, parse_action
from phone_agent.adb import get_current_app, get_screenshot
from phone_agent.config import SYSTEM_PROMPT
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.model.client import MessageBuilder
from phone_agent.utils.stabilizer import wait_for_ui_stabilization

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the PhoneAgent."""

    max_steps: int = 100
    device_id: str | None = None
    system_prompt: str = SYSTEM_PROMPT
    verbose: bool = True
    max_history_images: int = 3  # 默认保留最近3张历史截图 (不含当前) -> Logically 4 total
    enable_stabilization: bool = True  # 是否开启截图防抖
    enable_xml_hierarchy: bool = True  # 是否获取XML UI层级信息


@dataclass
class StepResult:
    """Result of a single agent step."""

    success: bool
    finished: bool
    action: dict[str, Any] | None
    thinking: str
    message: str | None = None
    usage: dict[str, Any] | None = None  # Token usage from AI model


class PhoneAgent:
    """
    AI-powered agent for automating Android phone interactions.

    The agent uses a vision-language model to understand screen content
    and decide on actions to complete user tasks.

    Args:
        model_config: Configuration for the AI model.
        agent_config: Configuration for the agent behavior.
        confirmation_callback: Optional callback for sensitive action confirmation.
        takeover_callback: Optional callback for takeover requests.

    Example:
        >>> from phone_agent import PhoneAgent
        >>> from phone_agent.model import ModelConfig
        >>>
        >>> model_config = ModelConfig(base_url="http://localhost:8000/v1")
        >>> agent = PhoneAgent(model_config)
        >>> agent.run("Open WeChat and send a message to John")
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        agent_config: AgentConfig | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
        step_callback: Any | None = None,
        installed_apps: list[dict[str, str]] | None = None,  # 已安装应用列表
        stream_callback: Callable[[str], None] | None = None,  # 流式 token 回调
    ):
        self.model_config = model_config or ModelConfig()
        self.agent_config = agent_config or AgentConfig()

        # 如果提供了已安装应用列表，注入到系统提示词中
        if installed_apps:
            apps_info = "\n".join([f"- {app['name']} ({app['package']})" for app in installed_apps])
            apps_prompt = f"\n\n## Installed Apps\nThe following apps are installed on the device. You can launch them using `open_app(app_name)`:\n{apps_info}\n"
            # 只有当系统提示词中尚未包含时才添加
            if "## Installed Apps" not in self.agent_config.system_prompt:
                self.agent_config.system_prompt += apps_prompt

        self.model_client = ModelClient(self.model_config)
        self.action_handler = ActionHandler(
            device_id=self.agent_config.device_id,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
        )

        self._context: list[dict[str, Any]] = []
        self._step_count = 0
        self._scratchpad: str = ""  # 🧠 Persistent Memory
        self._last_action_result: str | None = None  # 上一步操作结果

        # 新增：步骤回调支持
        from phone_agent.kernel.callback import NoOpCallback

        self.step_callback = step_callback or NoOpCallback()
        self.stream_callback = stream_callback  # 流式 token 回调

    async def _compress_history_images(self, image_indices: list[int]):
        """
        智能压缩历史图片：保持最新一张高清(1080p PNG)，压缩历史图片为标清(512p JPEG)。
        该方法直接修改 self._context 中的消息内容。
        """
        if not image_indices:
            return

        # 最新的一张图片不需要压缩（它是当前的屏幕状态）
        # 历史图片仅用于提供上下文（"之前在什么界面"），不需要高清细节
        history_indices = image_indices[:-1]

        for idx in history_indices:
            try:
                msg = self._context[idx]
                if not isinstance(msg.get("content"), list):
                    continue

                for item in msg["content"]:
                    if item.get("type") == "image_url":
                        image_url = item["image_url"]["url"]
                        # 只处理 PNG 格式或者尚未标记为压缩的图片
                        # 这里简单通过检测是否包含 "image/png" 来判断是否是原始高清图
                        if "data:image/png" in image_url:
                            # 提取 base64
                            try:
                                base64_data = image_url.split("base64,")[1]
                                # 🛡️ 防御性检查
                                if (
                                    not base64_data
                                    or base64_data == "None"
                                    or len(base64_data) < 100
                                ):
                                    logger.warning(
                                        f"Skipping compression for invalid image data at index {idx}"
                                    )
                                    continue

                                image_bytes = base64.b64decode(base64_data)

                                # 加载并处理
                                img = Image.open(io.BytesIO(image_bytes))

                                # 调整大小：最大边长 512px
                                max_dimension = 512
                                if max(img.size) > max_dimension:
                                    img.thumbnail(
                                        (max_dimension, max_dimension), Image.Resampling.LANCZOS
                                    )

                                # 转为 JPEG 格式以进一步压缩体积 (Quality=70)
                                buffer = io.BytesIO()
                                # 转换为 RGB (JPEG 不支持 RGBA)
                                if img.mode in ("RGBA", "P"):
                                    img = img.convert("RGB")
                                img.save(buffer, format="JPEG", quality=70)

                                new_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

                                # 更新消息内容
                                item["image_url"]["url"] = f"data:image/jpeg;base64,{new_base64}"
                                logger.info(
                                    f"Using Smart Compression for history image at index {idx}"
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Error during image compression at index {idx}: {e}"
                                )
                                continue
            except Exception as e:
                logger.warning(f"Failed to compress history image at index {idx}: {e}")

    def _strip_xml_from_history(self):
        """
        Strip UI Elements data from historical user messages to save tokens.
        Only the most recent user message should contain UI Elements.
        """
        import re

        # Find all user messages except the last one
        user_msg_indices = [i for i, msg in enumerate(self._context) if msg.get("role") == "user"]

        if len(user_msg_indices) <= 1:
            return  # No history to strip

        def strip_ui_elements(text: str) -> str:
            """Remove UI Elements section from text."""
            # Match "UI Elements:" followed by everything until end or next section
            cleaned = re.sub(r"\n\nUI Elements:\n.*$", "", text, flags=re.DOTALL)
            return cleaned

        # Strip UI Elements from all but the last user message
        for idx in user_msg_indices[:-1]:
            msg = self._context[idx]
            content = msg.get("content")

            if isinstance(content, list):
                # Multi-part message (text + image)
                for item in content:
                    if item.get("type") == "text":
                        item["text"] = strip_ui_elements(item.get("text", ""))
            elif isinstance(content, str):
                self._context[idx]["content"] = strip_ui_elements(content)

    def run(self, task: str) -> str:
        """
        Run the agent to complete a task.

        Args:
            task: Natural language description of the task.

        Returns:
            Final message from the agent.
        """
        self._context = []
        self._step_count = 0

        # First step with user prompt
        result = self._execute_step(task, is_first=True)

        if result.finished:
            return result.message or "Task completed"

        # Continue until finished or max steps reached
        while self._step_count < self.agent_config.max_steps:
            result = self._execute_step(is_first=False)

            if result.finished:
                return result.message or "Task completed"

        return "Max steps reached"

    def step(self, task: str | None = None) -> StepResult:
        """
        Execute a single step of the agent.

        Useful for manual control or debugging.

        Args:
            task: Task description (only needed for first step).

        Returns:
            StepResult with step details.
        """
        is_first = len(self._context) == 0

        if is_first and not task:
            raise ValueError("Task is required for the first step")

        return self._execute_step(task, is_first)

    def reset(self) -> None:
        """Reset the agent state for a new task."""
        self._context = []
        self._step_count = 0

    def inject_comment(self, comment: str) -> bool:
        """
        Inject a user comment into the conversation context.

        This allows users to provide mid-execution guidance or corrections
        to the agent. The comment will be included in the next LLM request.

        Args:
            comment: The user's comment/instruction to inject.

        Returns:
            True if injection was successful, False if context is empty.
        """
        if not self._context:
            logger.warning("Cannot inject comment: context is empty")
            return False

        # Add as a user message (will be seen by the model in next step)
        self._context.append(
            MessageBuilder.create_user_message(text=f"[User Intervention] {comment}")
        )
        logger.info(f"Injected user comment: {comment[:50]}...")
        return True

    def _execute_step(self, user_prompt: str | None = None, is_first: bool = False) -> StepResult:
        """Execute a single step of the agent loop."""
        self._step_count += 1

        # Warning: 不在这里调用 on_step_start，因为此时还没有 thinking 和 action
        # on_step_start 会在 LLM 响应后、执行动作前调用

        # Capture current screen state (with stabilization)
        # Capture current screen state (with stabilization)
        try:
            if self.agent_config.enable_stabilization:
                screenshot = wait_for_ui_stabilization(self.agent_config.device_id)
            else:
                screenshot = get_screenshot(self.agent_config.device_id)
            current_app = get_current_app(self.agent_config.device_id)
        except Exception as e:
            logger.error(f"Failed to capture screenshot or get app info: {e}")
            if self.agent_config.verbose:
                traceback.print_exc()
            return StepResult(
                success=False,
                finished=True,
                action=None,
                thinking="",
                message=f"System error: Failed to capture screen. {e}",
            )

        # 🛡️ 数据完整性检查
        if (
            not screenshot.base64_data
            or screenshot.base64_data == "None"
            or screenshot.base64_data.strip() == "None"
        ):
            logger.error(
                f"Invalid screenshot data detected! len={len(screenshot.base64_data) if screenshot.base64_data else 'None'}"
            )
            # 强制修正为 None，避免后续流程报错
            screenshot.base64_data = None

        # Get UI Hierarchy (XML) - Optional but recommended
        ui_elements_str = ""
        if self.agent_config.enable_xml_hierarchy:
            try:
                from phone_agent.adb.xml_tree import format_elements_for_llm, get_ui_hierarchy

                elements = get_ui_hierarchy(self.agent_config.device_id)
                # Pass screen dimensions for coordinate normalization
                screen_w = screenshot.width if screenshot else 1080
                screen_h = screenshot.height if screenshot else 2400
                ui_elements_str = format_elements_for_llm(
                    elements, screen_width=screen_w, screen_height=screen_h
                )
                # logger.debug(f"Fetched {len(elements)} UI elements")
            except Exception as e:
                logger.warning(f"Failed to get UI hierarchy: {e}")

        # Build messages
        if is_first:
            self._context.append(
                MessageBuilder.create_system_message(self.agent_config.system_prompt)
            )

            screen_info = MessageBuilder.build_screen_info(
                current_app, ui_hierarchy=ui_elements_str
            )
            text_content = f"{user_prompt}\n\n{screen_info}"

            # 🧠 如果有记忆，注入到Prompt中
            if self._scratchpad:
                text_content = f"** 🧠 Persistent Memory (Update with UpdateMemory) **\n{self._scratchpad}\n\n{text_content}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )
        else:
            screen_info = MessageBuilder.build_screen_info(
                current_app, ui_hierarchy=ui_elements_str
            )

            # 注入上一步操作结果（关键反馈）
            action_feedback = ""
            if self._last_action_result:
                action_feedback = f"** Last Action Result **\n{self._last_action_result}\n\n"

            text_content = f"{action_feedback}** Screen Info **\n\n{screen_info}"

            # 🧠 如果有记忆，注入到Prompt中
            if self._scratchpad:
                text_content = f"** 🧠 Persistent Memory (Update with UpdateMemory) **\n{self._scratchpad}\n\n{text_content}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )

        # Get model response (支持流式输出)
        try:
            # 🆕 通知步骤开始（在调用模型前，以便前端接收流式Thinking）
            start_info = {"thinking": "", "action": "Thinking..."}
            self.step_callback.on_step_start(
                self._step_count, json.dumps(start_info, ensure_ascii=False)
            )

            if self.model_config.enable_streaming:
                response = self.model_client.request_stream(
                    self._context,
                    on_token=self.stream_callback,
                )
            else:
                response = self.model_client.request(self._context)
        except Exception as e:
            # 错误处理：如果遇到 BadRequestError (400)，尝试移除最新的一张图片重试
            # 错误特征: 'Non-base64 digit found' 或 'BadRequestError'
            error_str = str(e)
            if "BadRequestError" in error_str or "Non-base64" in error_str or "400" in error_str:
                logger.warning(
                    f"Model request failed with 400 Error: {e}. Retrying without ANY images..."
                )

                # 移除整个上下文中的所有图片（不仅是最后一条）
                # 这是为了防止历史消息中残留无效的图片数据导致持续报错
                if self._context:
                    for i in range(len(self._context)):
                        self._context[i] = MessageBuilder.remove_images_from_message(
                            self._context[i]
                        )

                    try:
                        logger.info("Retrying request with text only (all images removed)...")
                        if self.model_config.enable_streaming:
                            response = self.model_client.request_stream(
                                self._context,
                                on_token=self.stream_callback,
                            )
                        else:
                            response = self.model_client.request(self._context)
                    except Exception as retry_e:
                        logger.error(f"Retry also failed: {retry_e}")
                        if self.agent_config.verbose:
                            traceback.print_exc()
                        return StepResult(
                            success=False,
                            finished=True,
                            action=None,
                            thinking="",
                            message=f"Model error (after retry): {retry_e}",
                        )
            else:
                if self.agent_config.verbose:
                    traceback.print_exc()
                return StepResult(
                    success=False,
                    finished=True,
                    action=None,
                    thinking="",
                    message=f"Model error: {e}",
                )

        # Parse action from response
        try:
            action = parse_action(response.action)
        except ValueError:
            if self.agent_config.verbose:
                traceback.print_exc()
            action = finish(message=response.action)

        # 🧠 Handle Memory Update (Before Callback)
        if action.get("action") == "UpdateMemory":
            old_memory = self._scratchpad
            new_memory = action.get("content", "")
            self._scratchpad = new_memory
            if self.agent_config.verbose:
                logger.debug(f"🧠 Memory Updated: {old_memory[:20]}... -> {new_memory[:20]}...")



        if self.agent_config.verbose:
            # 打印思考过程（使用logger替代print）
            logger.debug("=" * 50)
            logger.debug("💭 思考过程:")
            logger.debug("-" * 50)
            logger.debug(response.thinking)
            logger.debug("-" * 50)
            logger.debug("🎯 执行动作:")
            logger.debug(json.dumps(action, ensure_ascii=False, indent=2))
            logger.debug("=" * 50)

        # Manage history images based on configuration
        # Identify all user messages with images
        image_indices = []
        for i, msg in enumerate(self._context):
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                # Check if message has image content
                has_image = any(item.get("type") == "image_url" for item in msg["content"])
                if has_image:
                    image_indices.append(i)

        # Keep the last N images (max_history_images) + 1 (current step)
        # Note: The current step's image is the last one in the list
        # max_history_images=1 means keep 1 history + 1 current = 2 total
        images_to_keep = self.agent_config.max_history_images + 1

        if len(image_indices) > images_to_keep:
            # We need to remove some images
            # Calculate how many to remove
            num_to_remove = len(image_indices) - images_to_keep

            # Remove images from messages
            for i in range(num_to_remove):
                idx = image_indices[i]
                msg = self._context[idx]
                self._context[idx] = MessageBuilder.remove_images_from_message(msg)
                logger.debug(f"Removed history image from message index {idx}")

        # 智能压缩历史图片：保持最新的图片为高清，其余压缩为标清
        # 重新获取包含图片的索引（因为上面可能移除了部分）
        remaining_image_indices = []
        for i, msg in enumerate(self._context):
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                if any(item.get("type") == "image_url" for item in msg["content"]):
                    remaining_image_indices.append(i)

        # 执行异步压缩
        import asyncio

        # 注意: _execute_step 是同步方法，这里使用 run_until_complete 或直接调用同步版本的 helper
        # 由于我们是在 executor 中运行 agent.step，这里可以直接运行
        try:
            asyncio.run(self._compress_history_images(remaining_image_indices))
        except RuntimeError:
            # 如果已有 loop 运行（例如在同一线程），则直接 await（但这通常不在 executor 中发生）
            # 简单起见，我们将 _compress_history_images 改为同步方法，或使用 new loop
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._compress_history_images(remaining_image_indices))
            loop.close()

        # Strip XML from older messages to save context tokens
        # Only keep XML in the current (last) user message
        self._strip_xml_from_history()

        # Execute action
        try:
            result = self.action_handler.execute(action, screenshot.width, screenshot.height)
        except Exception as e:
            if self.agent_config.verbose:
                traceback.print_exc()
            result = self.action_handler.execute(
                finish(message=str(e)), screenshot.width, screenshot.height
            )

        # Store action result for next step's feedback
        action_name = action.get("action", action.get("_metadata", "unknown"))
        if result.success:
            self._last_action_result = f"✓ {action_name} executed successfully"
            if result.message:
                self._last_action_result += f": {result.message}"
        else:
            self._last_action_result = f"✗ {action_name} failed"
            if result.message:
                self._last_action_result += f": {result.message}"

        # Add assistant response to context
        self._context.append(
            MessageBuilder.create_assistant_message(
                f"<think>{response.thinking}</think><answer>{response.action}</answer>"
            )
        )

        # Check if finished
        finished = action.get("_metadata") == "finish" or result.should_finish

        # 通知步骤完成
        self.step_callback.on_step_complete(
            self._step_count,
            result.success,
            thinking=response.thinking,
            observation=result.message or action.get("message", ""),
            action=json.dumps(action, ensure_ascii=False) if action else None,
        )

        if finished and self.agent_config.verbose:
            logger.info("=" * 50)
            logger.info(f"任务完成: {result.message or action.get('message', '完成')}")
            logger.info("=" * 50)

        return StepResult(
            success=result.success,
            finished=finished,
            action=action,
            thinking=response.thinking,
            message=result.message or action.get("message"),
            usage=response.usage,  # Pass token usage info
        )

    @property
    def context(self) -> list[dict[str, Any]]:
        """Get the current conversation context."""
        return self._context.copy()

    @property
    def step_count(self) -> int:
        """Get the current step count."""
        return self._step_count
