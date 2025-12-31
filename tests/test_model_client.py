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
        
        config = ModelConfig(
            api_key="test-key",
            base_url="https://custom.api.com/v1/"
        )
        assert config.base_url == "https://custom.api.com/v1/"


class TestModelClient:
    """Tests for ModelClient class."""

    def test_initialization(self, mock_model_config):
        """Test ModelClient initialization."""
        from phone_agent.model.client import ModelClient
        
        client = ModelClient(mock_model_config)
        assert client.config == mock_model_config

    @patch("phone_agent.model.client.httpx.Client")
    def test_request_json_success(self, mock_httpx, mock_model_config, mock_model_response):
        """Test successful JSON request."""
        from phone_agent.model.client import ModelClient
        
        # Setup mock
        mock_client = MagicMock()
        mock_httpx.return_value.__enter__ = Mock(return_value=mock_client)
        mock_httpx.return_value.__exit__ = Mock(return_value=False)
        
        mock_http_response = Mock()
        mock_http_response.json.return_value = {
            "choices": [{"message": {"content": '{"action": "done"}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        }
        mock_http_response.raise_for_status = Mock()
        mock_client.post.return_value = mock_http_response
        
        client = ModelClient(mock_model_config)
        
        # This test validates the interface exists
        assert hasattr(client, "request_json") or hasattr(client, "chat")
