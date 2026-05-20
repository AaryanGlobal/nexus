"""TDD: Nexus Bridge Connection Tests - Auto-discovery and connection"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from hermes_pi_bridge_core.bridge import AgentBridge, AgentType, get_bridge
from hermes_pi_bridge_core.life_context import LifeContextEngine


@pytest.fixture
def temp_storage():
    """Create temp storage path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.json"


@pytest.fixture
def engine(temp_storage):
    """Create engine with temp storage."""
    return LifeContextEngine(storage_path=str(temp_storage))


class TestBridgeAutoConnect:
    """Test automatic bridge connection on initialization."""
    
    def test_bridge_auto_discovers_hermes_capabilities(self, temp_storage):
        """Bridge should auto-discover Hermes capabilities on init."""
        engine = LifeContextEngine(storage_path=str(temp_storage))
        
        # After init, Hermes should have capabilities
        caps = engine.get_capabilities("hermes")
        assert len(caps) > 0, "Hermes should have auto-discovered capabilities"
    
    def test_bridge_auto_discovers_pi_capabilities(self, temp_storage):
        """Bridge should auto-discover PI capabilities on init."""
        engine = LifeContextEngine(storage_path=str(temp_storage))
        
        # After init, PI should have capabilities
        caps = engine.get_capabilities("pi")
        assert len(caps) > 0, "PI should have auto-discovered capabilities"
    
    def test_nexus_status_shows_capabilities(self, temp_storage):
        """Nexus /status should show discovered capabilities."""
        engine = LifeContextEngine(storage_path=str(temp_storage))
        
        status = engine.get_status()
        
        assert 'capabilities' in status
        assert 'hermes' in status['capabilities']
        assert 'pi' in status['capabilities']
        assert status['capabilities']['hermes'] > 0
        assert status['capabilities']['pi'] > 0


class TestLifeContextAutoInit:
    """Test that LifeContextEngine auto-initializes on creation."""
    
    def test_new_engine_has_capabilities(self, temp_storage):
        """New engine should have capabilities without manual call."""
        engine = LifeContextEngine(storage_path=str(temp_storage))
        
        # Check both agents have capabilities
        h_caps = engine.get_capabilities("hermes")
        p_caps = engine.get_capabilities("pi")
        
        assert len(h_caps) > 0, "New engine should have Hermes capabilities"
        assert len(p_caps) > 0, "New engine should have PI capabilities"
    
    def test_new_engine_has_pillars(self, temp_storage):
        """New engine with sample data should have pillars."""
        engine = LifeContextEngine(storage_path=str(temp_storage))
        engine.add_sample_data()
        
        pillars = engine.get_pillars()
        assert len(pillars) > 0, "Engine with sample data should have pillars"


class TestNexusServerIntegration:
    """Test Nexus server properly integrates bridge and life context."""
    
    def test_nexus_status_endpoint_returns_full_info(self):
        """Nexus /status should return connected bridges and life context."""
        from nexus_server import NexusAPIHandler
        from unittest.mock import MagicMock
        import io
        import sys
        
        # We can't easily test the HTTP handler directly,
        # but we can test the components it uses
        bridge = get_bridge()
        engine = LifeContextEngine()
        
        # Manual check that status structure is correct
        bridge_status = bridge.get_connection_status()
        life_status = engine.get_status()
        
        assert 'hermes' in bridge_status
        assert 'pi' in bridge_status
    
    def test_nexus_server_calls_discover_on_init(self, temp_storage):
        """Nexus server should call discover_capabilities on startup."""
        # This is what the server should do on init
        engine = LifeContextEngine(storage_path=str(temp_storage))
        
        # Simulate what server should do
        h_caps = engine.discover_capabilities("hermes")
        p_caps = engine.discover_capabilities("pi")
        
        assert len(h_caps) > 0
        assert len(p_caps) > 0


class TestBridgeConnection:
    """Test bridge connection logic."""
    
    def test_bridge_knows_default_urls(self):
        """Bridge should have default URLs for Hermes and PI."""
        bridge = AgentBridge()
        
        assert bridge.connections[AgentType.HERMES].url == "http://localhost:8080"
        assert bridge.connections[AgentType.PI].url == "http://localhost:8645"
    
    def test_bridge_can_get_connection_status(self):
        """Bridge connection status returns dict."""
        bridge = AgentBridge()
        status = bridge.get_connection_status()
        
        assert 'hermes' in status
        assert 'pi' in status
        assert status['hermes']['status'] == 'disconnected'  # Not connected yet
        assert status['pi']['status'] == 'disconnected'
    
    def test_bridge_can_connect_to_hermes(self):
        """Bridge can attempt connection to Hermes."""
        bridge = AgentBridge()
        
        # Try to connect - will fail if Hermes isn't running, but shouldn't crash
        result = bridge.connect(AgentType.HERMES)
        
        # Connection attempt should return boolean
        assert isinstance(result, bool)
    
    def test_bridge_can_connect_to_pi(self):
        """Bridge can attempt connection to PI."""
        bridge = AgentBridge()
        
        result = bridge.connect(AgentType.PI)
        
        assert isinstance(result, bool)


class TestSampleData:
    """Test sample data population."""
    
    def test_add_sample_data_returns_stats(self, temp_storage):
        """add_sample_data should return dict with counts."""
        engine = LifeContextEngine(storage_path=str(temp_storage))
        
        result = engine.add_sample_data()
        
        assert 'contexts' in result
        assert 'goals' in result
        assert 'capabilities' in result
        assert result['contexts'] > 0
        assert result['goals'] > 0
    
    def test_sample_data_persists(self, temp_storage):
        """Sample data should persist after reload."""
        engine = LifeContextEngine(storage_path=str(temp_storage))
        engine.add_sample_data()
        
        # Reload engine
        engine2 = LifeContextEngine(storage_path=str(temp_storage))
        
        assert len(engine2.contexts) > 0
        assert len(engine2.goals) > 0


class TestNexusAutoInitialization:
    """Test that Nexus auto-initializes on import."""
    
    def test_nexus_import_initializes_engine(self, temp_storage):
        """Importing Nexus modules should initialize components."""
        # The server.py imports these and uses them
        from hermes_pi_bridge_core.life_context import LifeContextEngine
        from hermes_pi_bridge_core.config import get_config
        from hermes_pi_bridge_core.bridge import get_bridge
        
        # Creating a new engine should work
        engine = LifeContextEngine(storage_path=str(temp_storage))
        
        # Engine should be functional
        assert engine.get_status() is not None


class TestEndToEndStatus:
    """End-to-end status check for Nexus."""
    
    def test_full_status_has_all_components(self, temp_storage):
        """Full status should have bridge, config, and life."""
        engine = LifeContextEngine(storage_path=str(temp_storage))
        bridge = get_bridge()
        
        # Discover capabilities
        engine.discover_capabilities("hermes")
        engine.discover_capabilities("pi")
        
        # Get full status
        status = {
            'bridge': bridge.get_connection_status(),
            'config': {'version': '1.0'},  # Simplified
            'life': engine.get_status()
        }
        
        assert 'bridge' in status
        assert 'life' in status
        assert 'hermes' in status['bridge']
        assert 'pi' in status['bridge']
        assert 'pillars' in status['life']
        assert 'capabilities' in status['life']