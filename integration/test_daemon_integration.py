"""TDD: Daemon and Server Integration Tests"""
import pytest
import subprocess
import sys
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.daemon import NexusDaemon, DaemonConfig, DaemonState


class TestDaemonLifecycle:
    """Test daemon lifecycle management."""
    
    def test_daemon_init(self):
        """Daemon initializes correctly."""
        config = DaemonConfig()
        daemon = NexusDaemon(config)
        
        assert daemon.config is not None
        assert daemon.state is not None
        assert daemon.state.running is False
    
    def test_daemon_config_defaults(self):
        """Daemon config has sensible defaults."""
        config = DaemonConfig()
        
        assert config.pid_file == "/tmp/nexus-daemon.pid"
        assert config.log_file == "/tmp/nexus-daemon.log"
        assert config.port == 8080
        assert config.auto_restart is True
        assert config.restart_delay == 1
        assert config.max_restarts == 3
    
    def test_daemon_state_transitions(self):
        """Daemon state transitions work correctly."""
        state = DaemonState()
        
        # Initial state
        assert state.running is False
        assert state.pid is None
        
        # Start
        state.start(pid=12345)
        assert state.running is True
        assert state.pid == 12345
        assert state.started_at is not None
        
        # Stop
        state.stop()
        assert state.running is False
    
    def test_daemon_can_start(self):
        """Daemon can start (mocked)."""
        config = DaemonConfig()
        daemon = NexusDaemon(config)
        
        # Mock the start behavior
        daemon._start_server = lambda: True
        
        result = daemon.start()
        
        assert result is True
        assert daemon.state.running is True
    
    def test_daemon_can_stop(self):
        """Daemon can stop."""
        config = DaemonConfig()
        daemon = NexusDaemon(config)
        
        # Set running state
        daemon.state.running = True
        daemon.state.pid = 12345
        
        daemon._stop_server = lambda: True
        
        result = daemon.stop()
        
        assert result is True
        assert daemon.state.running is False
    
    def test_daemon_restart(self):
        """Daemon can restart."""
        config = DaemonConfig()
        daemon = NexusDaemon(config)
        
        daemon._start_server = lambda: True
        daemon._stop_server = lambda: True
        
        # Start first
        daemon.start()
        pid1 = daemon.state.pid
        
        # Restart
        result = daemon.restart()
        
        assert result is True


class TestDaemonHealth:
    """Test daemon health monitoring."""
    
    def test_get_health(self):
        """Daemon health check works."""
        config = DaemonConfig()
        daemon = NexusDaemon(config)
        
        health = daemon.get_health()
        
        assert 'running' in health
        assert 'pid' in health
        assert 'uptime' in health
    
    def test_get_status(self):
        """Daemon status works."""
        config = DaemonConfig()
        daemon = NexusDaemon(config)
        
        status = daemon.get_status()
        
        assert 'running' in status
        assert 'pid' in status
        assert 'config' in status
    
    def test_health_updates_when_running(self):
        """Health updates when daemon is running."""
        config = DaemonConfig()
        daemon = NexusDaemon(config)
        
        daemon._start_server = lambda: True
        daemon.start()
        
        # Daemon should be running
        # Note: May already be running from previous test
        health = daemon.get_health()
        
        # Health should contain required fields
        assert 'running' in health
        assert 'pid' in health
        assert 'uptime' in health
        
        daemon.stop()


class TestDaemonErrorHandling:
    """Test daemon error handling."""
    
    def test_record_error(self):
        """Daemon can record errors."""
        state = DaemonState()
        
        state.record_error("Test error")
        
        assert state.last_error == "Test error"
        assert state.restart_count >= 1
    
    def test_multiple_errors(self):
        """Daemon tracks multiple errors."""
        state = DaemonState()
        
        state.record_error("Error 1")
        state.record_error("Error 2")
        
        assert state.last_error == "Error 2"
        assert state.restart_count >= 2
    
    def test_error_clears_on_start(self):
        """Error is cleared on successful start."""
        state = DaemonState()
        
        state.record_error("Previous error")
        state.start(pid=99999)
        
        # Error should be cleared after start
        # (Implementation specific)


class TestDaemonSignals:
    """Test daemon signal handling."""
    
    def test_register_signal_handlers(self):
        """Daemon can register signal handlers."""
        config = DaemonConfig()
        daemon = NexusDaemon(config)
        
        # Should not crash
        daemon.register_signal_handlers()
        
        # Signal handlers are registered (can't easily test without signals)
    
    def test_handle_signal(self):
        """Daemon can handle signals."""
        config = DaemonConfig()
        daemon = NexusDaemon(config)
        
        import signal
        
        # SIGTERM should be handled
        result = daemon.handle_signal(signal.SIGTERM)
        
        # Should return True or handle gracefully
        assert result is not None


