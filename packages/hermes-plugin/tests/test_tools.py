"""
Tests for Hermes plugin tools.

TDD: These tests define expected behavior of pi delegation tools.
"""

import os
import sys
from pathlib import Path

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock

# Find project root and add to path for local imports
_project_root = Path(__file__).parent.parent.parent
_plugin_src = _project_root / "packages" / "hermes-plugin" / "src"
_core_src = _project_root / "packages" / "core" / "src"
if str(_plugin_src) not in sys.path:
    sys.path.insert(0, str(_plugin_src))
if str(_core_src) not in sys.path:
    sys.path.insert(0, str(_core_src))

from hermes_pi_bridge.config import BridgeConfig
from hermes_pi_bridge.tools.delegate import PiDelegateTool
from hermes_pi_bridge.tools.status import PiStatusTool


class TestPiDelegateTool:
    """Test pi delegation tool."""
    
    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration."""
        return BridgeConfig(
            pi_url="http://localhost:2719",
            timeout_seconds=300,
            hermes_home=tmp_path,
        )
    
    @pytest.fixture
    def tool(self, config):
        """Create tool instance with mocked client."""
        with patch('hermes_pi_bridge.tools.delegate.PiHttpClient') as mock_client_class:
            mock_client = Mock()
            mock_client.delegate_task = Mock(return_value={
                "success": True,
                "task_id": "pi-task-123",
            })
            mock_client_class.return_value = mock_client
            
            tool = PiDelegateTool(config)
            tool.client = mock_client
            return tool
    
    def test_tool_name(self, tool):
        """Tool has correct name."""
        assert tool.name == "pi_delegate"
    
    def test_tool_has_description(self, tool):
        """Tool has a description."""
        assert len(tool.description) > 0
        assert "pi" in tool.description.lower()
    
    def test_tool_has_parameters(self, tool):
        """Tool has parameter schema."""
        params = tool.parameters
        assert params["type"] == "object"
        assert "task" in params["properties"]
        assert "timeout" in params["properties"]
        assert "priority" in params["properties"]
    
    def test_tool_requires_task_parameter(self, tool):
        """Task parameter is required."""
        params = tool.parameters
        assert "task" in params["required"]
    
    def test_execute_delegates_to_pi(self, tool, config, tmp_path):
        """Execute sends task to pi HTTP client."""
        # Mock Kanban
        with patch('hermes_pi_bridge.tools.delegate.create_task') as mock_create:
            with patch('hermes_pi_bridge.tools.delegate.update_task_status'):
                mock_create.return_value = "kanban-123"
                
                result = tool.execute(
                    task="Analyze this code",
                    context="Some context",
                    timeout=300,
                )
        
        # Verify pi client was called
        tool.client.delegate_task.assert_called_once()
        call_args = tool.client.delegate_task.call_args
        assert "Analyze this code" in str(call_args)
    
    def test_execute_returns_kanban_id(self, tool, tmp_path):
        """Execute returns Hermes Kanban task ID."""
        with patch('hermes_pi_bridge.tools.delegate.create_task') as mock_create:
            with patch('hermes_pi_bridge.tools.delegate.update_task_status'):
                mock_create.return_value = "kanban-task-456"
                
                result = tool.execute(task="Test task")
        
        result_data = json.loads(result)
        assert result_data["ok"] == True
        assert result_data["kanban_id"] == "kanban-task-456"
    
    def test_execute_handles_pi_failure(self, tool, tmp_path):
        """Execute handles pi client failure gracefully."""
        tool.client.delegate_task = Mock(return_value={
            "success": False,
            "error": "pi not available",
        })
        
        with patch('hermes_pi_bridge.tools.delegate.create_task') as mock_create:
            with patch('hermes_pi_bridge.tools.delegate.update_task_status'):
                mock_create.return_value = "kanban-123"
                
                result = tool.execute(task="Test task")
        
        result_data = json.loads(result)
        assert result_data["ok"] == False
        assert "pi delegation failed" in result_data["error"]
    
    def test_execute_handles_exception(self, tool, tmp_path):
        """Execute handles unexpected exceptions."""
        tool.client.delegate_task = Mock(side_effect=Exception("Connection refused"))
        
        with patch('hermes_pi_bridge.tools.delegate.create_task') as mock_create:
            mock_create.return_value = "kanban-123"
            
            result = tool.execute(task="Test task")
        
        result_data = json.loads(result)
        assert result_data["ok"] == False
        assert "Failed to delegate" in result_data["error"]
    
    def test_execute_uses_default_timeout(self, tool, tmp_path):
        """Execute uses config timeout if not specified."""
        with patch('hermes_pi_bridge.tools.delegate.create_task') as mock_create:
            with patch('hermes_pi_bridge.tools.delegate.update_task_status'):
                mock_create.return_value = "kanban-123"
                
                result = tool.execute(task="Test task")
        
        result_data = json.loads(result)
        assert result_data["timeout"] == 300  # from config
    
    def test_execute_priority_normalized(self, tool, tmp_path):
        """Execute normalizes priority value."""
        with patch('hermes_pi_bridge.tools.delegate.create_task') as mock_create:
            with patch('hermes_pi_bridge.tools.delegate.update_task_status'):
                mock_create.return_value = "kanban-123"
                
                result = tool.execute(task="Test", priority="high")
        
        result_data = json.loads(result)
        assert result_data["ok"] == True


class TestPiStatusTool:
    """Test pi status check tool."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return BridgeConfig(
            pi_url="http://localhost:2719",
        )
    
    @pytest.fixture
    def tool(self, config):
        """Create tool instance with mocked client."""
        with patch('hermes_pi_bridge.tools.status.PiHttpClient') as mock_client_class:
            mock_client = Mock()
            mock_client.get_status = Mock(return_value={
                "available": True,
                "version": "0.75.0",
                "max_concurrent": 2,
                "current_load": 0,
                "capabilities": ["delegate", "status"],
            })
            mock_client_class.return_value = mock_client
            
            tool = PiStatusTool(config)
            tool.client = mock_client
            return tool
    
    def test_tool_name(self, tool):
        """Tool has correct name."""
        assert tool.name == "pi_status"
    
    def test_tool_no_required_parameters(self, tool):
        """Status tool has no required parameters."""
        params = tool.parameters
        assert params["type"] == "object"
        assert len(params.get("required", [])) == 0
    
    def test_execute_returns_availability(self, tool):
        """Execute returns pi availability status."""
        result = tool.execute()
        result_data = json.loads(result)
        
        assert result_data["ok"] == True
        assert result_data["available"] == True
        assert result_data["version"] == "0.75.0"
        assert result_data["max_concurrent"] == 2
    
    def test_execute_handles_unavailable(self, tool):
        """Execute handles pi not available."""
        tool.client.get_status = Mock(return_value={
            "available": False,
            "reason": "Connection refused",
        })
        
        result = tool.execute()
        result_data = json.loads(result)
        
        assert result_data["ok"] == True
        assert result_data["available"] == False
        assert "reason" in result_data
    
    def test_execute_handles_exception(self, tool):
        """Execute handles connection errors."""
        tool.client.get_status = Mock(side_effect=Exception("Connection refused"))
        
        result = tool.execute()
        result_data = json.loads(result)
        
        assert result_data["ok"] == True
        assert result_data["available"] == False


class TestBridgeConfig:
    """Test configuration management."""
    
    def test_default_config(self, tmp_path):
        """Default configuration has sensible values."""
        config = BridgeConfig(hermes_home=tmp_path)
        
        assert config.pi_url == "http://localhost:2719"
        assert config.timeout_seconds == 300
        assert config.max_concurrent == 2
        assert config.auth_token == ""
    
    def test_config_from_env(self, tmp_path, monkeypatch):
        """Can override config from environment variables."""
        monkeypatch.setenv("HERMES_PI_BRIDGE_PI_URL", "http://custom:8080")
        monkeypatch.setenv("HERMES_PI_BRIDGE_TIMEOUT", "600")
        
        config = BridgeConfig(hermes_home=tmp_path)
        
        assert config.pi_url == "http://custom:8080"
        assert config.timeout_seconds == 600
    
    def test_config_kanban_path(self, tmp_path):
        """Kanban path is derived from hermes home."""
        config = BridgeConfig(hermes_home=tmp_path)
        
        assert config.kanban_db == tmp_path / "kanban.db"
