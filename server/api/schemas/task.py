"""
任务相关的 API 数据模型
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    model_config = {"protected_namespaces": ()}  # 禁用保护命名空间警告
    
    instruction: str = Field(..., description="任务指令（自然语言）")
    device_id: Optional[str] = Field(None, description="指定设备ID（不指定则自动分配）")
    ai_provider: Optional[str] = Field("zhipu", description="AI模型提供商（固定为zhipu）")
    ai_model: Optional[str] = Field("autoglm-phone", description="AI模型名称（推荐：autoglm-phone官方优化，glm-4.6v-flash免费最新，glm-4.6v付费旗舰，glm-4.6v-flashx付费极速）")
    ai_api_key: Optional[str] = Field(None, description="AI模型API密钥（可选，使用环境变量）")
    max_steps: Optional[int] = Field(None, description="最大步骤数（默认从环境变量获取）")
    prompt_card_ids: Optional[List[int]] = Field(None, description="提示词卡片ID列表")
    # Warning: 已废弃：kernel_mode（保留字段用于API兼容，但不再使用）
    kernel_mode: Optional[str] = Field(
        default="vision",
        description="[已废弃] 执行内核模式：统一使用vision内核，不再支持xml/auto"
    )


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    instruction: str
    device_id: Optional[str]
    status: str
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration: Optional[float]
    result: Optional[str]
    error: Optional[str]
    steps: list = []  # 修复：改为list类型，返回完整步骤详情
    # Token统计
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