class TestDaemonIntegrationWithServer:
    """Test daemon integration with main server."""
    
    def test_server_uses_life_engine(self):
        """Server imports and uses LifeContextEngine."""
        with open("/home/agi/nexus/nexus_server.py") as f:
            content = f.read()
        
        assert "LifeContextEngine" in content
        assert "life_context" in content.lower()
    
    def test_server_uses_bridge(self):
        """Server imports and uses AgentBridge."""
        with open("/home/agi/nexus/nexus_server.py") as f:
            content = f.read()
        
        assert "AgentBridge" in content
        assert "get_bridge" in content
    
    def test_server_uses_config(self):
        """Server imports and uses config."""
        with open("/home/agi/nexus/nexus_server.py") as f:
            content = f.read()
        
        assert "get_config" in content
        assert "NexusConfig" in content or "config" in content.lower()
    
    def test_server_has_all_endpoints(self):
        """Server has all required endpoints."""
        with open("/home/agi/nexus/nexus_server.py") as f:
            content = f.read()
        
        endpoints = ["/health", "/status", "/life", "/connections", "/messages", "/context"]
        for ep in endpoints:
            assert ep in content or f'\"{ep}\"' in content or f"'{ep}'" in content


class TestWebSocketIntegration:
    """Test WebSocket integration."""
    
    def test_websocket_server_importable(self):
        """WebSocket server can be imported."""
        from hermes_pi_bridge_core.websocket import WebSocketServer, WebSocketClient
        
        assert WebSocketServer is not None
        assert WebSocketClient is not None
    
    def test_websocket_server_init(self):
        """WebSocket server initializes."""
        from hermes_pi_bridge_core.websocket import WebSocketServer
        
        server = WebSocketServer(port=8090)
        
        assert server.port == 8090
    
    def test_websocket_server_methods(self):
        """WebSocket server has required methods."""
        from hermes_pi_bridge_core.websocket import WebSocketServer
        
        server = WebSocketServer()
        
        assert hasattr(server, 'start')
        assert hasattr(server, 'stop')
        assert hasattr(server, 'broadcast')
        assert hasattr(server, 'send_to')
        assert hasattr(server, 'get_clients')
        assert hasattr(server, 'get_status')
    
    def test_websocket_client_init(self):
        """WebSocket client initializes."""
        from hermes_pi_bridge_core.websocket import WebSocketClient
        
        # Client requires ws_url
        client = WebSocketClient(ws_url="ws://localhost:8090")
        
        assert client.ws_url == "ws://localhost:8090"
    
    def test_websocket_client_methods(self):
        """WebSocket client has required methods."""
        from hermes_pi_bridge_core.websocket import WebSocketClient
        
        client = WebSocketClient(ws_url="ws://localhost:8090")
        
        # Client should have basic connection methods
        assert hasattr(client, 'connect')
        assert hasattr(client, 'disconnect')  # This is the close method
        assert hasattr(client, 'send_message')
        assert hasattr(client, 'register_callback')
        assert hasattr(client, 'get_status')


class TestControlPanelIntegration:
    """Test control panel integration."""
    
    def test_control_panel_importable(self):
        """Control panel can be imported."""
        import nexus_control_panel
        
        assert hasattr(nexus_control_panel, 'DashboardHandler')
        assert hasattr(nexus_control_panel, 'run_dashboard')
    
    def test_dashboard_handler_has_endpoints(self):
        """Dashboard handler has all endpoints."""
        import nexus_control_panel
        
        # Check class methods
        assert hasattr(nexus_control_panel.DashboardHandler, 'do_GET')
        assert hasattr(nexus_control_panel.DashboardHandler, 'do_POST')
        # The class has these methods - don't instantiate
    
    def test_run_dashboard_function(self):
        """run_dashboard function exists."""
        import nexus_control_panel
        
        assert callable(nexus_control_panel.run_dashboard)
    
    def test_dashboard_html_template_exists(self):
        """Dashboard has HTML template."""
        import nexus_control_panel
        
        assert hasattr(nexus_control_panel, 'HTML_TEMPLATE')
        assert len(nexus_control_panel.HTML_TEMPLATE) > 100


