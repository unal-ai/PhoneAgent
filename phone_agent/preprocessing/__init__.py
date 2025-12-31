"""
任务预处理模块

在LLM之前对任务进行智能路由，让简单的系统指令直接执行。

Version: 1.0.0 (Phase 1)
Author: PhoneAgent Team
"""

from .rule_engine import RuleEngineExecutor
from .task_preprocessor import ExecutionPlan, ExecutorType, TaskPreprocessor, TaskType

__all__ = [
    "TaskPreprocessor",
    "ExecutionPlan",
    "TaskType",
    "ExecutorType",
    "RuleEngineExecutor",
]

__version__ = "1.0.0"
