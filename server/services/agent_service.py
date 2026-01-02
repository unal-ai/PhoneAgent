#!/usr/bin/env python3
"""
AgentService - Agent 任务管理服务

职责：
1. 任务管理（创建、执行、取消、查询）
2. Agent 调度和执行（异步包装）
3. 状态跟踪和回调通知
4. 与 DevicePool 对接
5. 截图保存和压缩
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from phone_agent.adb import get_screenshot
from phone_agent.agent import AgentConfig, PhoneAgent
from phone_agent.logging import TaskLogger  # 新增: 工程化日志系统
from phone_agent.model import ModelConfig
from server.database import crud
from server.database.session import get_db
from server.services.model_call_tracker import track_model_call  # 新增: 模型调用追踪
from server.utils.image_utils import compress_screenshot

logger = logging.getLogger(__name__)

# 截图存储目录
SCREENSHOT_DIR = "data/screenshots"


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class TaskStep:
    """任务步骤信息"""

    step_index: int  # 步骤索引
    timestamp: str  # 时间戳 ISO格式
    step_type: str  # 类型: "thought" | "action" | "observation"
    content: str  # 内容（思考内容/动作描述/观察结果）
    screenshot_path: Optional[str] = None  # 截图路径（如果有）
    duration_ms: Optional[int] = None  # 耗时（毫秒）
    tokens_used: Optional[Dict[str, int]] = (
        None  # Token消耗 {"prompt": 100, "completion": 50, "total": 150}
    )

    def to_dict(self) -> dict:
        result = {
            "step_index": self.step_index,
            "timestamp": self.timestamp,
            "step_type": self.step_type,
            "content": self.content,
            "screenshot_path": self.screenshot_path,
        }
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.tokens_used:
            result["tokens_used"] = self.tokens_used
        return result


@dataclass
class Task:
    """任务信息"""

    task_id: str  # 任务 ID
    instruction: str  # 任务指令
    device_id: Optional[str] = None  # 分配的设备 ID
    status: TaskStatus = TaskStatus.PENDING  # 任务状态

    # 执行信息
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 结果
    result: Optional[str] = None  # 最终结果
    error: Optional[str] = None  # 错误信息

    # 步骤详情（新增）
    steps: list[Dict[str, Any]] = field(default_factory=list)  # 步骤列表（每步的详细日志）
    current_step: int = 0  # 当前步骤索引

    # Token统计
    total_tokens: int = 0  # 总token消耗
    total_prompt_tokens: int = 0  # 总输入token
    total_completion_tokens: int = 0  # 总输出token

    # 模型配置
    model_config: Optional[Dict[str, Any]] = None
    model_name: Optional[str] = None  # 使用的模型名称（用于统计）
    kernel_mode: Optional[str] = None  # 使用的内核模式（xml/vision/auto/planning）

    @property
    def duration(self) -> Optional[float]:
        """任务执行时长（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        # 🔒 安全：脱敏 model_config 中的 API Key
        safe_model_config = None
        if self.model_config:
            safe_model_config = self.model_config.copy()
            if "api_key" in safe_model_config:
                # 只显示前8位和后4位，中间用星号
                api_key = safe_model_config["api_key"]
                if len(api_key) > 12:
                    safe_model_config["api_key"] = f"{api_key[:8]}...{api_key[-4:]}"
                else:
                    safe_model_config["api_key"] = "***"

        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "device_id": self.device_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "result": self.result,
            "error": self.error,
            "steps": len(self.steps),
            "model_config": safe_model_config,  # 使用脱敏后的配置
        }


