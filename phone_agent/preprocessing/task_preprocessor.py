"""
任务预处理器

根据任务特征进行智能路由，系统指令类任务直接执行。

Phase 1: 支持基础系统指令（launch/home/back/screenshot）
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型"""

    SYSTEM_COMMAND = "system_command"  # 系统指令
    UI_INTERACTION = "ui_interaction"  # UI交互
    UNKNOWN = "unknown"  # 未知


class ExecutorType(Enum):
    """执行器类型"""

    RULE_ENGINE = "rule_engine"  # 规则引擎
    XML_KERNEL = "xml"
    VISION_KERNEL = "vision"
    PLANNING_KERNEL = "planning"
    AUTO = "auto"


@dataclass
class ExecutionPlan:
    """执行计划"""

    executor: ExecutorType
    task_type: TaskType
    direct_action: Optional[Dict]  # 如果可以直接执行
    skip_llm: bool  # 是否跳过LLM
    params: Dict  # 传递给执行器的参数
    fallback: ExecutorType  # 失败时降级
    confidence: float  # 决策置信度 0-1


class TaskPreprocessor:
    """任务预处理器 - Phase 1版本"""

    # 系统指令模式（优先级从高到低）
    SYSTEM_PATTERNS = {
        "launch_app": [
            # 中文 - 宽松匹配：允许"打开XX，然后..."格式
            (r"^(打开|启动)\s*(?P<app>[\w\u4e00-\u9fa5]+)\s*[，,]", 0.90),  # 🆕 带逗号的复合任务
            (r"^(打开|启动)\s*(?P<app>[\w\u4e00-\u9fa5]+)(app|应用)?$", 0.95),  # 原有：纯启动
            (r"^(?P<app>[\w\u4e00-\u9fa5]+)\s*(app|应用)$", 0.90),
            # 🆕 隐式启动：应用名在开头，后跟动作（如"小红书创作一篇图文笔记"）
            (
                r"^(?P<app>[\w\u4e00-\u9fa5]{2,6})(创作|发布|发送|搜索|查找|购买|下单|刷|看|浏览)",
                0.85,
            ),
            # 🆕 隐式启动：在XX做YY（如"在微信给张三发消息"）
            (r"^在\s*(?P<app>[\w\u4e00-\u9fa5]+)\s*(给|向|跟|和|找|搜|查)", 0.85),
            # 英文
            (r"^(Open|Launch)\s+(?P<app>[\w\s]+?)\s*[，,]", 0.90, re.IGNORECASE),  # 🆕 复合任务
            (r"^(Open|Launch)\s+(?P<app>[\w\s]+?)(app)?$", 0.95, re.IGNORECASE),
        ],
        "go_home": [
            (r"^(返回|回到)\s*(桌面|主屏幕)$", 0.95),
            (r"^(Go|Back to)\s+home$", 0.95, re.IGNORECASE),
            (r"^Home$", 0.90, re.IGNORECASE),
        ],
        "go_back": [
            (r"^(返回|后退)$", 0.95),
            (r"^Back$", 0.95, re.IGNORECASE),
        ],
        "screenshot": [
            (r"^截[个屏图]?$", 0.95),
            (r"^(Screenshot|Capture)$", 0.95, re.IGNORECASE),
        ],
    }

    def __init__(self):
        self.stats = {
            "total": 0,
            "direct_execution": 0,
            "by_type": {},
        }

    def preprocess(self, instruction: str, current_kernel: str = "auto") -> ExecutionPlan:
        """
        预处理任务指令

        Args:
            instruction: 用户指令
            current_kernel: 当前请求的内核模式

        Returns:
            ExecutionPlan: 执行计划
        """
        self.stats["total"] += 1

        # 去除首尾空格
        instruction = instruction.strip()

        # 1. 尝试匹配系统指令
        for action_type, patterns in self.SYSTEM_PATTERNS.items():
            for pattern_data in patterns:
                pattern = pattern_data[0]
                confidence = pattern_data[1]
                flags = pattern_data[2] if len(pattern_data) > 2 else 0

                match = re.match(pattern, instruction, flags)
                if match:
                    # 匹配成功，创建直接执行计划
                    direct_action = self._create_direct_action(action_type, match.groupdict())

                    # 🆕 检测复合任务
                    # 1. 包含逗号/句号/且/并且等连接词
                    # 2. 隐式启动（应用名后跟动作，如"小红书创作..."、"在微信给..."）
                    is_compound = bool(re.search(r"[，,。；;]|且|并且|然后|接着", instruction))
                    is_implicit_launch = bool(
                        re.search(
                            r"^[\w\u4e00-\u9fa5]{2,6}(创作|发布|发送|搜索|查找|购买|下单|刷|看|浏览)|^在\s*[\w\u4e00-\u9fa5]+\s*(给|向|跟|和|找|搜|查)",
                            instruction,
                        )
                    )

                    if (is_compound or is_implicit_launch) and action_type == "launch_app":
                        direct_action["is_compound"] = True
                        task_type_desc = "隐式启动" if is_implicit_launch else "复合任务"
                        logger.info(
                            f"📋 任务预处理: '{instruction}' → {action_type}(app={direct_action.get('app')}) + LLM后续 "
                            f"({task_type_desc}，置信度: {confidence:.2f})"
                        )
                        # 复合任务：先执行launch，再交给LLM
                        return ExecutionPlan(
                            executor=ExecutorType.RULE_ENGINE,
                            task_type=TaskType.SYSTEM_COMMAND,
                            direct_action=direct_action,
                            skip_llm=False,  # 🆕 不跳过LLM！
                            params={"instruction": instruction},
                            fallback=ExecutorType(current_kernel),
                            confidence=confidence,
                        )

                    logger.info(
                        f"📋 任务预处理: '{instruction}' → {action_type} "
                        f"(置信度: {confidence:.2f})"
                    )

                    self.stats["direct_execution"] += 1
                    self.stats["by_type"][action_type] = (
                        self.stats["by_type"].get(action_type, 0) + 1
                    )

                    return ExecutionPlan(
                        executor=ExecutorType.RULE_ENGINE,
                        task_type=TaskType.SYSTEM_COMMAND,
                        direct_action=direct_action,
                        skip_llm=True,
                        params={"instruction": instruction},
                        fallback=ExecutorType(current_kernel),
                        confidence=confidence,
                    )

        # 2. 未匹配到系统指令，走正常流程
        logger.debug(f"📋 任务预处理: '{instruction}' → 未识别为系统指令，走正常流程")

        return ExecutionPlan(
            executor=ExecutorType(current_kernel),
            task_type=TaskType.UI_INTERACTION,
            direct_action=None,
            skip_llm=False,
            params={"instruction": instruction},
            fallback=ExecutorType.AUTO,
            confidence=0.5,
        )

    def _create_direct_action(self, action_type: str, match_dict: Dict) -> Dict:
        """创建可直接执行的动作"""

        if action_type == "launch_app":
            app_name = match_dict.get("app", "").strip()
            return {
                "type": "launch",
                "app": app_name,
                # 🆕 标记是否为复合任务（需要后续LLM处理）
                "is_compound": False,  # 由调用方设置
            }

        elif action_type == "go_home":
            return {"type": "home"}

        elif action_type == "go_back":
            return {"type": "back"}

        elif action_type == "screenshot":
            return {"type": "screenshot"}

        return {}

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = max(1, self.stats["total"])
        return {
            **self.stats,
            "direct_execution_rate": self.stats["direct_execution"] / total,
            "direct_execution_percentage": f"{(self.stats['direct_execution'] / total * 100):.1f}%",
        }
