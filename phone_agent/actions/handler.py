#!/usr/bin/env python3
# Original: Copyright (c) 2024 ZAI Organization (Apache-2.0)
# Modified: Copyright (C) 2025 PhoneAgent Contributors (AGPL-3.0)
# Based on: https://github.com/zai-org/Open-AutoGLM

"""Action handler for processing AI model outputs."""

import time
from dataclasses import dataclass
from typing import Any, Callable

from phone_agent.adb import (
    back,
    double_tap,
    home,
    launch_app,
    long_press,
    swipe,
    tap,
)


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    should_finish: bool
    message: str | None = None
    requires_confirmation: bool = False


class ActionHandler:
    """
    Handles execution of actions from AI model output.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        confirmation_callback: Optional callback for sensitive action confirmation.
            Should return True to proceed, False to cancel.
        takeover_callback: Optional callback for takeover requests (login, captcha).
    """

    def __init__(
        self,
        device_id: str | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ):
        self.device_id = device_id
        self.confirmation_callback = confirmation_callback or self._default_confirmation
        self.takeover_callback = takeover_callback or self._default_takeover

    def execute(
        self, action: dict[str, Any], screen_width: int, screen_height: int
    ) -> ActionResult:
        """
        Execute an action from the AI model.

        Args:
            action: The action dictionary from the model.
            screen_width: Current screen width in pixels.
            screen_height: Current screen height in pixels.

        Returns:
            ActionResult indicating success and whether to finish.
        """
        action_type = action.get("_metadata")

        if action_type == "finish":
            return ActionResult(success=True, should_finish=True, message=action.get("message"))

        if action_type != "do":
            return ActionResult(
                success=False,
                should_finish=True,
                message=f"Unknown action type: {action_type}",
            )

        action_name = action.get("action")
        handler_method = self._get_handler(action_name)

        if handler_method is None:
            return ActionResult(
                success=False,
                should_finish=False,
                message=f"Unknown action: {action_name}",
            )

        try:
            return handler_method(action, screen_width, screen_height)
        except Exception as e:
            return ActionResult(success=False, should_finish=False, message=f"Action failed: {e}")

    def _get_handler(self, action_name: str) -> Callable | None:
        """Get the handler method for an action."""
        handlers = {
            "Launch": self._handle_launch,
            "Tap": self._handle_tap,
            "Type": self._handle_type,
            "Type_Name": self._handle_type,
            "Swipe": self._handle_swipe,
            "Back": self._handle_back,
            "Home": self._handle_home,
            "Double Tap": self._handle_double_tap,
            "Long Press": self._handle_long_press,
            "Wait": self._handle_wait,
            "Take_over": self._handle_takeover,
            "Note": self._handle_note,
            "Call_API": self._handle_call_api,
            "Interact": self._handle_interact,
            "GetInstalledApps": self._handle_get_installed_apps,
            "UpdateMemory": self._handle_update_memory,
        }
        return handlers.get(action_name)

    def _convert_relative_to_absolute(
        self, element: list[int], screen_width: int, screen_height: int
    ) -> tuple[int, int]:
        """Convert relative coordinates (0-1000) to absolute pixels."""
        x = int(element[0] / 1000 * screen_width)
        y = int(element[1] / 1000 * screen_height)
        return x, y

    def _handle_launch(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle app launch action."""
        app_name = action.get("app")
        if not app_name:
            return ActionResult(False, False, "No app name specified")

        success = launch_app(app_name, self.device_id)
        if success:
            return ActionResult(True, False)
        return ActionResult(False, False, f"App not found: {app_name}")

    def _handle_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)

        # Check for sensitive operation
        if "message" in action:
            if not self.confirmation_callback(action["message"]):
                return ActionResult(
                    success=False,
                    should_finish=True,
                    message="User cancelled sensitive operation",
                )

        tap(x, y, self.device_id)
        return ActionResult(True, False)

    def _handle_type(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle text input action."""
        text = action.get("text", "")

        # 使用智能输入（优先yadb，兜底ADB Keyboard）
        from phone_agent.adb.smart_input import smart_type_text

        success = smart_type_text(text, self.device_id)

        if success:
            return ActionResult(True, False)
        else:
            return ActionResult(False, False, "文本输入失败")

    def _handle_swipe(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle swipe action."""
        start = action.get("start")
        end = action.get("end")

        if not start or not end:
            return ActionResult(False, False, "Missing swipe coordinates")

        start_x, start_y = self._convert_relative_to_absolute(start, width, height)
        end_x, end_y = self._convert_relative_to_absolute(end, width, height)

        swipe(start_x, start_y, end_x, end_y, device_id=self.device_id)
        return ActionResult(True, False)

    def _handle_back(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle back button action."""
        back(self.device_id)
        return ActionResult(True, False)

    def _handle_home(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle home button action."""
        home(self.device_id)
        return ActionResult(True, False)

    def _handle_double_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle double tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)
        double_tap(x, y, self.device_id)
        return ActionResult(True, False)

    def _handle_long_press(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle long press action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)
        long_press(x, y, device_id=self.device_id)
        return ActionResult(True, False)

    def _handle_wait(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle wait action."""
        duration_str = action.get("duration", "1 seconds")
        try:
            duration = float(duration_str.replace("seconds", "").strip())
        except ValueError:
            duration = 1.0

        time.sleep(duration)
        return ActionResult(True, False)

    def _handle_takeover(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle takeover request (login, captcha, etc.)."""
        message = action.get("message", "User intervention required")
        self.takeover_callback(message)
        return ActionResult(True, False)

    def _handle_note(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle note action (placeholder for content recording)."""
        # This action is typically used for recording page content
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_call_api(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle API call action (placeholder for summarization)."""
        # This action is typically used for content summarization
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_interact(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle interaction request (user choice needed)."""
        # This action signals that user input is needed
        return ActionResult(True, False, message="User interaction required")

    @staticmethod
    def _default_confirmation(message: str) -> bool:
        """Default confirmation callback using console input."""
        response = input(f"Sensitive operation: {message}\nConfirm? (Y/N): ")
        return response.upper() == "Y"

    @staticmethod
    def _default_takeover(message: str) -> None:
        """Default takeover callback using console input."""
        input(f"{message}\nPress Enter after completing manual operation...")

    def _handle_get_installed_apps(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle GetInstalledApps action."""
        # 暂时只支持获取第三方应用，因为系统应用太多
        from phone_agent.adb.app_discovery import get_third_party_packages
        import asyncio

        # 这里的 execute 是同步的，但 device_pool 可能是异步的
        # 不过 adb.app_discovery 是 async 的
        # 由于 handler 方法都在同步上下文中调用 (agent.py -> action_handler.execute)
        # 我们需要在这里运行 async 代码

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        apps = loop.run_until_complete(get_third_party_packages(self.device_id))

        app_list_str = ", ".join(apps)
        return ActionResult(
            success=True, should_finish=False, message=f"Installed 3rd-party apps: {app_list_str}"
        )

    def _handle_update_memory(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle UpdateMemory action."""
        content = action.get("content", "")
        # The actual state update happens in PhoneAgent class
        return ActionResult(
            success=True, should_finish=False, message=f"Memory updated to: {content[:50]}..."
        )


def parse_action(response: str) -> dict[str, Any]:
    """
    Parse action from model response using AST (safe alternative to eval).

    Args:
        response: Raw response string from the model.

    Returns:
        Parsed action dictionary.

    Raises:
        ValueError: If the response cannot be parsed.

    Security:
        Uses AST parsing instead of eval() to prevent code injection attacks.
    """
    import ast

    response = response.strip()

    try:
        # Method 1: AST parsing (safest)
        tree = ast.parse(response, mode="eval")

        if not isinstance(tree.body, ast.Call):
            raise ValueError("Response must be a function call")

        func_name = tree.body.func.id if isinstance(tree.body.func, ast.Name) else None

        if func_name not in ["do", "finish"]:
            raise ValueError(f"Unknown function: {func_name}")

        # Extract arguments safely
        args = {}
        for keyword in tree.body.keywords:
            arg_name = keyword.arg
            # Use literal_eval to safely evaluate the value
            try:
                arg_value = ast.literal_eval(keyword.value)
            except (ValueError, SyntaxError):
                # If literal_eval fails, try to get the value as string
                if isinstance(keyword.value, ast.Constant):
                    arg_value = keyword.value.value
                elif isinstance(keyword.value, ast.List):
                    # Handle list literals like [x, y]
                    arg_value = [ast.literal_eval(el) for el in keyword.value.elts]
                else:
                    raise ValueError(f"Cannot parse argument: {arg_name}")

            args[arg_name] = arg_value

        args["_metadata"] = func_name
        return args

    except Exception as e:
        # Fallback to regex parsing for simple cases
        try:
            return _parse_action_with_regex(response)
        except Exception as fallback_error:
            raise ValueError(
                f"Failed to parse action. AST error: {e}, Regex error: {fallback_error}"
            )


def _parse_action_with_regex(response: str) -> dict[str, Any]:
    """
    Fallback regex-based parser for simple action strings.

    Args:
        response: Raw response string from the model.

    Returns:
        Parsed action dictionary.
    """
    import re

    # Match do(...) or finish(...)
    func_match = re.match(r"^(do|finish)\((.*)\)$", response, re.DOTALL)
    if not func_match:
        raise ValueError(f"Invalid action format: {response}")

    func_name = func_match.group(1)
    args_str = func_match.group(2)

    # Parse key=value pairs
    args = {}

    # Handle special patterns
    if func_name == "finish":
        # finish(message="xxx")
        message_match = re.search(r'message\s*=\s*["\'](.+?)["\']', args_str)
        if message_match:
            args["message"] = message_match.group(1)
    else:
        # Parse action, element, etc.
        # action="Launch"
        action_match = re.search(r'action\s*=\s*["\'](\w+)["\']', args_str)
        if action_match:
            args["action"] = action_match.group(1)

        # app="xxx"
        app_match = re.search(r'app\s*=\s*["\'](.+?)["\']', args_str)
        if app_match:
            args["app"] = app_match.group(1)

        # text="xxx"
        text_match = re.search(r'text\s*=\s*["\'](.+?)["\']', args_str)
        if text_match:
            args["text"] = text_match.group(1)

        # element=[x,y]
        element_match = re.search(r"element\s*=\s*\[(\d+)\s*,\s*(\d+)\]", args_str)
        if element_match:
            args["element"] = [int(element_match.group(1)), int(element_match.group(2))]

        # start=[x,y]
        start_match = re.search(r"start\s*=\s*\[(\d+)\s*,\s*(\d+)\]", args_str)
        if start_match:
            args["start"] = [int(start_match.group(1)), int(start_match.group(2))]

        # end=[x,y]
        end_match = re.search(r"end\s*=\s*\[(\d+)\s*,\s*(\d+)\]", args_str)
        if end_match:
            args["end"] = [int(end_match.group(1)), int(end_match.group(2))]

        # message="xxx"
        message_match = re.search(r'message\s*=\s*["\'](.+?)["\']', args_str)
        if message_match:
            args["message"] = message_match.group(1)

        # duration="x seconds"
        duration_match = re.search(r'duration\s*=\s*["\'](.+?)["\']', args_str)
        if duration_match:
            args["duration"] = duration_match.group(1)

    args["_metadata"] = func_name
    return args


def do(**kwargs) -> dict[str, Any]:
    """Helper function for creating 'do' actions."""
    kwargs["_metadata"] = "do"
    return kwargs


def finish(**kwargs) -> dict[str, Any]:
    """Helper function for creating 'finish' actions."""
    kwargs["_metadata"] = "finish"
    return kwargs
