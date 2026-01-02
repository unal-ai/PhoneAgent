#!/usr/bin/env python3
# Original: Copyright (c) 2024 ZAI Organization (Apache-2.0)
# Modified: Copyright (C) 2025 PhoneAgent Contributors (AGPL-3.0)
# Based on: https://github.com/zai-org/Open-AutoGLM

"""Main PhoneAgent class for orchestrating phone automation."""

import json
import logging
import traceback
from dataclasses import dataclass
from typing import Any, Callable

from phone_agent.actions import ActionHandler
from phone_agent.actions.handler import finish, parse_action
from phone_agent.adb import get_current_app, get_screenshot
from phone_agent.config import SYSTEM_PROMPT
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.model.client import MessageBuilder

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the PhoneAgent."""

    max_steps: int = 100
    device_id: str | None = None
    system_prompt: str = SYSTEM_PROMPT
    verbose: bool = True


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
        step_callback: Any | None = None,  # 新增：步骤回调
    ):
        self.model_config = model_config or ModelConfig()
        self.agent_config = agent_config or AgentConfig()

        self.model_client = ModelClient(self.model_config)
        self.action_handler = ActionHandler(
            device_id=self.agent_config.device_id,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
        )

        self._context: list[dict[str, Any]] = []
        self._step_count = 0

        # 新增：步骤回调支持
        from phone_agent.kernel.callback import NoOpCallback

        self.step_callback = step_callback or NoOpCallback()

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
            MessageBuilder.create_user_message(
                text=f"[User Intervention] {comment}"
            )
        )
        logger.info(f"Injected user comment: {comment[:50]}...")
        return True

    def _execute_step(self, user_prompt: str | None = None, is_first: bool = False) -> StepResult:
        """Execute a single step of the agent loop."""
        self._step_count += 1

        # Warning: 不在这里调用 on_step_start，因为此时还没有 thinking 和 action
        # on_step_start 会在 LLM 响应后、执行动作前调用

        # Capture current screen state
        screenshot = get_screenshot(self.agent_config.device_id)
        current_app = get_current_app(self.agent_config.device_id)

        # Build messages
        if is_first:
            self._context.append(
                MessageBuilder.create_system_message(self.agent_config.system_prompt)
            )

            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"{user_prompt}\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )
        else:
            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"** Screen Info **\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )

        # Get model response
        try:
            response = self.model_client.request(self._context)
        except Exception as e:
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

        # 🆕 通知步骤开始（此时已有 thinking 和 action）
        action_json = json.dumps(action, ensure_ascii=False) if action else "{}"
        # 将 thinking 和 action 组合传递
        step_info = {"thinking": response.thinking, "action": action_json}
        self.step_callback.on_step_start(
            self._step_count, json.dumps(step_info, ensure_ascii=False)
        )

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

        # Remove image from context to save space
        self._context[-1] = MessageBuilder.remove_images_from_message(self._context[-1])

        # Execute action
        try:
            result = self.action_handler.execute(action, screenshot.width, screenshot.height)
        except Exception as e:
            if self.agent_config.verbose:
                traceback.print_exc()
            result = self.action_handler.execute(
                finish(message=str(e)), screenshot.width, screenshot.height
            )

        # Add assistant response to context
        self._context.append(
            MessageBuilder.create_assistant_message(
                f"<think>{response.thinking}</think><answer>{response.action}</answer>"
            )
        )

        # Check if finished
        finished = action.get("_metadata") == "finish" or result.should_finish

        # 🆕 通知步骤完成
        self.step_callback.on_step_complete(
            self._step_count,
            result.success,
            thinking=response.thinking,
            observation=result.message or action.get("message", ""),
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
