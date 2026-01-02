"""
App discovery module for querying installed packages via ADB.
"""

import logging
from typing import List, Dict, Optional
from phone_agent.adb.connection import ADBConnection

logger = logging.getLogger(__name__)


async def get_third_party_packages(device_id: str) -> List[str]:
    """
    Get list of third-party package names installed on the device.
    Uses 'pm list packages -3' command.
    """
    try:
        # Execute ADB command
        output = await ADBConnection.execute(device_id, "pm list packages -3")
        if not output:
            return []

        packages = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line.replace("package:", "", 1))

        return packages
    except Exception as e:
        logger.error(f"Failed to get installed packages for {device_id}: {e}")
        return []


async def get_all_packages(device_id: str) -> List[str]:
    """
    Get list of ALL package names installed on the device.
    Uses 'pm list packages' command.
    """
    try:
        # Execute ADB command
        output = await ADBConnection.execute(device_id, "pm list packages")
        if not output:
            return []

        packages = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line.replace("package:", "", 1))

        return packages
    except Exception as e:
        logger.error(f"Failed to get all packages for {device_id}: {e}")
        return []