class AgentCallback:
    """
    Agent 回调接口（同步版本 - 用于在线程池中运行的Agent）

    用于在任务执行过程中收集状态信息

    关键修复：
    - XML/Hybrid Agent在线程池中同步运行（run_in_executor）
    - 回调必须是同步的，通过 asyncio.run_coroutine_threadsafe 调度到事件循环
    - 否则 async 回调不会被执行，导致实时进度预览卡住
    """

    def __init__(self, task: Task, websocket_broadcast_callback=None, loop=None):
        self.task = task
        self.websocket_broadcast_callback = websocket_broadcast_callback
        self.loop = loop or asyncio.get_event_loop()  # 保存事件循环引用

    def on_step_start(self, step: int, action: str):
        """步骤开始（同步方法）"""
        # 检查任务是否已被取消
        if self.task.status == TaskStatus.CANCELLED:
            logger.warning(f" Task {self.task.task_id} cancelled, stopping execution")
            raise Exception("Task cancelled by user")

        logger.info(f"Task {self.task.task_id} Step {step} started")

        # 解析步骤信息（可能包含 thinking 和 action）
        thinking = ""
        action_data = action
        try:
            import json

            step_info = json.loads(action)
            if isinstance(step_info, dict):
                thinking = step_info.get("thinking", "")
                action_data = step_info.get("action", action)
        except (json.JSONDecodeError, TypeError):
            # 如果不是 JSON，直接使用原始字符串
            pass

        step_data = {
            "step": step,
            "thinking": thinking,  # 在步骤开始时就有 thinking
            "action": action_data,
            "status": "running",  # 初始状态为 "running"
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "screenshot": None,  # 将在步骤完成时填充
        }
        self.task.steps.append(step_data)

        # 立即广播步骤开始状态（包含 thinking）
        if self.websocket_broadcast_callback:
            try:
                logger.info(
                    f"📡 [AgentCallback] Broadcasting step start: task_id={self.task.task_id}, step={step}"
                )
                # 使用 run_coroutine_threadsafe 从同步线程调度到事件循环
                future = asyncio.run_coroutine_threadsafe(
                    self.websocket_broadcast_callback(
                        {
                            "type": "task_step_update",
                            "data": {
                                "task_id": self.task.task_id,
                                "step": step,
                                "thinking": thinking,  # 包含 thinking
                                "action": action_data,
                                "status": "running",
                                "timestamp": step_data["timestamp"],
                            },
                        }
                    ),
                    self.loop,
                )
                # Warning: 不等待结果，避免阻塞（fire-and-forget）
            except Exception as e:
                logger.error(f"Failed to broadcast step start: {e}", exc_info=True)
        else:
            logger.warning(
                f" [AgentCallback] No websocket_broadcast_callback set for task {self.task.task_id}"
            )

    def on_step_complete(self, step: int, success: bool, thinking: str = "", observation: str = ""):
        """步骤完成（同步方法，非阻塞）"""
        logger.info(f"Task {self.task.task_id} Step {step}: {'success' if success else 'failed'}")

        # 立即更新步骤状态（不等待截图）
        self._update_step_status(step, success, thinking, observation, screenshot_paths=None)

        # 异步保存截图并广播（fire-and-forget，不阻塞）
        try:
            asyncio.run_coroutine_threadsafe(
                self._save_and_broadcast_step(step, success, thinking, observation), self.loop
            )
            # Warning: 不等待结果，避免阻塞Agent执行
        except Exception as e:
            logger.error(f"Failed to schedule screenshot save for step {step}: {e}")

    async def _save_and_broadcast_step(
        self, step: int, success: bool, thinking: str, observation: str
    ):
        """保存截图并广播（异步，非阻塞）"""
        # 保存截图
        screenshot_paths = await self._save_step_screenshot(step)

        # 更新任务中的截图路径（异步完成后）
        if screenshot_paths and self.task.steps:
            last_step = self.task.steps[-1]
            step_key = last_step.get("step") if "step" in last_step else last_step.get("step_index")

            if step_key == step:
                self.task.steps[-1].update(
                    {
                        "screenshot": screenshot_paths.get("medium"),
                        "screenshot_small": screenshot_paths.get("small"),
                        "screenshot_ai": screenshot_paths.get("ai"),
                    }
                )

        # WebSocket实时推送步骤更新（包含截图）
        if self.websocket_broadcast_callback and self.task.steps:
            try:
                last_step = self.task.steps[-1]
                step_key = (
                    last_step.get("step") if "step" in last_step else last_step.get("step_index")
                )

                if step_key == step:
                    await self.websocket_broadcast_callback(
                        {
                            "type": "task_step_update",
                            "data": {
                                "task_id": self.task.task_id,
                                "step": step,
                                "thinking": thinking,
                                "action": last_step.get("action", ""),
                                "observation": observation,
                                "screenshot": (
                                    screenshot_paths.get("small") if screenshot_paths else None
                                ),
                                "success": success,
                                "status": "completed" if success else "failed",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "duration_ms": last_step.get("duration_ms"),
                                "tokens_used": last_step.get("tokens_used"),
                            },
                        }
                    )
                    logger.info(
                        f"[WebSocket] Broadcasted step complete: task_id={self.task.task_id}, step={step}, status={'completed' if success else 'failed'}"
                    )
            except Exception as e:
                logger.error(f"[WebSocket] Failed to broadcast step update: {e}", exc_info=True)

        return screenshot_paths

    def _update_step_status(
        self, step: int, success: bool, thinking: str, observation: str, screenshot_paths
    ):
        """更新步骤状态（同步）"""
        if self.task.steps and len(self.task.steps) > 0:
            # 更新最后一个步骤的状态
            last_step = self.task.steps[-1]
            # 兼容两种键名：step 或 step_index
            step_key = last_step.get("step") if "step" in last_step else last_step.get("step_index")

            if step_key == step:
                self.task.steps[-1].update(
                    {
                        "status": "completed" if success else "failed",
                        "success": success,
                        "thinking": thinking,
                        "observation": observation,
                        "screenshot": screenshot_paths.get("medium") if screenshot_paths else None,
                        "screenshot_small": (
                            screenshot_paths.get("small") if screenshot_paths else None
                        ),
                        "screenshot_ai": screenshot_paths.get("ai") if screenshot_paths else None,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            else:
                logger.warning(
                    f"Step mismatch: expected {step}, got {step_key}. Last step: {last_step}"
                )

    async def _save_step_screenshot(self, step: int) -> Optional[Dict[str, str]]:
        """
        保存步骤截图并压缩

        Returns:
            截图路径字典 {ai: path, medium: path, small: path}
        """
        try:
            # 确保截图目录存在
            task_screenshot_dir = os.path.join(SCREENSHOT_DIR, self.task.task_id)
            os.makedirs(task_screenshot_dir, exist_ok=True)

            # 获取截图
            # 将 device_id 转换为 ADB 地址 (device_6100 -> localhost:6100)
            from server.utils import device_id_to_adb_address

            device_id = self.task.device_id
            adb_address = device_id_to_adb_address(device_id)

            screenshot = await asyncio.to_thread(get_screenshot, adb_address)

            if not screenshot or not screenshot.base64_data:
                logger.warning(f"Failed to capture screenshot for step {step}")
                return None

            # 保存原始截图
            import base64

            original_path = os.path.join(task_screenshot_dir, f"step_{step:03d}_original.png")
            with open(original_path, "wb") as f:
                f.write(base64.b64decode(screenshot.base64_data))

            # 压缩截图（生成多个级别）
            compressed_paths = await asyncio.to_thread(
                compress_screenshot, original_path, task_screenshot_dir, for_ai=True
            )

            # 返回相对路径（便于前端访问）
            result = {}
            for level, path in compressed_paths.items():
                if path:
                    # 转换为相对于项目根目录的路径
                    result[level] = path.replace("\\", "/")

            logger.info(f"Screenshot saved for step {step}: {len(result)} levels")
            return result

        except Exception as e:
            logger.error(f"Failed to save screenshot for step {step}: {e}")
            return None

    async def on_task_complete(self, success: bool, result: str):
        """任务完成"""
        logger.info(f"Task {self.task.task_id}: completed with result: {result}")
        self.task.result = result
        self.task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        self.task.completed_at = datetime.now(timezone.utc)

    async def on_error(self, error: str):
        """错误"""
        import traceback

        # Get full traceback if available
        tb_str = traceback.format_exc()
        if tb_str and tb_str != "NoneType: None\n":
            detailed_error = f"{error}\n\nTraceback:\n{tb_str}"
        else:
            detailed_error = error

        logger.error(f"Task {self.task.task_id} error: {detailed_error}")
        self.task.error = detailed_error
        self.task.status = TaskStatus.FAILED
        self.task.completed_at = datetime.now(timezone.utc)


class AgentService:
    """
    Agent 服务（v3.0 - 混合模式）

    管理 Agent 任务的生命周期

    架构设计（混合模式）:
    - 运行中任务保留在内存（快速访问，频繁更新）
    - 已完成任务立即持久化并移出内存（节省内存）
    - 历史任务仅存储在数据库（无限容量）
    - 查询支持双层（内存优先，数据库兜底）

    优势:
    - 内存占用减少95%（100个→5个运行中任务）
    - 数据永不丢失（立即持久化）
    - 性能不受影响（运行时仍在内存）
    - 无需LRU清理逻辑（自动清理）
    """

    def __init__(self):
        # 仅保留运行中任务（预计5-10个）
        self.running_tasks: Dict[str, Task] = {}

        # asyncio.Task句柄管理（用于取消任务）
        self._running_task_handles: Dict[str, asyncio.Task] = {}

        # 存储运行中的 Agent 实例（用于调试和访问上下文）
        self._active_agents: Dict[str, Any] = {}

        self._lock = asyncio.Lock()
        self._websocket_broadcast_callback = None
        self.task_logger = TaskLogger(log_dir="logs")

        logger.info("AgentService initialized (Hybrid Mode: Memory for running, DB for completed)")

        # 尝试恢复已中断的任务状态
        self.recover_tasks()

    def recover_tasks(self):
        """恢复/清理异常中断的任务（启动时调用）"""
        try:
            db = next(get_db())
            try:
                # 查找所有标记为 RUNNING 的任务
                running_tasks = crud.list_tasks(db, status="running")
                count = 0
                for task in running_tasks:
                    # 标记为失败
                    logger.warning(f"Found orphaned running task {task.task_id}, marking as FAILED")
                    crud.update_task(
                        db,
                        task.task_id,
                        status="failed",
                        error="Task flow interrupted (server restart)",
                        completed_at=datetime.now(timezone.utc),
                    )
                    count += 1

                if count > 0:
                    logger.info(f"Recovered {count} orphaned running tasks")

                # 查找长时间 PENDING 的任务 (例如超过1小时)
                from datetime import timedelta

                pending_tasks = crud.list_tasks(db, status="pending")
                cutoff = datetime.now(timezone.utc) - timedelta(hours=1)

                pending_count = 0
                for task in pending_tasks:
                    # 数据库时间通常是 naive UTC，需要处理时区
                    created_at = task.created_at
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)

                    if created_at < cutoff:
                        logger.warning(
                            f"Found stale pending task {task.task_id}, marking as FAILED"
                        )
                        crud.update_task(
                            db,
                            task.task_id,
                            status="failed",
                            error="Task timeout (stale pending)",
                            completed_at=datetime.now(timezone.utc),
                        )
                        pending_count += 1

                if pending_count > 0:
                    logger.info(f"Recovered {pending_count} stale pending tasks")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to recover tasks: {e}")

    async def create_task(
        self,
        instruction: str,
        model_config: Optional[Dict[str, Any]] = None,
        device_id: Optional[str] = None,
    ) -> str:
        """
        创建任务

        Args:
            instruction: 任务指令
            model_config: 模型配置（可选）
            device_id: 指定设备 ID（可选，不指定则自动分配）

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())

        task = Task(
            task_id=task_id, instruction=instruction, device_id=device_id, model_config=model_config
        )

        # 立即持久化到数据库（异步）
        await self._persist_task_to_db(task)

        # 添加到运行中任务（等待执行）
        async with self._lock:
            self.running_tasks[task_id] = task

        # 工程化日志
        try:
            self.task_logger.log_task_start(
                task_id=task_id,
                instruction=instruction,
                device_id=device_id or "auto",
                model_config=model_config or {},
            )
        except Exception as e:
            logger.error(f"Failed to log task start: {e}")

        logger.info(f"Task created: {task_id}, instruction: {instruction[:50]}...")
        return task_id

    async def execute_task(self, task_id: str, device_pool=None) -> bool:
        """
        执行任务

        Args:
            task_id: 任务 ID
            device_pool: 设备池（可选，用于自动分配设备）

        Returns:
            是否启动成功
        """
        import time

        start_time = time.time()
        logger.info(f"⏱️  [Task {task_id}] Starting execute_task...")

        async with self._lock:
            task = self.running_tasks.get(task_id)
            if not task:
                logger.error(f"Task not found: {task_id}")
                return False

            if task.status != TaskStatus.PENDING:
                logger.error(f"Task {task_id} cannot be executed (status: {task.status})")
                return False

            # 如果没有指定设备，从设备池获取
            if not task.device_id and device_pool:
                logger.info(f"⏱️  [Task {task_id}] Getting available device...")
                device_start = time.time()
                device = await device_pool.get_available_device()
                logger.info(f"⏱️  [Task {task_id}] Got device in {time.time() - device_start:.2f}s")
                if not device:
                    logger.error(f"No available device for task {task_id}")
                    return False
                task.device_id = device.device_id
                await device_pool.assign_task(device.device_id, task_id)

            if not task.device_id:
                logger.error(f"No device assigned for task {task_id}")
                return False

            # 更新状态
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now(timezone.utc)

            # 立即持久化状态到数据库
            db = None
            try:
                db = next(get_db())
                crud.update_task(
                    db,
                    task.task_id,
                    status="running",
                    started_at=task.started_at,
                )
            except Exception as e:
                logger.error(f"Failed to update task status to RUNNING in DB: {e}")
            finally:
                if db:
                    db.close()

        # 启动异步任务
        asyncio_task = asyncio.create_task(self._run_agent(task, device_pool))
        self._running_task_handles[task_id] = asyncio_task

        elapsed = time.time() - start_time
        logger.info(
            f"⏱️  [Task {task_id}] Task launched in {elapsed:.2f}s on device {task.device_id}"
        )
        return True

    async def _run_agent(self, task: Task, device_pool=None):
        """
        运行 Agent（内部方法）

        Args:
            task: 任务对象
            device_pool: 设备池
        """
        import time

        agent_start = time.time()
        logger.info(f"⏱️  [Task {task.task_id}] _run_agent started...")

        try:
            # 获取当前事件循环并传给回调
            loop = asyncio.get_event_loop()

            # 创建回调（传入事件循环）
            callback = AgentCallback(task, self._websocket_broadcast_callback, loop)

            # 获取设备的实际 ADB 地址（从V2扫描器）
            adb_device_id = None
            if task.device_id:
                try:
                    from server.services.device_scanner import get_device_scanner

                    scanner = get_device_scanner()
                    scanned_devices = scanner.get_scanned_devices()
                    if task.device_id in scanned_devices:
                        v2_device = scanned_devices[task.device_id]
                        adb_device_id = v2_device.adb_address
                        logger.info(f"⏱️  [Task {task.task_id}] Using device: {adb_device_id}")
                    else:
                        logger.error(
                            f"Task {task.task_id}: Device {task.device_id} not found in scanned devices"
                        )
                except Exception as e:
                    logger.error(f"Failed to get device from scanner: {e}")

            # 构建模型配置
            model_config_dict = task.model_config or {}

            # 检查任务是否已被取消
            if task.status == TaskStatus.CANCELLED:
                logger.warning(f" Task {task.task_id} cancelled before preprocessing")
                return

            # 🆕 Phase 1: 任务预处理
            from phone_agent.preprocessing import RuleEngineExecutor, TaskPreprocessor

            preprocessor = TaskPreprocessor()
            execution_plan = preprocessor.preprocess(
                instruction=task.instruction,
                current_kernel=model_config_dict.get("kernel_mode", "auto"),
            )

            logger.info(
                f"📋 [Task {task.task_id}] 预处理结果: {execution_plan.task_type.value} → "
                f"{execution_plan.executor.value} (置信度: {execution_plan.confidence:.2f})"
            )

            # 🆕 如果可以直接执行（高置信度的纯系统指令，且非复合任务）
            if (
                execution_plan.direct_action
                and execution_plan.skip_llm  # 🆕 只有skip_llm=True才完全跳过
                and execution_plan.confidence >= 0.9
                and adb_device_id
            ):

                logger.info(
                    f"[Task {task.task_id}] 规则引擎直接执行: {execution_plan.direct_action}"
                )

                rule_executor = RuleEngineExecutor(adb_device_id)
                success, message = rule_executor.execute(execution_plan.direct_action)

                if success:
                    # 记录步骤并广播（规则引擎直接执行）
                    step_timestamp = datetime.now(timezone.utc).isoformat()
                    task.steps.append(
                        {
                            "step": 0,
                            "timestamp": step_timestamp,
                            "thinking": "规则引擎识别为纯系统指令，直接执行",
                            "action": execution_plan.direct_action,
                            "observation": message,
                            "duration_ms": int(
                                (datetime.now(timezone.utc) - task.started_at).total_seconds()
                                * 1000
                            ),
                            "success": True,
                            "status": "completed",
                        }
                    )

                    # WebSocket 广播步骤更新
                    if self._websocket_broadcast_callback:
                        try:
                            await self._websocket_broadcast_callback(
                                {
                                    "type": "task_step_update",
                                    "data": {
                                        "task_id": task.task_id,
                                        "step": 0,
                                        "thinking": "规则引擎识别为纯系统指令，直接执行",
                                        "action": execution_plan.direct_action,
                                        "observation": message,
                                        "success": True,
                                        "status": "completed",
                                        "timestamp": step_timestamp,
                                    },
                                }
                            )
                        except Exception as e:
                            logger.error(f"Failed to broadcast step update: {e}")

                    # 直接执行成功
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now(timezone.utc)
                    # duration 是自动计算的 @property，不需要赋值
                    task.result = {
                        "success": True,
                        "message": message,
                        "action": execution_plan.direct_action,
                        "execution_type": "rule_engine",
                        "duration": task.duration,
                    }

                    # 保存结果
                    self._save_task_result(task)

                    # 新增: 清理内存
                    await self._cleanup_completed_task(task.task_id)

                    # 输出统计
                    stats = preprocessor.get_stats()
                    logger.info(
                        f"[Task {task.task_id}] 规则引擎直接执行完成 "
                        f"(耗时: {task.duration:.2f}s)"
                    )
                    logger.info(
                        f"📊 预处理统计: 总任务={stats['total']}, "
                        f"直接执行={stats['direct_execution']} ({stats['direct_execution_percentage']})"
                    )

                    return
                else:
                    # 直接执行失败，降级到正常流程
                    logger.warning(
                        f" [Task {task.task_id}] 规则引擎执行失败: {message}, "
                        f"降级到 {execution_plan.fallback.value}"
                    )
                    # 继续走正常流程

            # 再次检查任务是否已被取消
            if task.status == TaskStatus.CANCELLED:
                logger.warning(f" Task {task.task_id} cancelled before compound task execution")
                return

            # 🆕 复合任务处理：先执行系统命令部分，再继续LLM流程
            elif (
                execution_plan.direct_action
                and not execution_plan.skip_llm  # 复合任务
                and execution_plan.confidence >= 0.85
                and adb_device_id
            ):

                logger.info(
                    f"[Task {task.task_id}] 复合任务：先执行系统命令 {execution_plan.direct_action}"
                )

                rule_executor = RuleEngineExecutor(adb_device_id)
                success, message = rule_executor.execute(execution_plan.direct_action)

                # 记录步骤并广播（复合任务的系统命令部分）
                step_timestamp = datetime.now(timezone.utc).isoformat()
                task.steps.append(
                    {
                        "step": 0,
                        "timestamp": step_timestamp,
                        "thinking": "复合任务：先执行系统命令部分",
                        "action": execution_plan.direct_action,
                        "observation": message,
                        "duration_ms": int(
                            (datetime.now(timezone.utc) - task.started_at).total_seconds() * 1000
                        ),
                        "success": success,
                        "status": "completed" if success else "failed",
                    }
                )

                # WebSocket 广播步骤更新
                if self._websocket_broadcast_callback:
                    try:
                        await self._websocket_broadcast_callback(
                            {
                                "type": "task_step_update",
                                "data": {
                                    "task_id": task.task_id,
                                    "step": 0,
                                    "thinking": "复合任务：先执行系统命令部分",
                                    "action": execution_plan.direct_action,
                                    "observation": message,
                                    "success": success,
                                    "status": "completed" if success else "failed",
                                    "timestamp": step_timestamp,
                                },
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to broadcast step update: {e}")

                if success:
                    logger.info(f"[Task {task.task_id}] 系统命令执行成功，继续LLM流程处理后续任务")
                    # 等待应用启动
                    import time

                    time.sleep(2)
                else:
                    logger.warning(f" [Task {task.task_id}] 系统命令执行失败: {message}")
                # 继续执行LLM流程（无论成败）

            # 从字典中提取 ModelConfig 支持的参数
            # phone_agent.model.ModelConfig 不支持 'provider' 参数
            model_params = {}

            # 初始化配置
            from server.config import Config
            config = Config()

            # API Key（必需）
            if "api_key" in model_config_dict:
                model_params["api_key"] = model_config_dict["api_key"]
            else:
                # 如果没有提供，尝试使用环境变量
                if config.ZHIPU_API_KEY:
                    model_params["api_key"] = config.ZHIPU_API_KEY
                    logger.info("Using ZHIPU_API_KEY from environment")
                else:
                    raise ValueError("未配置API Key，请在.env中设置ZHIPU_API_KEY或在创建任务时提供")

            # Base URL（修复404错误 - 默认使用智谱AI地址）
            if "base_url" in model_config_dict:
                model_params["base_url"] = model_config_dict["base_url"]
            else:
                # 默认使用智谱AI的API地址
                model_params["base_url"] = "https://open.bigmodel.cn/api/paas/v4/"
                logger.info("Using default base_url: https://open.bigmodel.cn/api/paas/v4/")

            # Model Name
            if "model_name" in model_config_dict:
                model_params["model_name"] = model_config_dict["model_name"]
            else:
                # 🆕 使用模型选择器根据内核模式动态选择模型
                kernel_mode = model_config_dict.get("kernel_mode", "auto")

                from phone_agent.model.selector import select_model_for_kernel

                selected_model = select_model_for_kernel(kernel_mode)

                model_params["model_name"] = selected_model
                logger.info(f"🤖 自动选择模型: {kernel_mode} 内核 → {selected_model}")

            # 其他可选参数
            if "max_tokens" in model_config_dict:
                model_params["max_tokens"] = model_config_dict["max_tokens"]
            if "temperature" in model_config_dict:
                model_params["temperature"] = model_config_dict["temperature"]

            # 🔒 脱敏日志：不直接打印可能包含API密钥的配置
            logger.info(f"Model config: {model_params['model_name']} @ {model_params['base_url']}")

            # 创建 ModelConfig 对象
            model_config = ModelConfig(**model_params)

            # 记录实际使用的模型名称和内核模式到Task对象（用于统计）
            task.model_name = model_params["model_name"]
            # Warning: 已废弃XML/混合内核，统一使用vision
            task.kernel_mode = "vision"  # 强制设置为vision，不再使用auto/xml

            # 构建 Agent 配置
            agent_config = AgentConfig(
                device_id=adb_device_id,  # 使用 ADB 地址而不是逻辑设备 ID
                max_steps=model_config_dict.get("max_steps", 100),
                verbose=True,
                max_history_images=model_config_dict.get("max_history_images", config.MAX_HISTORY_IMAGES),
            )

            # 获取内核模式
            kernel_mode = model_config_dict.get("kernel_mode", "auto")
            logger.info(f"⏱️  [Task {task.task_id}] Kernel mode: {kernel_mode}")

            # Warning: 已废弃：XML和混合内核（稳定性差，已移除）
            # 详见 PROJECT_ASSESSMENT.md 和 ROADMAP.md
            # 现在统一使用Vision内核（PhoneAgent），它更稳定且经过充分测试
            if False:  # kernel_mode in ["xml", "auto"]:  # DEPRECATED
                # 🗑️ 废弃：使用混合智能体（支持XML和Vision）
                from phone_agent.kernel import ExecutionMode, HybridAgent, HybridConfig

                # 映射内核模式
                mode_map = {
                    "xml": ExecutionMode.XML,
                    "vision": ExecutionMode.VISION,
                    "auto": ExecutionMode.AUTO,
                }
                execution_mode = mode_map.get(kernel_mode, ExecutionMode.AUTO)

                logger.info(
                    f"⏱️  [Task {task.task_id}] Creating HybridAgent with mode {execution_mode.value}..."
                )

                hybrid_config = HybridConfig(
                    mode=execution_mode,
                    device_id=adb_device_id,
                    max_steps=model_config_dict.get("max_steps", 50),
                    verbose=True,
                )

                # 创建异步回调
                async_callback = AgentCallback(
                    task=task, websocket_broadcast_callback=self._websocket_broadcast_callback
                )

                # 🆕 使用同步适配器包装异步回调（传递事件循环以支持实时广播）
                from phone_agent.kernel import AsyncStepCallback

                loop = asyncio.get_event_loop()
                sync_callback = AsyncStepCallback(async_callback, loop=loop)

                agent = HybridAgent(
                    model_config=model_config,
                    config=hybrid_config,
                    step_callback=sync_callback,  # 🆕 传递同步适配器
                )

                # 再次检查任务是否已被取消（Agent执行前的最后一次检查）
                if task.status == TaskStatus.CANCELLED:
                    logger.warning(f" Task {task.task_id} cancelled before agent.run()")
                    return

                logger.info(f"⏱️  [Task {task.task_id}] Running HybridAgent...")

                # 使用可取消的包装器运行agent
                try:
                    result = await loop.run_in_executor(None, agent.run, task.instruction)
                except asyncio.CancelledError:
                    logger.warning(f" Task {task.task_id} was cancelled during execution")
                    task.status = TaskStatus.CANCELLED
                    task.error = "Task cancelled by user"
                    task.completed_at = datetime.now(timezone.utc)
                    return  # 提前退出

                # 检查是否在执行期间被取消
                if task.status == TaskStatus.CANCELLED:
                    logger.warning(f" Task {task.task_id} was cancelled")
                    return

                # 🆕 实时广播版本不需要flush（已在每步自动广播）
                logger.debug(f"[Task {task.task_id}] All steps broadcasted in real-time")

                # 处理结果
                task.result = result.get("message", "任务完成")
                task.status = TaskStatus.COMPLETED if result.get("success") else TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc)
                # duration 是自动计算的 @property，不需要赋值

                # 广播任务完成状态
                if self._websocket_broadcast_callback:
                    try:
                        await self._websocket_broadcast_callback(
                            {
                                "type": "task_status_change",
                                "data": {
                                    "task_id": task.task_id,
                                    "status": task.status.value,
                                    "message": task.result,
                                    "timestamp": task.completed_at.isoformat(),
                                    "duration": task.duration,
                                },
                            }
                        )
                        logger.info(f"Broadcasted task completion: {task.task_id}")
                    except Exception as e:
                        logger.error(f"Failed to broadcast task completion: {e}")

                # 记录步骤信息（简化版）
                task.steps.append(
                    {
                        "step": 0,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "thinking": f"使用{result.get('mode', 'unknown')}模式执行",
                        "action": {"action": "complete", "message": task.result},
                        "success": result.get("success"),
                        "cost_estimate": result.get("cost_estimate", 0),
                    }
                )

                logger.info(f"[Task {task.task_id}] HybridAgent completed: {task.result}")

            else:
                # 使用传统Vision Agent
                logger.info(f"⏱️  [Task {task.task_id}] Creating PhoneAgent (Vision mode)...")

                # 创建异步回调
                loop = asyncio.get_event_loop()  # 先获取事件循环
                async_callback = AgentCallback(
                    task=task,
                    websocket_broadcast_callback=self._websocket_broadcast_callback,
                    loop=loop,  # 传递事件循环，确保回调能正确广播
                )

                # 🆕 使用同步适配器包装异步回调（传递事件循环以支持实时广播）
                from phone_agent.kernel import AsyncStepCallback

                sync_callback = AsyncStepCallback(async_callback, loop=loop)

                agent = PhoneAgent(
                    model_config=model_config,
                    agent_config=agent_config,
                    step_callback=sync_callback,  # 🆕 传递回调
                )

                # Store active agent instance for context retrieval
                self._active_agents[task.task_id] = agent

                logger.info(f"⏱️  [Task {task.task_id}] Starting agent step-by-step execution...")
                agent_run_start = time.time()

                # 逐步执行Agent，记录每步的token消耗和耗时
                loop = asyncio.get_event_loop()
                step_index = 0
                is_first = True
                result_message = None
                consecutive_failures = 0  # 🆕 连续失败计数器

                while step_index < agent_config.max_steps:
                    # 检查任务是否被取消
                    if task.status == TaskStatus.CANCELLED:
                        logger.warning(f" Task {task.task_id} cancelled, stopping execution")
                        result_message = "Task cancelled by user"
                        break

                    # 🆕 检查连续失败
                    if consecutive_failures >= 5:
                        logger.error(f"❌ Task {task.task_id} aborted: 5 consecutive failures")
                        result_message = "Task aborted due to 5 consecutive operation failures"
                        # 标记最后一步失败以便记录
                        if task.steps:
                            task.steps[-1]["status"] = "failed"
                        break

                    step_start = time.time()

                    # 执行单步（在线程池中运行同步方法）
                    if is_first:
                        step_result = await loop.run_in_executor(None, agent.step, task.instruction)
                        is_first = False
                    else:
                        step_result = await loop.run_in_executor(None, agent.step, None)

                    # 🆕 更新连续失败计数器
                    if step_result.success:
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        logger.warning(f"⚠️ Action failed ({consecutive_failures}/5): {step_result.action}")

                    step_end = time.time()
                    duration_ms = int((step_end - step_start) * 1000)

                    # 🛡️ 实时持久化上下文：防止服务重启导致日志丢失
                    self._save_context_to_file(task.task_id)

                    # 累计token消耗
                    if step_result.usage:
                        task.total_prompt_tokens += step_result.usage.get("prompt_tokens", 0)
                        task.total_completion_tokens += step_result.usage.get(
                            "completion_tokens", 0
                        )
                        task.total_tokens += step_result.usage.get("total_tokens", 0)

                        # 新增: 记录模型调用统计（异步，不阻塞）
                        try:
                            await track_model_call(
                                task_id=task.task_id,
                                model_name=task.model_name or "unknown",
                                kernel_mode=task.kernel_mode,
                                usage=step_result.usage,
                                latency_ms=duration_ms,
                                success=step_result.success,
                            )
                        except Exception as e:
                            logger.error(f"Failed to track model call: {e}")

                    # 记录步骤详情（使用step而不是step_index，保持一致性）
                    step_timestamp = datetime.now(timezone.utc).isoformat()
                    task.steps.append(
                        {
                            "step": step_index,
                            "timestamp": step_timestamp,
                            "thinking": step_result.thinking,
                            "action": step_result.action,
                            "duration_ms": duration_ms,
                            "tokens_used": step_result.usage,
                            "success": step_result.success,
                            "status": "running",  # 初始状态
                        }
                    )

                    # 立即广播步骤开始状态（包含 thinking 和 action）
                    if self._websocket_broadcast_callback:
                        try:
                            await self._websocket_broadcast_callback(
                                {
                                    "type": "task_step_update",
                                    "data": {
                                        "task_id": task.task_id,
                                        "step": step_index,
                                        "thinking": step_result.thinking,
                                        "action": step_result.action,
                                        "success": step_result.success,
                                        "status": "running",  # 初始状态
                                        "timestamp": step_timestamp,
                                        "duration_ms": duration_ms,
                                        "tokens_used": step_result.usage,
                                    },
                                }
                            )
                            logger.info(
                                f"[WebSocket] Broadcasted step start: task_id={task.task_id}, step={step_index}"
                            )
                        except Exception as e:
                            logger.error(
                                f"[WebSocket] Failed to broadcast step start: {e}", exc_info=True
                            )

                    logger.info(
                        f"⏱️  [Task {task.task_id}] Step {step_index}: {duration_ms}ms, tokens: {step_result.usage}"
                    )

                    # 保存截图并更新步骤状态为 completed
                    # on_step_complete 是同步方法，不需要 await
                    async_callback.on_step_complete(
                        step_index,
                        step_result.success,
                        step_result.thinking,
                        str(step_result.action) if step_result.action else "",
                    )

                    # 新增: 工程化日志 - 记录每一步
                    try:
                        # 获取最新的截图路径
                        screenshot_path = None
                        if task.steps and len(task.steps) > step_index:
                            screenshot_path = task.steps[step_index].get("screenshot")

                        self.task_logger.log_step(
                            task_id=task.task_id,
                            step=step_index,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            thinking=step_result.thinking,
                            action=(
                                step_result.action
                                if isinstance(step_result.action, dict)
                                else {"action": str(step_result.action)}
                            ),
                            observation=str(step_result.action) if step_result.action else "",
                            screenshot_path=screenshot_path,
                            performance={
                                "step_duration": duration_ms / 1000,
                                "inference_time": duration_ms / 1000,  # 可以更精确计算
                            },
                            tokens_used=step_result.usage,
                        )
                    except Exception as e:
                        logger.error(f"Failed to log step: {e}")

                    # 检查是否完成
                    if step_result.finished:
                        result_message = step_result.message or "Task completed"
                        break

                    step_index += 1

                if result_message is None:
                    result_message = "Max steps reached"

                logger.info(
                    f"⏱️  [Task {task.task_id}] Agent execution completed in {time.time() - agent_run_start:.2f}s"
                )
                logger.info(
                    f"📊 [Task {task.task_id}] Total tokens: {task.total_tokens} (prompt: {task.total_prompt_tokens}, completion: {task.total_completion_tokens})"
                )

                # 完成回调（同步方法）
                # on_task_complete 需要改为异步调用或直接处理状态
                # 直接更新任务状态和广播
                task.status = TaskStatus.COMPLETED
                task.result = result_message
                task.completed_at = datetime.now(timezone.utc)
                # duration 是自动计算的 @property，不需要赋值

                # 广播任务完成状态
                if self._websocket_broadcast_callback:
                    try:
                        await self._websocket_broadcast_callback(
                            {
                                "type": "task_status_change",
                                "data": {
                                    "task_id": task.task_id,
                                    "status": TaskStatus.COMPLETED.value,
                                    "message": result_message,
                                    "timestamp": task.completed_at.isoformat(),
                                    "duration": task.duration,
                                },
                            }
                        )
                        logger.info(
                            f"[WebSocket] Broadcasted task status change: task_id={task.task_id}, status=COMPLETED"
                        )
                    except Exception as e:
                        logger.error(
                            f"[WebSocket] Failed to broadcast task completion: {e}", exc_info=True
                        )

                logger.info(f"Task {task.task_id} completed successfully (Vision mode)")

                # 新增: 工程化日志 - 记录任务完成
                try:
                    self.task_logger.log_task_complete(
                        task_id=task.task_id,
                        status="success",
                        result_message=result_message,
                        total_steps=step_index + 1,
                        total_time=time.time() - agent_start,
                        total_tokens=task.total_tokens,
                    )
                    logger.info(f"Task completion logged to JSONL: {task.task_id}")
                except Exception as e:
                    logger.error(f"Failed to log task completion: {e}")

        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)

            # 直接更新任务状态（不使用 callback.on_error，它是同步方法）
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)
            # duration 是自动计算的 @property，不需要赋值

            # 广播任务失败状态
            if self._websocket_broadcast_callback:
                try:
                    await self._websocket_broadcast_callback(
                        {
                            "type": "task_status_change",
                            "data": {
                                "task_id": task.task_id,
                                "status": TaskStatus.FAILED.value,
                                "error": str(e),
                                "timestamp": task.completed_at.isoformat(),
                                "duration": task.duration,
                            },
                        }
                    )
                except Exception as broadcast_error:
                    logger.error(f"Failed to broadcast task failure: {broadcast_error}")

            # 新增: 工程化日志 - 记录任务失败
            try:
                self.task_logger.log_task_complete(
                    task_id=task.task_id,
                    status="failed",
                    result_message=str(e),
                    total_steps=len(task.steps),
                    total_time=time.time() - agent_start if "agent_start" in locals() else 0,
                    total_tokens=task.total_tokens,
                )
            except Exception as log_error:
                logger.error(f"Failed to log task failure: {log_error}")

        finally:
            # 持久化任务结果到数据库
            try:
                db = next(get_db())
                try:
                    crud.update_task(
                        db,
                        task_id=task.task_id,
                        status=task.status.value,
                        started_at=task.started_at,
                        completed_at=task.completed_at,
                        result=task.result,
                        error=task.error,
                        steps_count=len(task.steps),
                        steps_detail=json.dumps(task.steps, ensure_ascii=False),
                        total_tokens=task.total_tokens,
                        total_prompt_tokens=task.total_prompt_tokens,
                        total_completion_tokens=task.total_completion_tokens,
                    )
                    logger.info(f"Task result persisted: {task.task_id}")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Failed to persist task result: {e}")

            # 清理
            # 新增: 清理已完成任务（移出内存）
            # 新增: 清理已完成任务（移出内存）
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                # 暂时禁用自动清理，以便前端调试面板可以查看历史上下文
                logger.info(f"Task {task.task_id} completed/failed, keeping context in memory for debugging")
                # await self._cleanup_completed_task(task.task_id)
            else:
                # 仅清理asyncio句柄，保留运行中任务
                if task.task_id in self._running_task_handles:
                    del self._running_task_handles[task.task_id]

            # 释放设备
            if device_pool and task.device_id:
                success = task.status == TaskStatus.COMPLETED
                await device_pool.complete_task(task.device_id, success=success)

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        注意：由于Agent在线程池中运行，取消操作可能需要等待当前步骤完成

        Args:
            task_id: 任务 ID

        Returns:
            是否取消成功
        """
        task = self.running_tasks.get(task_id)
        if not task:
            logger.error(f"Task not found: {task_id}")
            return False

        # 允许取消 PENDING 或 RUNNING 状态的任务
        if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            logger.error(f"Task {task_id} cannot be cancelled (status: {task.status})")
            return False

        async with self._lock:
            # 标记任务为已取消（Agent会在下一步检查此标志）
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)
            task.error = "Task cancelled by user"
            logger.warning(f" Task {task_id} marked as cancelled")

            # 持久化到数据库（关键修复：确保取消的任务被保存）
            try:
                await self._persist_task_to_db(task)
                logger.info(f"Task {task_id} persisted to database after cancellation")
            except Exception as e:
                logger.error(f"Failed to persist cancelled task to database: {e}")

            # 取消异步任务（尽力而为）
            if task_id in self._running_task_handles:
                try:
                    self._running_task_handles[task_id].cancel()
                    logger.info(f"Cancelled async task: {task_id}")
                except Exception as e:
                    logger.error(f"Failed to cancel async task {task_id}: {e}")

            # 从运行中任务列表移除（让任务进入历史记录）
            if task_id in self.running_tasks:
                self.running_tasks.pop(task_id)
                logger.info(f"Removed task {task_id} from running tasks")

        # 广播任务取消事件
        if self._websocket_broadcast_callback:
            try:
                await self._websocket_broadcast_callback(
                    {
                        "type": "task_cancelled",
                        "data": {
                            "task_id": task_id,
                            "status": "cancelled",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    }
                )
            except Exception as e:
                logger.error(f"Failed to broadcast task cancellation: {e}")

        return True

    def set_websocket_broadcast_callback(self, callback):
        """设置WebSocket广播回调"""
        self._websocket_broadcast_callback = callback
        logger.info(f"WebSocket broadcast callback set: {callback}")

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务（同步版本，兼容旧代码）

        Args:
            task_id: 任务 ID

        Returns:
            任务对象
        """
        # 仅查询运行中任务（内存）
        return self.running_tasks.get(task_id)

    async def get_task_async(self, task_id: str) -> Optional[Task]:
        """
        获取任务（异步版本，支持数据库查询）

        Args:
            task_id: 任务 ID

        Returns:
            任务对象
        """
        # Layer 1: 查询运行中任务（内存，快速）
        if task_id in self.running_tasks:
            return self.running_tasks[task_id]

        # Layer 2: 查询数据库（历史任务）
        return await self._get_task_from_db(task_id)

    def list_tasks(
        self, status: Optional[TaskStatus] = None, limit: int = 100, offset: int = 0
    ) -> list[Task]:
        """
        列出任务（同步版本，仅运行中任务）

        Args:
            status: 筛选状态（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            任务列表
        """
        tasks = list(self.running_tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        # 按创建时间倒序排序
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return tasks[offset : offset + limit]

    async def list_tasks_async(
        self, status: Optional[TaskStatus] = None, limit: int = 100, offset: int = 0
    ) -> list[Task]:
        """
        列出任务（异步版本，支持数据库查询）

        Args:
            status: 筛选状态（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            任务列表
        """
        # 直接从数据库查询（包含所有历史任务）
        return await self._list_tasks_from_db(status, limit, offset)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息（从数据库）

        Returns:
            统计数据字典
        """

        def _get_stats():
            db = next(get_db())
            try:
                all_tasks = crud.list_tasks(db, limit=10000)
                total = len(all_tasks)
                pending = sum(1 for t in all_tasks if t.status == "pending")
                running = sum(1 for t in all_tasks if t.status == "running")
                completed = sum(1 for t in all_tasks if t.status == "completed")
                failed = sum(1 for t in all_tasks if t.status == "failed")
                cancelled = sum(1 for t in all_tasks if t.status == "cancelled")

                # 计算平均执行时间
                durations = []
                for t in all_tasks:
                    if t.started_at and t.completed_at:
                        duration = (t.completed_at - t.started_at).total_seconds()
                        durations.append(duration)

                avg_duration = sum(durations) / len(durations) if durations else 0

                return {
                    "total_tasks": total,
                    "pending": pending,
                    "running": running,
                    "completed": completed,
                    "failed": failed,
                    "cancelled": cancelled,
                    "success_rate": (
                        (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
                    ),
                    "avg_duration": avg_duration,
                    "memory_tasks": len(self.running_tasks),  # 新增: 内存中任务数
                }
            finally:
                db.close()

        return _get_stats()

    # ========== 数据库辅助方法 ==========

    async def _persist_task_to_db(self, task: Task):
        """持久化任务到数据库（创建或更新）"""

        def _persist():
            db = next(get_db())
            try:
                existing = crud.get_task(db, task.task_id)
                if existing:
                    logger.info(
                        f"💾 Updating task in database: {task.task_id}, status={task.status.value}, steps={len(task.steps)}"
                    )
                    crud.update_task(
                        db,
                        task.task_id,
                        status=task.status.value,
                        started_at=task.started_at,
                        completed_at=task.completed_at,
                        result=task.result,
                        error=task.error,
                        steps_count=len(task.steps),
                        steps_detail=json.dumps(task.steps, ensure_ascii=False),
                        total_tokens=task.total_tokens,
                        total_prompt_tokens=task.total_prompt_tokens,
                        total_completion_tokens=task.total_completion_tokens,
                    )
                    logger.info(f"Task updated successfully in database: {task.task_id}")
                else:
                    logger.info(
                        f"💾 Creating new task in database: {task.task_id}, instruction={task.instruction[:50]}..."
                    )
                    crud.create_task(
                        db,
                        task_id=task.task_id,
                        instruction=task.instruction,
                        device_id=task.device_id,
                        model_config=task.model_config,
                    )
                    logger.info(f"Task created successfully in database: {task.task_id}")
            except Exception as e:
                logger.error(
                    f"Failed to persist task {task.task_id} to database: {e}", exc_info=True
                )
                raise
            finally:
                db.close()

        await asyncio.get_event_loop().run_in_executor(None, _persist)

    async def _get_task_from_db(self, task_id: str) -> Optional[Task]:
        """从数据库获取任务"""

        def _get():
            db = next(get_db())
            try:
                db_task = crud.get_task(db, task_id)
                if not db_task:
                    return None

                task = Task(
                    task_id=db_task.task_id,
                    instruction=db_task.instruction,
                    device_id=db_task.device_id,
                    model_config=json.loads(db_task.model_config) if db_task.model_config else None,
                )
                task.status = TaskStatus(db_task.status)
                task.created_at = (
                    db_task.created_at.replace(tzinfo=timezone.utc)
                    if db_task.created_at
                    else datetime.now(timezone.utc)
                )
                task.started_at = (
                    db_task.started_at.replace(tzinfo=timezone.utc) if db_task.started_at else None
                )
                task.completed_at = (
                    db_task.completed_at.replace(tzinfo=timezone.utc)
                    if db_task.completed_at
                    else None
                )
                task.result = db_task.result
                task.error = db_task.error
                task.steps = json.loads(db_task.steps_detail) if db_task.steps_detail else []
                task.total_tokens = db_task.total_tokens or 0
                task.total_prompt_tokens = db_task.total_prompt_tokens or 0
                task.total_completion_tokens = db_task.total_completion_tokens or 0
                return task
            finally:
                db.close()

        return await asyncio.get_event_loop().run_in_executor(None, _get)

    async def _list_tasks_from_db(
        self, status: Optional[TaskStatus] = None, limit: int = 100, offset: int = 0
    ) -> list[Task]:
        """从数据库列出任务"""

        def _list():
            db = next(get_db())
            try:
                db_tasks = crud.list_tasks(
                    db, status=status.value if status else None, limit=limit, offset=offset
                )

                tasks = []
                for db_task in db_tasks:
                    task = Task(
                        task_id=db_task.task_id,
                        instruction=db_task.instruction,
                        device_id=db_task.device_id,
                        model_config=(
                            json.loads(db_task.model_config) if db_task.model_config else None
                        ),
                    )
                    task.status = TaskStatus(db_task.status)
                    task.created_at = (
                        db_task.created_at.replace(tzinfo=timezone.utc)
                        if db_task.created_at
                        else datetime.now(timezone.utc)
                    )
                    task.started_at = (
                        db_task.started_at.replace(tzinfo=timezone.utc)
                        if db_task.started_at
                        else None
                    )
                    task.completed_at = (
                        db_task.completed_at.replace(tzinfo=timezone.utc)
                        if db_task.completed_at
                        else None
                    )
                    task.result = db_task.result
                    task.error = db_task.error
                    task.steps = json.loads(db_task.steps_detail) if db_task.steps_detail else []
                    task.total_tokens = db_task.total_tokens or 0
                    tasks.append(task)

                return tasks
            finally:
                db.close()

        return await asyncio.get_event_loop().run_in_executor(None, _list)

    async def _cleanup_completed_task(self, task_id: str):
        """清理已完成任务（移出内存）"""
        async with self._lock:
            task = self.running_tasks.get(task_id)
            if not task:
                return

            # 1. 保存任务上下文到文件（新增：在清理前保存上下文）
            self._save_context_to_file(task_id)

            # 2. 最终持久化到数据库
            await self._persist_task_to_db(task)

            # 2. 从内存移除
            del self.running_tasks[task_id]

            # 3. 清理asyncio句柄
            if task_id in self._running_task_handles:
                del self._running_task_handles[task_id]

            # 4. 清理 active agent 实例
            if task_id in self._active_agents:
                del self._active_agents[task_id]
                logger.info(f"cleaned up active agent instance for task {task_id}")

            logger.info(
                f"🗑️ Task {task_id} completed and removed from memory (status: {task.status.value})"
            )

    def _save_context_to_file(self, task_id: str):
        """保存任务上下文到文件（用于调试历史任务）"""
        agent = self._active_agents.get(task_id)
        if not agent:
            return

        try:
            context = agent.context

            # Ensure directory exists
            context_dir = "data/contexts"
            os.makedirs(context_dir, exist_ok=True)

            file_path = os.path.join(context_dir, f"{task_id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(context, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved context for task {task_id} to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save context for task {task_id}: {e}")

    def get_task_context(self, task_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取任务的 LLM 上下文（支持运行中和已完成任务）

        Args:
            task_id: 任务 ID

        Returns:
            上下文列表或 None
        """
        # 1. 尝试从内存获取 (Active Agent)
        agent = self._active_agents.get(task_id)
        if agent:
            try:
                # 直接访问 PhoneAgent 的 _context 属性
                return agent.context
            except Exception as e:
                logger.error(f"Failed to get context from memory for task {task_id}: {e}")

        # 2. 尝试从文件获取 (History)
        try:
            file_path = os.path.join("data/contexts", f"{task_id}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load context from file for task {task_id}: {e}")

        return None

    def inject_comment(self, task_id: str, comment: str) -> bool:
        """
        向运行中的任务注入用户评论

        Args:
            task_id: 任务 ID
            comment: 用户评论内容

        Returns:
            是否成功注入
        """
        logger.info(f"[Inject] Attempting to inject comment for task {task_id}")
        logger.info(f"[Inject] Active agents: {list(self._active_agents.keys())}")
        
        agent = self._active_agents.get(task_id)
        if not agent:
            logger.warning(f"Cannot inject comment: task {task_id} not found in active agents")
            logger.warning(f"Available agents: {list(self._active_agents.keys())}")
            return False

        try:
            result = agent.inject_comment(comment)

            # 🆕 Log user intervention to timeline
            from datetime import datetime
            task = self.running_tasks.get(task_id)
            if task and result:
                # Create a virtual step for user input
                step_record = {
                    "step": len(task.steps),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "thinking": "👥 用户介入 (User Input)",
                    "action": {"action": "user_input", "message": comment},
                    "success": True,
                    "status": "user_input",
                    "duration_ms": 0,
                    "tokens_used": {},
                }
                task.steps.append(step_record)

                # Broadcast immediately
                if self._websocket_broadcast_callback:
                    asyncio.run_coroutine_threadsafe(
                        self._websocket_broadcast_callback(
                            {
                                "type": "task_step_update",
                                "data": {
                                    "task_id": task.task_id,
                                    **step_record,
                                },
                            }
                        ),
                        asyncio.get_event_loop(),
                    )

            logger.info(f"[Inject] Comment injected successfully: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to inject comment for task {task_id}: {e}")
            return False


# 全局实例
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """
    获取全局 AgentService 实例

    Returns:
        AgentService 实例
    """
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


if __name__ == "__main__":
    # 测试
    async def test():
        service = AgentService()

        # 创建任务
        task_id = await service.create_task(
            instruction="Open WeChat",
            model_config={
                "model_name": "glm-4.1v-thinking-flash",
                "base_url": "https://open.bigmodel.cn/api/paas/v4/",
                "api_key": "your_api_key",
            },
            device_id="localhost:6100",
        )
        print(f"Task created: {task_id}")

        # 执行任务
        success = await service.execute_task(task_id)
        print(f"Task execution started: {success}")

        # 等待完成
        await asyncio.sleep(5)

        # 获取任务状态
        task = service.get_task(task_id)
        if task:
            print(f"Task status: {task.to_dict()}")

        # 获取统计信息
        stats = service.get_stats()
        print(f"Stats: {stats}")

    asyncio.run(test())
