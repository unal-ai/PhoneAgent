#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""
API Routes - RESTful API 路由定义

包含：
- 设备管理 API
- 任务管理 API
- 语音识别 API
- WebSocket 实时通信
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from server.api.anti_detection_config import router as anti_detection_router
from server.api.model_stats import router as model_stats_router
from server.api.planning import router as planning_router
from server.api.presets import router as presets_router
from server.api.schemas.task import CreateTaskRequest, ModelTestRequest, TaskResponse
from server.api.scrcpy import router as scrcpy_router
from server.api.speech_api import router as speech_router
from server.services import get_agent_service, get_device_pool
from server.services.agent_service import TaskStatus
from server.services.device_scanner import get_device_scanner
from server.websocket.connection_manager import get_connection_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# 注册子路由（带标签分类）

# 注册子路由（带标签分类）
# 按照功能模块分类，方便API文档查看和维护
router.include_router(speech_router, prefix="/speech", tags=["Speech"])
router.include_router(scrcpy_router, prefix="", tags=["Streaming"])
router.include_router(planning_router, prefix="", tags=["Planning"])
router.include_router(presets_router, prefix="", tags=["Presets"])
router.include_router(model_stats_router, prefix="", tags=["Stats"])
router.include_router(anti_detection_router, prefix="", tags=["Anti-Detection"])


# ============================================
# 端口管理 API
# ============================================


@router.get("/ports/status", summary="查询所有端口分配状态", tags=["🔌 端口管理"])
async def get_port_allocations():
    """获取所有端口的分配状态"""
    from server.services.port_manager import get_port_manager

    port_manager = get_port_manager()
    allocations = await port_manager.list_allocations()

    return {"allocations": allocations, "count": len(allocations)}


@router.get("/ports/{port}/status", summary="查询指定端口状态", tags=["🔌 端口管理"])
async def get_port_status(port: int):
    """查询指定端口是否被占用"""
    from server.services.port_manager import get_port_manager

    port_manager = get_port_manager()
    status = await port_manager.get_port_status(port)

    if status:
        return {
            "port": port,
            "occupied": True,
            "device_id": status["device_id"],
            "device_name": status["device_name"],
            "allocated_at": status["allocated_at"].isoformat(),
        }
    else:
        return {"port": port, "occupied": False}


@router.get("/ports/available", summary="查找可用端口", tags=["🔌 端口管理"])
async def find_available_port(start: int = 6100, end: int = 6199):
    """查找可用端口"""
    from server.services.port_manager import get_port_manager

    port_manager = get_port_manager()
    available_port = await port_manager.find_available_port(start, end)

    if available_port:
        return {"available": True, "port": available_port}
    else:
        return {"available": False, "message": f"No available ports in range {start}-{end}"}


# ============================================
# Pydantic Models (请求/响应模型)
# ============================================
# 注意：CreateTaskRequest 和 TaskResponse 已从 server.api.schemas.task 导入


class DeviceResponse(BaseModel):
    """设备响应"""

    device_id: str
    device_name: str
    frp_port: int
    adb_address: str
    status: str
    frp_connected: bool
    ws_connected: bool
    current_task: Optional[str]
    model: str
    android_version: str
    screen_resolution: str
    battery: int
    total_tasks: int
    success_tasks: int
    failed_tasks: int
    success_rate: float
    registered_at: str
    last_active: str


class StatsResponse(BaseModel):
    """统计信息响应"""

    device_stats: Dict[str, Any]
    task_stats: Dict[str, Any]


# ============================================
# 设备管理 API
# ============================================