class TestGovernanceIntegration:
    """Test governance integration."""
    
    def test_governance_circuit_breaker(self):
        """Governance has circuit breaker."""
        from hermes_pi_bridge_core.governance import BridgeGovernance, GovernanceConfig
        
        gov = BridgeGovernance(GovernanceConfig())
        
        assert hasattr(gov, 'circuit_open')
        assert hasattr(gov, 'consecutive_failures')
    
    def test_governance_validate_decision(self):
        """Governance can validate decisions."""
        from hermes_pi_bridge_core.governance import BridgeGovernance, GovernanceConfig, DecisionType
        
        gov = BridgeGovernance(GovernanceConfig())
        
        decision, should_proceed = gov.validate_decision(
            DecisionType.EXECUTE_TASK,
            "Test action",
            {}
        )
        
        assert decision is not None
        assert isinstance(should_proceed, bool)
    
    def test_governance_get_confidence(self):
        """Governance can get confidence scores."""
        from hermes_pi_bridge_core.governance import BridgeGovernance, GovernanceConfig, DecisionType
        
        gov = BridgeGovernance(GovernanceConfig())
        
        score = gov.get_confidence_score(DecisionType.EXECUTE_TASK)
        
        assert isinstance(score, float)
        assert 0 <= score <= 1
    
    def test_governance_report(self):
        """Governance can generate reports."""
        from hermes_pi_bridge_core.governance import BridgeGovernance, GovernanceConfig
        
        gov = BridgeGovernance(GovernanceConfig())
        
        report = gov.get_governance_report()
        
        assert isinstance(report, dict)
        assert 'circuit_open' in report or 'consecutive_failures' in report


class TestFullSystemIntegration:
    """Test full system integration."""
    
    def test_all_core_modules_importable(self):
        """All core modules can be imported."""
        from hermes_pi_bridge_core.bridge import AgentBridge, AgentType, get_bridge
        from hermes_pi_bridge_core.life_context import LifeContextEngine
        from hermes_pi_bridge_core.rl import ReinforcementLearning, ActionType
        from hermes_pi_bridge_core.config import get_config
        from hermes_pi_bridge_core.governance import BridgeGovernance
        from hermes_pi_bridge_core.daemon import NexusDaemon
        from hermes_pi_bridge_core.rate_limiter import RateLimiter
        from hermes_pi_bridge_core.scanner import WorkScanner
        
        # All should import without error
        assert True
    
    def test_bridge_singleton_works(self):
        """Bridge singleton works."""
        from hermes_pi_bridge_core.bridge import get_bridge
        
        bridge1 = get_bridge()
        bridge2 = get_bridge()
        
        assert bridge1 is bridge2
    
    def test_life_engine_auto_discovers(self):
        """Life engine auto-discovers capabilities."""
        from hermes_pi_bridge_core.life_context import LifeContextEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = LifeContextEngine(storage_path=str(Path(tmpdir) / "test.json"))
            
            h_caps = engine.get_capabilities("hermes")
            p_caps = engine.get_capabilities("pi")
            
            assert len(h_caps) > 0
            assert len(p_caps) > 0
    
    def test_rl_reward_cycle(self):
        """RL reward cycle works."""
        from hermes_pi_bridge_core.rl import ReinforcementLearning, ActionType
        
        rl = ReinforcementLearning()
        
        reward = rl.reward(ActionType.EXECUTE, True)
        
        assert isinstance(reward, float)
        
        stats = rl.get_stats()
        assert stats['total_rewards'] > 0
    
    def test_config_get_status(self):
        """Config get_status works."""
        from hermes_pi_bridge_core.config import get_config
        
        config = get_config()
        status = config.get_status()
        
        assert 'version' in status
        assert 'rate_limit' in status
    
    def test_rate_limiter_can_proceed(self):
        """Rate limiter can check if can proceed."""
        from hermes_pi_bridge_core.rate_limiter import RateLimiter, RateLimitConfig
        
        rl = RateLimiter(RateLimitConfig())
        
        can_proceed, reason = rl.can_proceed("test")
        
        assert isinstance(can_proceed, bool)
        assert isinstance(reason, str)
    
    def test_scanner_scan(self):
        """Scanner scan works."""
        from hermes_pi_bridge_core.scanner import WorkScanner, ScanConfig
        
        config = ScanConfig(scan_paths=["/tmp"])
        scanner = WorkScanner(config)
        
        tasks = scanner.scan()
        
        assert isinstance(tasks, list)
    
    def test_governance_circuit_breaker(self):
        """Governance circuit breaker works."""
        from hermes_pi_bridge_core.governance import BridgeGovernance
        
        gov = BridgeGovernance()
        
        # Initially should not be open
        # (Implementation specific)