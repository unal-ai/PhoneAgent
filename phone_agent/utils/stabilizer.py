
import base64
import logging
import math
import time
from io import BytesIO

from PIL import Image, ImageChops

from phone_agent.adb.screenshot import Screenshot, get_screenshot

logger = logging.getLogger(__name__)


def calculate_rms_diff(img1: Image.Image, img2: Image.Image) -> float:
    """Calculate Root Mean Square difference between two images."""
    try:
        # Resize to speed up and reduce noise sensitivity
        img1_small = img1.resize((64, 64)).convert("L")
        img2_small = img2.resize((64, 64)).convert("L")

        diff = ImageChops.difference(img1_small, img2_small)
        h = diff.histogram()
        sq = (value * ((idx % 256) ** 2) for idx, value in enumerate(h))
        sum_of_squares = sum(sq)
        rms = math.sqrt(sum_of_squares / float(img1_small.size[0] * img1_small.size[1]))
        return rms
    except Exception as e:
        logger.warning(f"Failed to calculate image diff: {e}")
        return 999.0


def screenshot_to_image(screenshot: Screenshot) -> Image.Image:
    """Convert Screenshot object to PIL Image."""
    image_data = base64.b64decode(screenshot.base64_data)
    return Image.open(BytesIO(image_data))


def wait_for_ui_stabilization(
    device_id: str | None, timeout: float = 3.0, threshold: float = 5.0
) -> Screenshot:
    """
    Wait for UI to stabilize (images stop changing).
    Returns the final stable screenshot.
    """
    start_time = time.time()

    # Initial screenshot
    try:
        current_screenshot = get_screenshot(device_id)
        current_img = screenshot_to_image(current_screenshot)
    except Exception as e:
        logger.error(f"Failed to capture initial screenshot for stabilization: {e}")
        return get_screenshot(device_id)  # Fallback

    attempts = 0

    while (time.time() - start_time) < timeout:
        time.sleep(0.5)  # Wait interval

        try:
            next_screenshot = get_screenshot(device_id)
            next_img = screenshot_to_image(next_screenshot)

            diff = calculate_rms_diff(current_img, next_img)

            if diff < threshold:
                # Stable!
                if attempts > 0:
                    logger.info(f"UI stabilized after {attempts} waits (diff: {diff:.2f})")
                return next_screenshot

            # Not stable, update current and continue
            current_screenshot = next_screenshot
            current_img = next_img
            attempts += 1
            if attempts % 2 == 0:
                logger.debug(f"UI still changing (diff: {diff:.2f})...")

        except Exception as e:
            logger.warning(f"Stabilization check failed: {e}")
            break

    logger.info(f"UI stabilization timeout after {timeout}s")
    return current_screenshot