async def get_websocket_device_status():
    """
    从WebSocket服务器查询设备连接状态（异步版本）

    返回两种映射：
    - ws_by_id: device_id -> ws_connected（主要匹配方式，格式：device_{frp_port}）
    - ws_by_port: frp_port -> ws_connected（备用匹配方式）
    """
    import os

    # 从环境变量获取WebSocket服务器地址，默认为本地
    ws_host = os.getenv("WEBSOCKET_HOST", "127.0.0.1")
    ws_port = os.getenv("WEBSOCKET_PORT", "9999")

    # 尝试多个可能的地址（包括外网IP，解决Docker/容器环境问题）
    # 优先级：环境变量配置 > 本地回环 > 外网IP（兜底）
    websocket_urls = [
        f"http://{ws_host}:{ws_port}/devices",
        "http://127.0.0.1:9999/devices",
        "http://localhost:9999/devices",
        # 兜底：尝试通过Docker网关或外网IP访问
        "http://host.docker.internal:9999/devices",  # Docker Desktop
        "http://172.17.0.1:9999/devices",  # Docker默认网关
    ]

    errors = []
    for url in websocket_urls:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=1.0) as client:  # 降低超时到1秒
                response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                # 返回设备状态映射
                ws_status = {
                    "by_id": {},  # device_id -> ws_connected
                    "by_port": {},  # frp_port -> ws_connected
                }
                for device in data.get("devices", []):
                    device_id = device.get("device_id")
                    frp_port = device.get("frp_port")
                    ws_connected = device.get("ws_connected", False)

                    # 按 device_id 映射（主要方式）
                    if device_id:
                        ws_status["by_id"][device_id] = ws_connected

                    # 按 frp_port 映射（备用方式）
                    if frp_port:
                        ws_status["by_port"][frp_port] = ws_connected

                logger.info(f"从WebSocket服务器({url})获取到设备状态: {ws_status}")
                return ws_status
            else:
                errors.append(f"{url}: HTTP {response.status_code}")
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")

    logger.error(f"所有WebSocket服务器地址都无法连接: {errors}")
    return {"by_id": {}, "by_port": {}}


@router.get("/devices/scanned", tags=["📱 设备管理"])
async def list_scanned_devices():
    """
    获取扫描到的设备列表（优化版 - 添加缓存）

    服务端主动扫描FRP端口发现的设备
    结合WebSocket连接状态
    """
    scanner = get_device_scanner()

    # 优化：直接返回缓存的设备列表，不触发新扫描
    online_devices = scanner.get_online_devices()

    # 从WebSocket服务器查询设备状态（异步）
    ws_device_status = await get_websocket_device_status()

    devices = []
    for device_id, device in online_devices.items():
        # 查询WebSocket连接状态（优先按device_id匹配，其次按frp_port匹配）
        ws_connected = ws_device_status["by_id"].get(
            device_id, False
        ) or ws_device_status[  # 按device_id匹配（device_{frp_port}格式）
            "by_port"
        ].get(
            device.frp_port, False
        )  # 按frp_port匹配（备用）

        # 只包含成功获取的字段，None值不返回
        device_data = {
            "device_id": device.device_id,
            "device_name": device.device_name,  # 使用设备名称
            "status": "online" if device.is_online else "offline",
            "frp_port": device.frp_port,
            "adb_address": device.adb_address,
            # 连接状态
            "frp_connected": True,  # 能扫描到说明FRP已连接
            "ws_connected": ws_connected,  # 从WebSocket管理器查询实际连接状态
            # 任务统计（V2暂不支持）
            "current_task": None,
            "total_tasks": 0,
            "success_tasks": 0,
            "failed_tasks": 0,
            "success_rate": 0.0,
            # 时间字段（兼容V1命名）
            "registered_at": device.discovered_at.isoformat(),
            "last_active": device.last_seen.isoformat(),
            "discovered_at": device.discovered_at.isoformat(),
            "last_seen": device.last_seen.isoformat(),
            "method": "port_scanning",  # 标识这是扫描发现的
        }

        # 只添加成功获取的字段（不为None）
        if device.model:
            device_data["model"] = device.model
        if device.android_version:
            device_data["android_version"] = device.android_version
        if device.screen_resolution:
            device_data["screen_resolution"] = device.screen_resolution
        if device.battery is not None:
            device_data["battery"] = device.battery
        if device.memory_total:
            device_data["memory_total"] = device.memory_total
        if device.memory_available:
            device_data["memory_available"] = device.memory_available
        if device.storage_total:
            device_data["storage_total"] = device.storage_total
        if device.storage_available:
            device_data["storage_available"] = device.storage_available

        devices.append(device_data)

    return {"devices": devices, "count": len(devices), "method": "active_scanning"}


# 废弃接口已删除: GET /devices -> 请使用 GET /devices/scanned


