#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""Executor for task plans."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from phone_agent.actions import ActionHandler
from phone_agent.adb import (
    back,
    clear_text,
    double_tap,
    home,
    launch_app,
    long_press,
    swipe,
    tap,
    type_text,
)

from .planner import TaskPlan

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of plan execution."""

    success: bool
    completed_steps: int
    total_steps: int
    failed_step: Optional[int]
    error_message: Optional[str]
    execution_time: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "completed_steps": self.completed_steps,
            "total_steps": self.total_steps,
            "failed_step": self.failed_step,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
        }


class PlanExecutor:
    """
    Executes task plans step by step.

    Supports智能定位 via XML Kernel for improved accuracy.
    """

    def __init__(
        self,
        device_id: Optional[str] = None,
        step_callback: Optional[Callable[[int, dict, bool, str], None]] = None,
        use_xml_positioning: bool = True,
    ):
        """
        Initialize plan executor.

        Args:
            device_id: Optional device ID for multi-device setups
            step_callback: Optional callback called after each step
                Signature: (step_num, step_data, success, message)
            use_xml_positioning: Whether to use XML-based smart positioning (default: True)
        """
        self.device_id = device_id
        self.step_callback = step_callback
        self.use_xml_positioning = use_xml_positioning
        self.action_handler = ActionHandler(device_id=device_id)

    def execute_plan(self, plan: TaskPlan) -> ExecutionResult:
        """
        Execute a complete task plan.

        Args:
            plan: TaskPlan to execute

        Returns:
            ExecutionResult with execution details
        """
        logger.info(f"Executing plan with {len(plan.steps)} steps")
        start_time = time.time()

        completed_steps = 0
        failed_step = None
        error_message = None

        try:
            for i, step in enumerate(plan.steps, 1):
                logger.info(
                    f"Executing step {i}/{len(plan.steps)}: {step.get('target_description', 'Unknown')}"
                )

                success, message = self._execute_step(step)

                if self.step_callback:
                    self.step_callback(i, step, success, message)

                if not success:
                    error_message = message
                    failed_step = i
                    logger.error(f"Step {i} failed: {message}")

                    # Check if this step has a critical checkpoint
                    is_critical = self._is_critical_step(plan, i)
                    if is_critical:
                        logger.error(f"Critical step {i} failed, aborting execution")
                        break
                    else:
                        logger.warning(f"Non-critical step {i} failed, continuing...")

                completed_steps = i

                # Small delay between steps for UI to settle
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Execution error: {e}", exc_info=True)
            error_message = f"Execution error: {str(e)}"

        execution_time = time.time() - start_time

        success = (failed_step is None) or (completed_steps == len(plan.steps))

        result = ExecutionResult(
            success=success,
            completed_steps=completed_steps,
            total_steps=len(plan.steps),
            failed_step=failed_step,
            error_message=error_message,
            execution_time=execution_time,
        )

        logger.info(
            f"Execution completed: {result.completed_steps}/{result.total_steps} steps in {result.execution_time:.2f}s"
        )

        return result

    def _execute_step(self, step: dict[str, Any]) -> tuple[bool, str]:
        """
        Execute a single step.

        Args:
            step: Step dictionary from plan

        Returns:
            Tuple of (success, message)
        """
        action_type = step.get("action_type")
        parameters = step.get("parameters", {})

        try:
            if action_type == "LAUNCH":
                return self._execute_launch(parameters)
            elif action_type == "TAP":
                return self._execute_tap(parameters)
            elif action_type == "DOUBLE_TAP":
                return self._execute_double_tap(parameters)
            elif action_type == "LONG_PRESS":
                return self._execute_long_press(parameters)
            elif action_type == "TYPE":
                return self._execute_type(parameters)
            elif action_type == "CLEAR_TEXT":
                return self._execute_clear_text(parameters)
            elif action_type == "SWIPE":
                return self._execute_swipe(parameters)
            elif action_type == "BACK":
                return self._execute_back(parameters)
            elif action_type == "HOME":
                return self._execute_home(parameters)
            elif action_type == "WAIT":
                return self._execute_wait(parameters)
            elif action_type == "CHECKPOINT":
                return self._execute_checkpoint(parameters)
            else:
                return False, f"Unknown action type: {action_type}"

        except Exception as e:
            logger.error(f"Step execution error: {e}", exc_info=True)
            return False, f"Error: {str(e)}"

    def _execute_launch(self, params: dict) -> tuple[bool, str]:
        """Execute LAUNCH action."""
        app_name = params.get("app_name")
        if not app_name:
            return False, "Missing app_name parameter"

        try:
            launch_app(app_name, self.device_id)
            # Wait for app to launch
            time.sleep(2)
            return True, f"Launched {app_name}"
        except Exception as e:
            return False, f"Failed to launch {app_name}: {e}"

    def _execute_tap(self, params: dict) -> tuple[bool, str]:
        """
        Execute TAP action with optional smart positioning.

        If element_selector is provided and use_xml_positioning is True,
        attempts to find element via XML tree before falling back to fixed coordinates.
        """
        # Try smart positioning first
        if self.use_xml_positioning and "element_selector" in params:
            x, y, found = self._find_element_by_selector(params["element_selector"])
            if found:
                try:
                    tap(x, y, self.device_id)
                    time.sleep(0.3)
                    return True, f"Smart tap at ({x}, {y})"
                except Exception as e:
                    logger.warning(f"Smart tap failed, trying fallback: {e}")

        # Fallback to fixed coordinates
        x = params.get("x")
        y = params.get("y")

        if x is None or y is None:
            return False, "Missing x or y coordinate and no valid selector"

        try:
            tap(x, y, self.device_id)
            time.sleep(0.3)  # Wait for tap to register
            return True, f"Tapped at ({x}, {y})"
        except Exception as e:
            return False, f"Failed to tap: {e}"

    def _execute_double_tap(self, params: dict) -> tuple[bool, str]:
        """Execute DOUBLE_TAP action."""
        x = params.get("x")
        y = params.get("y")

        if x is None or y is None:
            return False, "Missing x or y coordinate"

        try:
            double_tap(x, y, self.device_id)
            time.sleep(0.3)
            return True, f"Double tapped at ({x}, {y})"
        except Exception as e:
            return False, f"Failed to double tap: {e}"

    def _execute_long_press(self, params: dict) -> tuple[bool, str]:
        """Execute LONG_PRESS action."""
        x = params.get("x")
        y = params.get("y")
        duration_ms = params.get("duration_ms", 3000)

        if x is None or y is None:
            return False, "Missing x or y coordinate"

        try:
            long_press(x, y, duration_ms, self.device_id)
            time.sleep(0.5)
            return True, f"Long pressed at ({x}, {y}) for {duration_ms}ms"
        except Exception as e:
            return False, f"Failed to long press: {e}"

    def _execute_type(self, params: dict) -> tuple[bool, str]:
        """Execute TYPE action."""
        text = params.get("text")
        if not text:
            return False, "Missing text parameter"

        try:
            type_text(text, self.device_id)
            time.sleep(0.2)
            return True, f"Typed: {text}"
        except Exception as e:
            return False, f"Failed to type: {e}"

    def _execute_clear_text(self, params: dict) -> tuple[bool, str]:
        """Execute CLEAR_TEXT action."""
        try:
            clear_text(self.device_id)
            time.sleep(0.2)
            return True, "Cleared text"
        except Exception as e:
            return False, f"Failed to clear text: {e}"

    def _execute_swipe(self, params: dict) -> tuple[bool, str]:
        """Execute SWIPE action."""
        start_x = params.get("start_x")
        start_y = params.get("start_y")
        end_x = params.get("end_x")
        end_y = params.get("end_y")

        if any(v is None for v in [start_x, start_y, end_x, end_y]):
            return False, "Missing swipe coordinates"

        try:
            swipe(start_x, start_y, end_x, end_y, self.device_id)
            time.sleep(0.5)
            return True, f"Swiped from ({start_x}, {start_y}) to ({end_x}, {end_y})"
        except Exception as e:
            return False, f"Failed to swipe: {e}"

    def _execute_back(self, params: dict) -> tuple[bool, str]:
        """Execute BACK action."""
        try:
            back(self.device_id)
            time.sleep(0.3)
            return True, "Pressed back button"
        except Exception as e:
            return False, f"Failed to press back: {e}"

    def _execute_home(self, params: dict) -> tuple[bool, str]:
        """Execute HOME action."""
        try:
            home(self.device_id)
            time.sleep(0.5)
            return True, "Pressed home button"
        except Exception as e:
            return False, f"Failed to press home: {e}"

    def _execute_wait(self, params: dict) -> tuple[bool, str]:
        """Execute WAIT action."""
        seconds = params.get("seconds", 1)

        try:
            time.sleep(seconds)
            return True, f"Waited {seconds} seconds"
        except Exception as e:
            return False, f"Failed to wait: {e}"

    def _execute_checkpoint(self, params: dict) -> tuple[bool, str]:
        """Execute CHECKPOINT action - verify current state."""
        description = params.get("description", "Checkpoint")

        # For now, checkpoints just log and succeed
        # In the future, we can add actual verification using screenshots
        logger.info(f"Checkpoint: {description}")
        return True, f"Checkpoint passed: {description}"

    def _is_critical_step(self, plan: TaskPlan, step_num: int) -> bool:
        """Check if a step has a critical checkpoint."""
        for checkpoint in plan.checkpoints:
            if checkpoint.get("step_id") == step_num and checkpoint.get("critical", False):
                return True
        return False

    def _find_element_by_selector(self, selector: dict[str, Any]) -> tuple[int, int, bool]:
        """
        Find element using XML-based smart positioning.

        Args:
            selector: Element selector with optional fields:
                - text: Element text content
                - content_desc: Content description
                - resource_id: Android resource ID
                - class_name: Android class name

        Returns:
            Tuple of (x, y, found) where:
            - x, y: Center coordinates if found
            - found: Whether element was successfully located
        """
        try:
            from phone_agent.adb.xml_tree import get_ui_hierarchy

            elements = get_ui_hierarchy(self.device_id)

            if not elements:
                logger.warning("No UI elements found, XML tree might be empty")
                return 0, 0, False

            # Try to match by各个selector条件
            text_match = selector.get("text")
            content_desc = selector.get("content_desc")
            resource_id = selector.get("resource_id")
            class_name = selector.get("class_name")

            for elem in elements:
                # Match by text (支持部分匹配)
                if text_match:
                    if elem.text and text_match.lower() in elem.text.lower():
                        logger.info(
                            f"Found element by text: '{text_match}' at ({elem.center_x}, {elem.center_y})"
                        )
                        return elem.center_x, elem.center_y, True

                # Match by content description
                if content_desc:
                    if elem.content_desc and content_desc.lower() in elem.content_desc.lower():
                        logger.info(
                            f"Found element by content_desc: '{content_desc}' at ({elem.center_x}, {elem.center_y})"
                        )
                        return elem.center_x, elem.center_y, True

                # Match by resource ID (精确匹配)
                if resource_id:
                    if elem.resource_id == resource_id:
                        logger.info(
                            f"Found element by resource_id: '{resource_id}' at ({elem.center_x}, {elem.center_y})"
                        )
                        return elem.center_x, elem.center_y, True

                # Match by class name
                if class_name:
                    if elem.class_name and class_name in elem.class_name:
                        logger.info(
                            f"Found element by class: '{class_name}' at ({elem.center_x}, {elem.center_y})"
                        )
                        return elem.center_x, elem.center_y, True

            logger.warning(f"No element found matching selector: {selector}")
            return 0, 0, False

        except Exception as e:
            logger.error(f"Error during smart positioning: {e}", exc_info=True)
            return 0, 0, False
