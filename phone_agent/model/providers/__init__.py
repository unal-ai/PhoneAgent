"""
Multi-modal Vision Language Model Providers
Support for Zhipu AI VLM models
"""

from phone_agent.model.providers.base import BaseVLMProvider
from phone_agent.model.providers.registry import ModelRegistry, register_provider
from phone_agent.model.providers.zhipu_provider import ZhipuAIProvider

__all__ = [
    "BaseVLMProvider",
    "ZhipuAIProvider",
    "ModelRegistry",
    "register_provider",
]