@router.get("/devices/{device_id}", tags=["📱 设备管理"])
async def get_device(device_id: str):
    """获取设备详情（从V2扫描器）"""
    from server.services.device_scanner import get_device_scanner

    scanner = get_device_scanner()
    scanned_devices = scanner.get_scanned_devices()

    if device_id not in scanned_devices:
        raise HTTPException(404, f"Device not found: {device_id}")

    device = scanned_devices[device_id]

    # 返回完整设备信息
    return {
        "device_id": device.device_id,
        "device_name": device.device_name,  # 使用device_name而不是device_id
        "status": "online" if device.is_online else "offline",
        "frp_port": device.frp_port,
        "adb_address": device.adb_address,
        "model": device.model,
        "android_version": device.android_version,
        "screen_resolution": device.screen_resolution,
        "battery": device.battery,
        "memory_total": device.memory_total,
        "memory_available": device.memory_available,
        "storage_total": device.storage_total,
        "storage_available": device.storage_available,
        "frp_connected": True,
        "ws_connected": False,
        "discovered_at": device.discovered_at.isoformat(),
        "last_seen": device.last_seen.isoformat(),
        "method": "port_scanning",
    }


class RenameDeviceRequest(BaseModel):
    """设备重命名请求"""

    device_name: str = Field(..., min_length=1, max_length=50, description="新设备名称")


@router.patch("/devices/{device_id}/name", summary="重命名设备", tags=["📱 设备管理"])
async def rename_device(device_id: str, request: RenameDeviceRequest):
    """
    更新设备名称

    用户可以为设备设置自定义名称，便于识别
    """
    from server.services.device_scanner import get_device_scanner

    device_scanner = get_device_scanner()
    success = await device_scanner.update_device_name(device_id, request.device_name)

    if not success:
        raise HTTPException(404, f"Device not found: {device_id}")

    return {
        "message": "Device renamed successfully",
        "device_id": device_id,
        "new_name": request.device_name,
    }


# ============================================
# 任务管理 API
# ============================================


@router.post("/tasks", response_model=TaskResponse, tags=["📋 任务管理"])
async def create_task(request: CreateTaskRequest):
    """
    创建任务

    支持两种模式：
    1. 指定设备ID（device_id）
    2. 自动分配（从设备池选择可用设备）
    """
    agent_service = get_agent_service()

    # 导入配置（在使用前导入）
    from server.config import Config

    config = Config()

    # 构建模型配置
    # Warning: 已废弃XML/混合内核，统一使用Vision内核
    # 如果用户未明确指定模型，让智能选择器决定
    should_use_selector = not request.ai_model or request.ai_model == "autoglm-phone"

    model_config = {
        "provider": request.ai_provider,
        "max_steps": request.max_steps or config.MAX_TASK_STEPS,  # 使用环境变量默认值
        "max_history_images": (
            request.max_history_images
            if request.max_history_images is not None
            else config.MAX_HISTORY_IMAGES
        ),
        "kernel_mode": "vision",  # 强制使用vision内核
    }
    if request.ai_base_url:
        model_config["base_url"] = request.ai_base_url

    # 只有用户明确指定非默认模型时，才传递 model_name
    if request.ai_model and request.ai_model != "autoglm-phone":
        model_config["model_name"] = request.ai_model
    # 否则让智能选择器在 agent_service._run_agent 中决定（会选择glm-4.6v-flash）

    # 使用用户提供的API Key，如果没有则从环境变量加载
    if request.ai_api_key:
        model_config["api_key"] = request.ai_api_key
    else:
        # 从 .env 文件自动加载 API Key（支持多平台：zhipu, openai, gemini, qwen, local）
        from server.utils.model_config_helper import get_model_config_from_env

        env_config = get_model_config_from_env("vision")

        if env_config["api_key"] and env_config["api_key"] != "EMPTY":
            model_config["api_key"] = env_config["api_key"]
            # 如果用户没有指定模型，也使用环境配置
            if should_use_selector and "model_name" not in model_config:
                model_config["model_name"] = env_config["model_name"]
            if "base_url" not in model_config:
                model_config["base_url"] = env_config["base_url"]
        elif config.MODEL_PROVIDER == "local":
            # 本地模型不需要 API Key
            model_config["api_key"] = "EMPTY"
            model_config["base_url"] = env_config["base_url"]
            if "model_name" not in model_config:
                model_config["model_name"] = env_config["model_name"]
        else:
            raise HTTPException(
                400,
                "未配置API Key，请在.env中设置：\n"
                "- 智谱AI: ZHIPU_API_KEY=xxx\n"
                "- OpenAI/其他: CUSTOM_API_KEY=xxx\n"
                "- 本地模型: MODEL_PROVIDER=local",
            )

    # 处理提示词卡片：拼接到指令中
    enhanced_instruction = request.instruction
    if request.prompt_card_ids and len(request.prompt_card_ids) > 0:
        from server.api.presets import prompt_cards_store

        all_cards = prompt_cards_store.load()
        selected_cards = [card for card in all_cards if card.id in request.prompt_card_ids]

        if selected_cards:
            prompt_cards_content = "\n\n===== 任务优化提示词 =====\n"
            for card in selected_cards:
                prompt_cards_content += f"\n【{card.title}】\n{card.content}\n"
            prompt_cards_content += "\n===== 提示词结束 =====\n"
            enhanced_instruction = f"{request.instruction}{prompt_cards_content}"

    # 创建任务
    task_id = await agent_service.create_task(
        instruction=enhanced_instruction,  # 使用增强后的指令
        model_config=model_config,
        device_id=request.device_id,
    )

    # 执行任务
    device_pool = get_device_pool()
    success = await agent_service.execute_task(task_id, device_pool)

    if not success:
        raise HTTPException(400, "Failed to start task execution")

    # 获取任务信息
    task = agent_service.get_task(task_id)
    if not task:
        raise HTTPException(500, "Task created but not found")

    return TaskResponse(
        task_id=task.task_id,
        instruction=task.instruction,
        device_id=task.device_id,
        status=task.status.value,
        created_at=task.created_at.isoformat(),
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        duration=task.duration,
        result=task.result,
        error=task.error,
        steps=task.steps,
    )


