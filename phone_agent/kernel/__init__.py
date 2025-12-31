#!/usr/bin/env python3
# Copyright (C) 2025 PhoneAgent Contributors
# Licensed under AGPL-3.0

"""
Kernel Package - Android自动化内核

包含多种内核实现：
- XMLKernelAgent: 基于UI树的快速内核
- HybridAgent: 混合内核（XML + Vision）
- StepCallback: 统一的步骤回调接口
"""

from .callback import AsyncStepCallback, NoOpCallback, StepCallback
from .hybrid_agent import ExecutionMode, HybridAgent, HybridConfig
from .xml_agent import XMLKernelAgent, XMLKernelConfig

__all__ = [
    "XMLKernelAgent",
    "XMLKernelConfig",
    "HybridAgent",
    "HybridConfig",
    "ExecutionMode",
    "StepCallback",
    "NoOpCallback",
    "AsyncStepCallback",
]
