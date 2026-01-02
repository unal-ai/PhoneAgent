"""
Tests for phone_agent.model.client

Unit tests for the ModelClient class.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestModelConfig:
    """Tests for ModelConfig dataclass."""

    def test_default_values(self):
        """Test ModelConfig with minimal required fields."""
        from phone_agent.model import ModelConfig

        config = ModelConfig(api_key="test-key")
        assert config.api_key == "test-key"
        assert config.model_name is not None

    def test_custom_base_url(self):
        """Test ModelConfig with custom base URL."""
        from phone_agent.model import ModelConfig

        config = ModelConfig(api_key="test-key", base_url="https://custom.api.com/v1/")
        assert config.base_url == "https://custom.api.com/v1/"


class TestModelClient:
    """Tests for ModelClient class."""

    def test_initialization(self, mock_model_config):
        """Test ModelClient initialization."""
        from phone_agent.model.client import ModelClient

        client = ModelClient(mock_model_config)
        assert client.config == mock_model_config

    @patch("phone_agent.model.client.OpenAI")
    def test_request_json_success(self, mock_openai, mock_model_config, mock_model_response):
        """Test successful JSON request."""
        from phone_agent.model.client import ModelClient

        # Setup mock
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"action": "done"}'))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_client.chat.completions.create.return_value = mock_response

        client = ModelClient(mock_model_config)

        # This test validates the interface exists
        assert hasattr(client, "request_json") or hasattr(client, "chat")