@router.post("/model/test", summary="测试AI模型连接", tags=["🤖 模型管理"])
async def test_model_connection(request: ModelTestRequest):
    """
    测试AI模型连接
    
    验证提供的模型配置是否有效，尝试生成简单的回复
    """
    from phone_agent.model.client import ModelClient, ModelConfig
    from server.config import Config
    from server.utils.model_config_helper import get_model_config_from_env

    config = Config()

    # 准备模型配置
    base_url = request.base_url
    api_key = request.api_key
    model_name = request.model_name

    # 如果未提供，尝试从环境变量加载
    # 类似于 create_task 中的逻辑
    if not api_key:
        env_config = get_model_config_from_env("vision")

        # 这里的逻辑需要根据provider调整，但为简单起见，我们优先使用用户提供的
        # 如果是 default/zhipu 且为空，尝试加载环境配置
        if request.provider in ["default", "zhipu"]:
            if not base_url:
                base_url = env_config.get("base_url")
            if not model_name:
                model_name = env_config.get("model_name")
            if not api_key and env_config.get("api_key") != "EMPTY":
                api_key = env_config.get("api_key")

        # 本地模型特殊处理
        if request.provider == "local" or config.MODEL_PROVIDER == "local":
            if not api_key:
                api_key = "EMPTY"
            if not base_url:
                base_url = request.base_url or env_config.get("base_url", "http://localhost:8000/v1")

    # 构建完整配置
    # 如果 model_name 依然为空，使用默认值
    if not model_name and request.provider == "zhipu":
        model_name = "glm-4-flash"
    elif not model_name and request.provider == "local":
        model_name = "vicuna-7b-v1.5"
    elif not model_name:
        model_name = "autoglm-phone"

    model_config = ModelConfig(
        base_url=base_url or "https://open.bigmodel.cn/api/paas/v4/", # 兜底默认值
        api_key=api_key or "EMPTY",
        model_name=model_name,
        max_tokens=20, # 测试只需要生成少量token
        temperature=0.1,
    )

    try:
        # 初始化客户端
        client = ModelClient(model_config)

        # 发送简单测试请求
        messages = [{"role": "user", "content": "Hi"}]
        start_time = datetime.now()
        response = client.request(messages)
        duration = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "message": "Connection successful",
            "latency_ms": int(duration * 1000),
            "response": response.raw_content[:200] + "..." if len(response.raw_content) > 200 else response.raw_content,
            "model_used": model_config.model_name
        }
    except Exception as e:
        logger.error(f"Model connection test failed: {e}")
        return {
            "success": False,
            "message": str(e),
            "error_type": type(e).__name__
        }


