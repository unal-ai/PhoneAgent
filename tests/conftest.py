"""
PhoneAgent Test Configuration

Pytest fixtures and shared test utilities.
"""

import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def mock_model_config():
    """Create a mock ModelConfig for testing."""
    from phone_agent.model import ModelConfig

    return ModelConfig(
        api_key="test-api-key", base_url="https://test.example.com/api/", model_name="test-model"
    )


@pytest.fixture
def mock_adb_device():
    """Mock ADB device connection."""
    with patch("phone_agent.adb.device.run_adb_command") as mock_cmd:
        mock_cmd.return_value = (True, "")
        yield mock_cmd


@pytest.fixture
def mock_model_response():
    """Mock model API response."""
    mock_response = Mock()
    mock_response.raw_content = '{"action": "done", "reason": "Task completed"}'
    mock_response.usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    return mock_response
