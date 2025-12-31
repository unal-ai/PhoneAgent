"""
Model Response Parser Factory

Inspired by GELab-Zero's parser_factory.py design.
Provides a pluggable architecture for parsing different model output formats.
"""

from .autoglm_parser import AutoGLMParser
from .base_parser import BaseResponseParser
from .factory import ParserFactory, register_parser

# Auto-register built-in parsers
register_parser("autoglm-phone", AutoGLMParser)
register_parser("glm-4v", AutoGLMParser)
register_parser("glm-4.1v-thinking-flash", AutoGLMParser)
register_parser("default", AutoGLMParser)

__all__ = [
    "ParserFactory",
    "register_parser",
    "BaseResponseParser",
    "AutoGLMParser",
]