@router.get("/tasks", response_model=List[TaskResponse], tags=["📋 任务管理"])
async def list_tasks(status: Optional[str] = None, limit: int = 100, offset: int = 0):
    """
    获取任务列表（优化版 - 使用异步查询）

    Args:
        status: 筛选状态 (pending, running, completed, failed, cancelled)
        limit: 返回数量
        offset: 偏移量
    """
    agent_service = get_agent_service()

    # 筛选状态
    filter_status = None
    if status:
        try:
            filter_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    # 使用异步版本避免阻塞
    tasks = await agent_service.list_tasks_async(status=filter_status, limit=limit, offset=offset)

    return [
        TaskResponse(
            task_id=t.task_id,
            instruction=t.instruction,
            device_id=t.device_id,
            status=t.status.value,
            created_at=t.created_at.isoformat(),
            started_at=t.started_at.isoformat() if t.started_at else None,
            completed_at=t.completed_at.isoformat() if t.completed_at else None,
            duration=t.duration,
            result=t.result,
            error=t.error,
            steps=t.steps,  # 修复：返回完整步骤列表
            total_tokens=t.total_tokens,
            total_prompt_tokens=t.total_prompt_tokens,
            total_completion_tokens=t.total_completion_tokens,
        )
        for t in tasks
    ]


@router.get("/tasks/{task_id}", response_model=TaskResponse, tags=["📋 任务管理"])
async def get_task(task_id: str):
    """获取任务详情（优化版 - 使用异步查询）"""
    agent_service = get_agent_service()
    # 使用异步版本避免阻塞
    task = await agent_service.get_task_async(task_id)

    if not task:
        raise HTTPException(404, f"Task not found: {task_id}")

    return TaskResponse(
        task_id=task.task_id,
        instruction=task.instruction,
        device_id=task.device_id,
        status=task.status.value,
        created_at=task.created_at.isoformat(),
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        duration=task.duration,
        result=task.result,
        error=task.error,
        steps=task.steps,  # 修复：返回完整步骤列表而不是步骤数量
        total_tokens=task.total_tokens,
        total_prompt_tokens=task.total_prompt_tokens,
        total_completion_tokens=task.total_completion_tokens,
    )


@router.get("/tasks/{task_id}/steps", tags=["📋 任务管理"])
async def get_task_steps(task_id: str):
    """获取任务的详细步骤信息"""
    agent_service = get_agent_service()
    task = agent_service.get_task(task_id)

    if not task:
        raise HTTPException(404, f"Task not found: {task_id}")

    return {
        "task_id": task.task_id,
        "instruction": task.instruction,
        "status": task.status.value,
        "current_step": task.current_step,
        "total_steps": len(task.steps),
        "steps": task.steps,  # 返回完整的步骤列表（包含token和耗时）
        "total_tokens": task.total_tokens,
        "total_prompt_tokens": task.total_prompt_tokens,
        "total_completion_tokens": task.total_completion_tokens,
    }


@router.get("/tasks/{task_id}/context", tags=["📋 任务管理"])
async def get_task_context(task_id: str):
    """
    获取任务的 LLM 上下文（用于调试 Agent 思维链）

    注意：
    1. 仅能获取内存中运行的任务（或刚完成未被清理的任务）
    2. 上下文包含完整的系统提示词、用户输入（含截图Base64）和模型响应
    """
    agent_service = get_agent_service()
    context = agent_service.get_task_context(task_id)

    if context is None:
        # 如果是已完成的任务，上下文可能已被清理
        raise HTTPException(
            404,
            "Context not found. The task might be completed and cleaned up from memory, "
            "or it was never started.",
        )

    # 过滤掉过大的 Base64 图片数据，避免响应过大
    # 前端只需要知道这里有图片即可
    filtered_context = []
    for msg in context:
        msg_copy = msg.copy()
        # 递归查找 image_url 并替换 base64
        if "content" in msg_copy and isinstance(msg_copy["content"], list):
            new_content = []
            for item in msg_copy["content"]:
                item_copy = item.copy()
                if item_copy.get("type") == "image_url":
                    url = item_copy.get("image_url", {}).get("url", "")
                    if url.startswith("data:image"):
                        # 保留前缀以便识别，但截断内容
                        item_copy["image_url"]["url"] = f"{url[:30]}...[BASE64_IMAGE_HIDDEN]"
                new_content.append(item_copy)
            msg_copy["content"] = new_content
        filtered_context.append(msg_copy)

    return {"task_id": task_id, "context": filtered_context}


class InjectCommentRequest(BaseModel):
    """用户评论注入请求"""

    comment: str


