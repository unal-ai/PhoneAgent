"""ADB utilities for Android device interaction."""

from phone_agent.adb.anti_detection import (
    AntiDetection,
    get_anti_detection,
    human_delay,
    randomize_point,
    reading_delay,
    thinking_delay,
)
from phone_agent.adb.connection import (
    ADBConnection,
    ConnectionType,
    DeviceInfo,
    list_devices,
    quick_connect,
)
from phone_agent.adb.device import (
    back,
    double_tap,
    get_current_app,
    home,
    launch_app,
    long_press,
    swipe,
    tap,
)
from phone_agent.adb.input import (
    clear_text,
    detect_and_set_adb_keyboard,
    restore_keyboard,
    type_text,
)
from phone_agent.adb.screenshot import get_screenshot
from phone_agent.adb.smart_input import (
    get_input_method,
    reset_input_method,
    smart_type_text,
)

__all__ = [
    # Screenshot
    "get_screenshot",
    # Input
    "type_text",
    "clear_text",
    "detect_and_set_adb_keyboard",
    "restore_keyboard",
    # Smart Input (✨ 新增: 优先yadb)
    "smart_type_text",
    "reset_input_method",
    "get_input_method",
    # Device control
    "get_current_app",
    "tap",
    "swipe",
    "back",
    "home",
    "double_tap",
    "long_press",
    "launch_app",
    # Connection management
    "ADBConnection",
    "DeviceInfo",
    "ConnectionType",
    "quick_connect",
    "list_devices",
    # Anti-Detection
    "AntiDetection",
    "get_anti_detection",
    "human_delay",
    "reading_delay",
    "thinking_delay",
    "randomize_point",
]
