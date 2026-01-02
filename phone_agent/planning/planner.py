#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""Planning agent for generating and executing task plans."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from phone_agent.adb import get_current_app, get_screenshot
from phone_agent.config.prompts import PLANNING_SYSTEM_PROMPT, PLANNING_USER_PROMPT_TEMPLATE
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.model.client import MessageBuilder

logger = logging.getLogger(__name__)


@dataclass
class TaskPlan:
    """Represents a complete task execution plan."""

    instruction: str
    complexity: str  # simple, medium, complex
    task_analysis: str
    overall_strategy: str
    estimated_duration_seconds: int
    steps: list[dict[str, Any]]
    checkpoints: list[dict[str, Any]]
    risk_points: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert plan to dictionary."""
        return {
            "instruction": self.instruction,
            "complexity": self.complexity,
            "task_analysis": self.task_analysis,
            "overall_strategy": self.overall_strategy,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "steps": self.steps,
            "checkpoints": self.checkpoints,
            "risk_points": self.risk_points,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskPlan":
        """Create plan from dictionary."""
        return cls(
            instruction=data["instruction"],
            complexity=data.get("complexity", "medium"),
            task_analysis=data.get("task_analysis", ""),
            overall_strategy=data.get("overall_strategy", ""),
            estimated_duration_seconds=data.get("estimated_duration_seconds", 30),
            steps=data.get("steps", []),
            checkpoints=data.get("checkpoints", []),
            risk_points=data.get("risk_points", []),
        )


class PlanningAgent:
    """
    Agent for planning mode - generates complete task plans before execution.

    This is faster and more efficient than step-by-step mode for well-defined tasks.
    """

    def __init__(
        self,
        model_config: Optional[ModelConfig] = None,
        device_id: Optional[str] = None,
    ):
        """
        Initialize planning agent.

        Args:
            model_config: Configuration for the AI model
            device_id: Optional device ID for multi-device setups
        """
        self.model_config = model_config or ModelConfig()
        self.device_id = device_id
        self.model_client = ModelClient(self.model_config)

    def generate_plan(self, task: str, include_screenshot: bool = True) -> TaskPlan:
        """
        Generate a complete execution plan for the task.

        Args:
            task: Natural language task description
            include_screenshot: Whether to include current screen in context

        Returns:
            TaskPlan object containing the complete plan

        Raises:
            ValueError: If plan generation fails or response is invalid
        """
        logger.info(f"Generating plan for task: {task}")

        # Get current screen state if requested
        screenshot = None
        current_app = "Unknown"
        screen_width = 1080
        screen_height = 2400

        if include_screenshot:
            try:
                screenshot = get_screenshot(self.device_id)
                current_app = get_current_app(self.device_id) or "Unknown"
                screen_width = screenshot.width
                screen_height = screenshot.height
            except Exception as e:
                logger.warning(f"Failed to get screen state: {e}")

        # Build user prompt
        user_prompt = PLANNING_USER_PROMPT_TEMPLATE.format(
            task=task,
            current_app=current_app,
            screen_width=screen_width,
            screen_height=screen_height,
        )

        # Build messages
        messages = [
            MessageBuilder.create_system_message(PLANNING_SYSTEM_PROMPT),
        ]

        if screenshot and include_screenshot:
            messages.append(
                MessageBuilder.create_user_message(
                    text=user_prompt, image_base64=screenshot.base64_data
                )
            )
        else:
            messages.append(MessageBuilder.create_user_message(text=user_prompt))

        # Get response from model (use request_json to force JSON output)
        try:
            response = self.model_client.request_json(messages)
            logger.debug(f"Model response: {response.action[:500]}...")  # Log first 500 chars
        except Exception as e:
            logger.error(f"Model request failed: {e}")
            raise ValueError(f"Failed to generate plan: {e}")

        # Parse JSON response
        try:
            plan_data = self._parse_json_response(response.action)
        except Exception as e:
            logger.error(f"Failed to parse plan: {e}")
            logger.error(f"Raw response: {response.action}")
            raise ValueError(f"Failed to parse plan: {e}")

        # 修复：处理AI返回列表的情况
        if isinstance(plan_data, list):
            # AI返回了步骤列表而不是完整的计划对象
            # 包装成标准格式，并确保每个步骤都有step_id
            logger.warning("AI returned a list instead of plan object, wrapping it")
            steps = plan_data
            # 确保每个步骤都有step_id（只处理字典类型的步骤）
            for i, step in enumerate(steps, 1):
                if isinstance(step, dict) and "step_id" not in step:
                    step["step_id"] = i
                elif not isinstance(step, dict):
                    logger.error(f"Step {i} is not a dict, type: {type(step)}, value: {step}")
                    raise ValueError(f"Invalid step format: step {i} must be a dictionary")

            plan_data = {
                "instruction": task,
                "complexity": "medium",
                "task_analysis": "AI直接返回了步骤列表",
                "overall_strategy": "按照步骤顺序执行",
                "estimated_duration_seconds": len(steps) * 10,
                "steps": steps,
                "checkpoints": [],
                "risk_points": [],
            }
        else:
            # 修复：即使是标准格式，也要确保步骤有step_id
            if "steps" in plan_data and isinstance(plan_data["steps"], list):
                for i, step in enumerate(plan_data["steps"], 1):
                    if isinstance(step, dict) and "step_id" not in step:
                        step["step_id"] = i
                        logger.warning(f"Added missing step_id={i} to step {i}")
                    elif not isinstance(step, dict):
                        logger.error(f"Step {i} is not a dict, type: {type(step)}, value: {step}")
                        raise ValueError(f"Invalid step format: step {i} must be a dictionary")

        # Validate and create plan
        try:
            plan = TaskPlan.from_dict(plan_data)
            logger.info(
                f"Generated plan with {len(plan.steps)} steps, complexity: {plan.complexity}"
            )
            return plan
        except Exception as e:
            logger.error(f"Failed to create plan object: {e}")
            logger.error(f"Plan data structure: {type(plan_data)}")
            logger.error(f"Plan data content: {plan_data}")
            raise ValueError(f"Invalid plan structure: {e}")

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """
        Parse JSON from model response, handling markdown code blocks.

        Args:
            response: Raw response string from model

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If JSON cannot be parsed
        """

        response = response.strip()

        # 检测特殊标签：[notool], [sensitive]
        if response.startswith("[notool]"):
            logger.warning(" AI returned [notool] - task doesn't need phone操作")
            raise ValueError(
                "Task doesn't require phone operation. "
                "This task can be answered directly without phone automation. "
                "Please use step-by-step mode if you want to execute phone actions."
            )

        if response.startswith("[sensitive]"):
            logger.error("🔒 AI returned [sensitive] - sensitive operation detected")
            raise ValueError(
                "Sensitive operation detected (payment, password, login, banking app). "
                "Stopping for safety. Planning mode cannot handle sensitive operations."
            )

        # Remove markdown code blocks if present
        # Pattern 1: ```json ... ```
        json_match = re.search(r"```json\s*\n(.*?)\n```", response, re.DOTALL)
        if json_match:
            response = json_match.group(1).strip()
        else:
            # Pattern 2: ``` ... ```
            json_match = re.search(r"```\s*\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                response = json_match.group(1).strip()

        # Clean up JSON (remove comments)
        # Remove // comments
        response = re.sub(r"//[^\n]*", "", response)
        # Remove /* */ comments
        response = re.sub(r"/\*.*?\*/", "", response, flags=re.DOTALL)

        # Try to parse JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            # Try to find JSON object in the response
            # Look for the first { and last }
            start_idx = response.find("{")
            end_idx = response.rfind("}")

            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx : end_idx + 1]
                # Clean this substring too
                json_str = re.sub(r"//[^\n]*", "", json_str)
                json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            # 容错处理：如果AI返回了自然语言而不是JSON，尝试从文本中提取关键信息
            logger.warning(" AI returned non-JSON response, attempting to extract action from text")

            # 检查是否包含 do() 调用（Vision模式的格式）
            do_match = re.search(r'do\(action="(\w+)"(?:,\s*(\w+)="([^"]+)")?\)', response)
            if do_match:
                action = do_match.group(1)
                param_name = do_match.group(2)
                param_value = do_match.group(3)

                logger.info(f"📝 Extracted action from text: {action}, {param_name}={param_value}")

                # 构造一个简单的计划
                if action == "Launch" and param_name in ["app", "app_name"]:
                    return {
                        "instruction": f"打开{param_value}",
                        "complexity": "simple",
                        "task_analysis": "单步任务：启动应用",
                        "overall_strategy": f"启动{param_value}应用",
                        "estimated_duration_seconds": 5,
                        "steps": [
                            {
                                "step_id": 1,
                                "action_type": "LAUNCH",
                                "target_description": f"启动{param_value}",
                                "expected_result": f"{param_value}应用打开",
                                "reasoning": "用户要求打开应用",
                                "parameters": {"app_name": param_value},
                            }
                        ],
                        "checkpoints": [],
                        "risk_points": [],
                    }

            raise ValueError(f"Cannot parse JSON: {e}")

    def validate_plan(self, plan: TaskPlan) -> tuple[bool, Optional[str]]:
        """
        Validate a task plan for correctness.

        Args:
            plan: TaskPlan to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        if not plan.instruction:
            return False, "Plan must have an instruction"

        if not plan.steps or len(plan.steps) == 0:
            return False, "Plan must have at least one step"

        # Validate steps
        valid_action_types = {
            "LAUNCH",
            "TAP",
            "DOUBLE_TAP",
            "LONG_PRESS",
            "TYPE",
            "CLEAR_TEXT",
            "SWIPE",
            "BACK",
            "HOME",
            "WAIT",
            "CHECKPOINT",
        }

        for i, step in enumerate(plan.steps, 1):
            if "step_id" not in step:
                return False, f"Step {i} missing step_id"

            if "action_type" not in step:
                return False, f"Step {i} missing action_type"

            action_type = step["action_type"]
            if action_type not in valid_action_types:
                return False, f"Step {i} has invalid action_type: {action_type}"

            if "parameters" not in step:
                return False, f"Step {i} missing parameters"

            # Validate parameters for each action type
            params = step["parameters"]
            if action_type == "LAUNCH" and "app_name" not in params:
                return False, f"Step {i} LAUNCH missing app_name"

            if action_type in ("TAP", "DOUBLE_TAP") and ("x" not in params or "y" not in params):
                return False, f"Step {i} {action_type} missing coordinates"

            if action_type == "LONG_PRESS":
                if "x" not in params or "y" not in params:
                    return False, f"Step {i} LONG_PRESS missing coordinates"
                # duration_ms is optional, has default value

            if action_type == "TYPE" and "text" not in params:
                return False, f"Step {i} TYPE missing text"

            # CLEAR_TEXT has no required parameters

            if action_type == "SWIPE":
                required = ["start_x", "start_y", "end_x", "end_y"]
                if not all(k in params for k in required):
                    return False, f"Step {i} SWIPE missing coordinates"

            if action_type == "WAIT" and "seconds" not in params:
                return False, f"Step {i} WAIT missing seconds"

        return True, None