@router.post("/tasks/{task_id}/inject", tags=["📋 任务管理"])
async def inject_comment(task_id: str, request: InjectCommentRequest):
    """
    向运行中的任务注入用户评论

    注入的评论会作为[User Intervention]添加到LLM上下文中，
    在下一步执行时被模型看到。

    使用场景：
    - 纠正Agent的错误判断
    - 提供额外的上下文信息
    - 引导Agent执行特定操作

    注意：
    - 仅对运行中的任务有效
    - 评论会在下一个step生效
    """
    agent_service = get_agent_service()
    success = agent_service.inject_comment(task_id, request.comment)

    if not success:
        raise HTTPException(
            400,
            f"Failed to inject comment. Task {task_id} might not be running "
            "or already completed.",
        )

    return {
        "success": True,
        "task_id": task_id,
        "message": "Comment injected successfully. It will be visible to the model in the next step.",
    }


@router.post("/tasks/{task_id}/cancel", tags=["📋 任务管理"])
async def cancel_task(task_id: str):
    """取消正在执行的任务"""
    agent_service = get_agent_service()
    success = await agent_service.cancel_task(task_id)

    if not success:
        raise HTTPException(400, f"Failed to cancel task: {task_id}")

    return {"message": "Task cancelled", "task_id": task_id}


@router.delete("/tasks/{task_id}", tags=["📋 任务管理"])
async def delete_task(task_id: str):
    """删除任务记录（仅能删除已完成/失败的任务）"""
    from server.database import get_db
    from server.database.crud import delete_task as db_delete_task
    from server.database.crud import get_task as db_get_task

    db = next(get_db())

    # 检查任务是否存在
    db_task = db_get_task(db, task_id)
    if not db_task:
        raise HTTPException(404, f"Task not found: {task_id}")

    # 只能删除已完成或失败的任务
    if db_task.status not in ["completed", "failed", "cancelled"]:
        raise HTTPException(400, "Cannot delete running task. Please cancel it first.")

    # 删除任务
    success = db_delete_task(db, task_id)

    if not success:
        raise HTTPException(500, f"Failed to delete task: {task_id}")

    return {"message": "Task deleted", "task_id": task_id}


@router.post("/tasks/delete-batch", tags=["📋 任务管理"])
async def delete_tasks_batch(request: dict):
    """批量删除任务记录"""
    from server.database import get_db
    from server.database.crud import delete_tasks_batch as db_delete_tasks_batch

    task_ids = request.get("task_ids", [])
    if not task_ids:
        raise HTTPException(400, "task_ids is required")

    db = next(get_db())
    count = db_delete_tasks_batch(db, task_ids)

    return {"message": f"Deleted {count} tasks", "count": count}


# ============================================
# 统计信息 API
# ============================================


@router.get("/stats", response_model=StatsResponse, tags=["📊 统计信息"])
async def get_stats():
    """获取整体统计信息"""
    device_pool = get_device_pool()
    agent_service = get_agent_service()

    return StatsResponse(device_stats=device_pool.get_stats(), task_stats=agent_service.get_stats())


# ============================================
# 语音识别 API - 已迁移到 speech_api.py
# ============================================
#
# 语音相关接口已迁移到专门的 speech_api.py 文件中：
# - POST /api/v1/speech/stt  - 语音转文字
# - POST /api/v1/speech/tts  - 文字转语音
# - GET  /api/v1/speech/health - 健康检查
#


# ============================================
# WebSocket 实时通信
# ============================================


manager = get_connection_manager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket端点 - 实时任务状态推送

    消息格式:
    {
        "type": "task_update" | "device_update" | "heartbeat",
        "data": {...}
    }
    """
    await manager.connect(websocket)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()

            # 处理心跳
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            # 处理订阅请求
            elif data.get("type") == "subscribe":
                # 发送当前状态
                device_pool = get_device_pool()
                agent_service = get_agent_service()

                await websocket.send_json(
                    {
                        "type": "initial_state",
                        "data": {
                            "devices": len(device_pool.devices),
                            "tasks": len(agent_service.running_tasks),
                        },
                    }
                )

            # 等待一段时间再检查状态（避免过于频繁）
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


# ============================================
# 后台任务：定期推送状态更新
# ============================================


async def broadcast_status_updates():
    """定期广播状态更新"""
    while True:
        try:
            await asyncio.sleep(5)  # 每5秒推送一次

            device_pool = get_device_pool()
            agent_service = get_agent_service()

            # 广播设备状态
            await manager.broadcast({"type": "device_update", "data": device_pool.get_stats()})

            # 广播任务状态
            await manager.broadcast({"type": "task_update", "data": agent_service.get_stats()})

        except Exception as e:
            logger.error(f"Broadcast error: {e}", exc_info=True)


# ============================================
# 启动后台任务已迁移到 app.py 的 lifespan
# ============================================
#
# Warning: 注意：@router.on_event("startup") 在 FastAPI 2.0+ 中已废弃
# 所有启动逻辑已迁移到 app.py 的 lifespan 函数中：
# - WebSocket广播回调设置
# - 后台任务启动
#

# ============================================
# 语音API已迁移到 speech_api.py
# ============================================
#
# 语音相关接口已迁移到专门的 speech_api.py 文件中：
# - POST /api/v1/speech/stt  - 语音转文字
# - POST /api/v1/speech/tts  - 文字转语音
# - GET  /api/v1/speech/health - 健康检查
#


# ============================================
# 截图管理 API
# ============================================


@router.get("/screenshots/{task_id}/{filename}", tags=["🖼️ 截图管理"])
async def get_screenshot(task_id: str, filename: str):
    """
    获取任务步骤截图

    Args:
        task_id: 任务ID
        filename: 文件名（如 step_001_small.jpg）
    """
    import os

    # 构建文件路径
    screenshot_path = os.path.join("data", "screenshots", task_id, filename)

    # 检查文件是否存在
    if not os.path.exists(screenshot_path):
        raise HTTPException(status_code=404, detail="截图文件不存在")

    # 返回文件
    return FileResponse(path=screenshot_path, media_type="image/jpeg", filename=filename)


@router.get("/devices/{device_id}/screenshot", tags=["🖼️ 截图管理"])
async def get_device_screenshot(device_id: str, size: str = "medium"):
    """
    获取设备实时截图

    Args:
        device_id: 设备ID (如 device_6100)
        size: 尺寸级别 (ai/medium/small/thumbnail)
    """
    import asyncio
    import base64
    import os
    import tempfile

    from phone_agent.adb import get_screenshot
    from server.utils.image_utils import compress_screenshot

    try:
        # 将 device_id 转换为 ADB 地址 (device_6100 -> localhost:6100)
        from server.utils import device_id_to_adb_address

        adb_address = device_id_to_adb_address(device_id)

        # 获取截图
        screenshot = await asyncio.to_thread(get_screenshot, adb_address)

        if not screenshot or not screenshot.base64_data:
            raise HTTPException(status_code=500, detail="无法获取设备截图")

        # 保存临时截图
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(base64.b64decode(screenshot.base64_data))
            tmp_path = tmp.name
            tmp.flush()  # 确保数据写入磁盘
            os.fsync(tmp.fileno())  # 强制同步到磁盘

        # 验证文件是否可读
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            raise HTTPException(status_code=500, detail="截图文件保存失败")

        # 压缩截图
        compressed_dir = os.path.dirname(tmp_path)
        compressed_paths = await asyncio.to_thread(
            compress_screenshot, tmp_path, compressed_dir, for_ai=(size == "ai")
        )

        # 获取指定尺寸的截图
        target_path = compressed_paths.get(size) or compressed_paths.get("medium")

        if not target_path or not os.path.exists(target_path):
            raise HTTPException(status_code=500, detail="截图压缩失败")

        # 读取文件内容直接返回（避免FileResponse异步删除问题）
        with open(target_path, "rb") as f:
            image_data = f.read()

        # 清理临时文件
        try:
            os.unlink(tmp_path)
            for path in compressed_paths.values():
                if path and os.path.exists(path):
                    os.unlink(path)
        except Exception:
            pass

        # 返回图片数据
        from fastapi.responses import Response

        return Response(
            content=image_data,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f'inline; filename="{device_id}_screenshot_{size}.jpg"'
            },
        )

    except Exception as e:
        logger.error(f"Get device screenshot error: {e}")
        raise HTTPException(status_code=500, detail=f"获取设备截图失败: {str(e)}")


# ============================================
# 日志管理 API
# ============================================


@router.get("/logs", tags=["🔍 日志管理"])
async def get_logs(
    level: Optional[str] = Query(None, description="日志级别过滤: DEBUG, INFO, WARNING, ERROR"),
    limit: int = Query(100, ge=1, le=1000, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
):
    """
    获取应用日志（优化版 - 限制文件大小和使用流式读取）

    返回格式化的日志列表，支持过滤和搜索
    """
    import json
    import os
    from datetime import datetime

    logs = []
    log_dir = "logs"

    # 如果日志目录不存在，返回空列表
    if not os.path.exists(log_dir):
        return {"logs": [], "total": 0, "offset": offset, "limit": limit}

    # 优化：只读取最近1个日志文件，限制文件大小
    log_files = sorted(
        [f for f in os.listdir(log_dir) if f.endswith(".log")],
        key=lambda x: os.path.getmtime(os.path.join(log_dir, x)),
        reverse=True,
    )[
        :1
    ]  # 只读最近1个文件（从3个减少到1个）

    max_file_size = 10 * 1024 * 1024  # 10MB 限制

    for log_file in log_files:
        try:
            file_path = os.path.join(log_dir, log_file)

            # 优化：检查文件大小，跳过过大的文件
            if os.path.getsize(file_path) > max_file_size:
                logger.warning(f"Log file {log_file} too large, skipping")
                continue

            # 优化：只读取文件最后的部分（倒序读取）
            with open(file_path, "r", encoding="utf-8") as f:
                # 读取最后 5000 行
                lines = f.readlines()[-5000:]

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # 尝试解析JSON格式的日志
                    try:
                        log_entry = json.loads(line)
                    except Exception:
                        # 如果不是JSON，解析文本格式
                        # 格式: timestamp - name - level - [file:line] - message
                        parts = line.split(" - ")
                        if len(parts) >= 5:
                            log_entry = {
                                "timestamp": parts[0],
                                "name": parts[1],
                                "level": parts[2].strip(),
                                "message": " - ".join(parts[4:]),  # 消息可能包含 ' - '
                            }
                        elif len(parts) >= 3:
                            # 简化格式: timestamp - name - level - message
                            log_entry = {
                                "timestamp": parts[0],
                                "name": parts[1] if len(parts) > 1 else "",
                                "level": parts[2].strip() if len(parts) > 2 else "INFO",
                                "message": " - ".join(parts[3:]) if len(parts) > 3 else line,
                            }
                        else:
                            log_entry = {
                                "timestamp": datetime.now().isoformat(),
                                "level": "INFO",
                                "message": line,
                            }

                    # 过滤日志级别
                    if level and log_entry.get("level") != level.upper():
                        continue

                    # 搜索关键词
                    if search and search.lower() not in log_entry.get("message", "").lower():
                        continue

                    logs.append(log_entry)
        except Exception as e:
            logger.error(f"Failed to read log file {log_file}: {e}")

    # 按时间倒序排序
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # 分页
    total = len(logs)
    logs = logs[offset : offset + limit]

    return {"logs": logs, "total": total, "offset": offset, "limit": limit}


@router.get("/logs/task/{task_id}", tags=["🔍 日志管理"])
async def get_task_logs(task_id: str):
    """
    获取特定任务的工程化日志（JSONL格式）

    返回该任务的所有步骤日志和元数据
    """
    from phone_agent.logging import TaskLogger

    task_logger = TaskLogger(log_dir="logs")

    try:
        logs = task_logger.read_logs(task_id)

        return {"logs": logs, "task_id": task_id, "total": len(logs)}
    except Exception as e:
        logger.error(f"Failed to read task logs: {e}")
        raise HTTPException(500, f"Failed to read logs: {str(e)}")


@router.delete("/logs", tags=["🔍 日志管理"])
async def clear_logs():
    """清空所有日志文件"""
    import os
    import shutil

    log_dir = "logs"

    if not os.path.exists(log_dir):
        return {"message": "No logs to clear"}

    try:
        # 备份日志
        backup_dir = f"logs_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copytree(log_dir, backup_dir)

        # 清空日志目录
        for file in os.listdir(log_dir):
            file_path = os.path.join(log_dir, file)
            if os.path.isfile(file_path):
                os.remove(file_path)

        return {"message": "Logs cleared successfully", "backup_location": backup_dir}
    except Exception as e:
        logger.error(f"Failed to clear logs: {e}")
        raise HTTPException(500, f"Failed to clear logs: {str(e)}")
