"""TDD: Nexus Server Integration Tests - End-to-end with running server"""
import pytest
import json
import time
import subprocess
import sys
import socket
import tempfile
from pathlib import Path
import http.client


# Path to the nexus server
NEXUS_SERVER_PATH = Path(__file__).parent.parent / "nexus_server.py"


def is_port_in_use(port):
    """Check if port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def find_available_port(start=8181, end=8200):
    """Find an available port."""
    for port in range(start, end):
        if not is_port_in_use(port):
            return port
    return None


def http_get(port, path):
    """Make HTTP GET request."""
    conn = http.client.HTTPConnection("localhost", port, timeout=5)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read().decode()
        try:
            data = json.loads(body)
        except:
            data = body
        return {"status": resp.status, "data": data}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def http_post(port, path, data):
    """Make HTTP POST request."""
    conn = http.client.HTTPConnection("localhost", port, timeout=5)
    try:
        headers = {"Content-Type": "application/json"}
        conn.request("POST", path, json.dumps(data), headers)
        resp = conn.getresponse()
        body = resp.read().decode()
        try:
            data = json.loads(body)
        except:
            data = body
        return {"status": resp.status, "data": data}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def wait_for_server(port, max_attempts=20):
    """Wait for server to be ready."""
    for i in range(max_attempts):
        result = http_get(port, "/health")
        if result.get("status") == 200:
            return True
        time.sleep(0.25)
    return False


@pytest.fixture(scope="module")
def nexus_server():
    """Start Nexus server for tests."""
    port = find_available_port()
    if port is None:
        pytest.skip("Could not find available port")
    
    # Start server process
    env = {
        "PYTHONPATH": str(Path(__file__).parent.parent / "packages" / "core" / "src"),
    }
    
    proc = subprocess.Popen(
        [sys.executable, str(NEXUS_SERVER_PATH), "--port", str(port)],
        env={**subprocess.os.environ, **env},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(Path(__file__).parent.parent)
    )
    
    # Wait for server to start
    if not wait_for_server(port):
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except:
            proc.kill()
        pytest.fail(f"Server failed to start on port {port}")
    
    yield {"port": port, "proc": proc}
    
    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


class TestNexusServerEndpoints:
    """Test Nexus server HTTP endpoints."""
    
    def test_health_endpoint(self, nexus_server):
        """GET /health returns ok status."""
        result = http_get(nexus_server["port"], "/health")
        
        assert result["status"] == 200
        assert result["data"]["status"] == "ok"
        assert "time" in result["data"]
    
    def test_status_endpoint_structure(self, nexus_server):
        """GET /status returns bridge, config, and life."""
        result = http_get(nexus_server["port"], "/status")
        
        assert result["status"] == 200
        data = result["data"]
        
        assert "bridge" in data
        assert "config" in data
        assert "life" in data
    
    def test_status_has_hermes_connection(self, nexus_server):
        """GET /status shows Hermes bridge."""
        result = http_get(nexus_server["port"], "/status")
        
        assert "hermes" in result["data"]["bridge"]
        assert "url" in result["data"]["bridge"]["hermes"]
        assert "status" in result["data"]["bridge"]["hermes"]
    
    def test_status_has_pi_connection(self, nexus_server):
        """GET /status shows PI bridge."""
        result = http_get(nexus_server["port"], "/status")
        
        assert "pi" in result["data"]["bridge"]
        assert "url" in result["data"]["bridge"]["pi"]
        assert "status" in result["data"]["bridge"]["pi"]
    
    def test_status_has_capabilities(self, nexus_server):
        """GET /status shows capabilities (auto-discovered)."""
        result = http_get(nexus_server["port"], "/status")
        
        life = result["data"]["life"]
        assert "capabilities" in life
        assert "hermes" in life["capabilities"]
        assert "pi" in life["capabilities"]
        
        # Capabilities should be auto-discovered (not zero)
        assert life["capabilities"]["hermes"] > 0
        assert life["capabilities"]["pi"] > 0
    
    def test_life_endpoint(self, nexus_server):
        """GET /life returns life context status."""
        result = http_get(nexus_server["port"], "/life")
        
        assert result["status"] == 200
        data = result["data"]
        
        assert "capabilities" in data
        assert "pillars" in data
        assert "goals_total" in data
    
    def test_connections_endpoint(self, nexus_server):
        """GET /connections returns connection status."""
        result = http_get(nexus_server["port"], "/connections")
        
        assert result["status"] == 200
        assert "hermes" in result["data"]
        assert "pi" in result["data"]
    
    def test_context_endpoint(self, nexus_server):
        """GET /context returns shared context."""
        result = http_get(nexus_server["port"], "/context")
        
        assert result["status"] == 200
        assert isinstance(result["data"], dict)
    
    def test_messages_endpoint(self, nexus_server):
        """GET /messages returns message history."""
        result = http_get(nexus_server["port"], "/messages")
        
        assert result["status"] == 200
        assert isinstance(result["data"], list)


class TestNexusServerPostEndpoints:
    """Test POST endpoints."""
    
    def test_connect_hermes(self, nexus_server):
        """POST /connect can connect to Hermes."""
        result = http_post(nexus_server["port"], "/connect", {
            "agent": "hermes",
            "url": "http://localhost:8080"
        })
        
        assert result["status"] == 200
        assert "success" in result["data"]
    
    def test_connect_pi(self, nexus_server):
        """POST /connect can connect to PI."""
        result = http_post(nexus_server["port"], "/connect", {
            "agent": "pi",
            "url": "http://localhost:9999"
        })
        
        assert result["status"] == 200
        assert "success" in result["data"]
    
    def test_sync_context(self, nexus_server):
        """POST /sync updates shared context."""
        result = http_post(nexus_server["port"], "/sync", {
            "context": {
                "test_key": "test_value"
            }
        })
        
        assert result["status"] == 200
        assert result["data"]["success"] is True
    
    def test_update_context(self, nexus_server):
        """POST /context updates specific key."""
        result = http_post(nexus_server["port"], "/context", {
            "key": "test_key",
            "value": "test_value"
        })
        
        assert result["status"] == 200
        assert result["data"]["success"] is True
    
    def test_invalid_json_returns_error(self, nexus_server):
        """Invalid JSON returns 400."""
        conn = http.client.HTTPConnection("localhost", nexus_server["port"], timeout=5)
        try:
            conn.request("POST", "/connect", "not json", {"Content-Type": "application/json"})
            resp = conn.getresponse()
            assert resp.status == 400
        finally:
            conn.close()
    
    def test_unknown_endpoint_returns_404(self, nexus_server):
        """Unknown endpoint returns 404."""
        result = http_get(nexus_server["port"], "/nonexistent")
        
        assert result["status"] == 404


class TestNexusConnectivity:
    """Test actual connectivity to external services."""
    
    def test_can_attempt_hermes_connection(self, nexus_server):
        """Server can attempt connection to Hermes."""
        result = http_post(nexus_server["port"], "/connect", {
            "agent": "hermes"
        })
        
        status = http_get(nexus_server["port"], "/status")
        assert status["status"] == 200
    
    def test_connection_status_reflects_result(self, nexus_server):
        """Connection status reflects attempt result."""
        http_post(nexus_server["port"], "/connect", {
            "agent": "pi",
            "url": "http://localhost:9999"
        })
        
        result = http_get(nexus_server["port"], "/connections")
        
        assert "pi" in result["data"]
        assert "status" in result["data"]["pi"]


class TestNexusRobustness:
    """Test server handles edge cases."""
    
    def test_handles_empty_post_body(self, nexus_server):
        """Handles empty POST body gracefully."""
        conn = http.client.HTTPConnection("localhost", nexus_server["port"], timeout=5)
        try:
            conn.request("POST", "/connect", "", {"Content-Type": "application/json"})
            resp = conn.getresponse()
            assert resp.status in [200, 400]
        finally:
            conn.close()
    
    def test_handles_missing_fields(self, nexus_server):
        """Handles missing POST fields gracefully."""
        result = http_post(nexus_server["port"], "/connect", {})
        
        assert result["status"] == 200
        assert "success" in result["data"]
    
    def test_multiple_health_checks(self, nexus_server):
        """Multiple health checks don't cause issues."""
        for _ in range(10):
            result = http_get(nexus_server["port"], "/health")
            assert result["status"] == 200


class TestNexusConfiguration:
    """Test configuration integration."""
    
    def test_config_in_status(self, nexus_server):
        """Config is included in status."""
        result = http_get(nexus_server["port"], "/status")
        
        config = result["data"]["config"]
        assert "version" in config
        assert config["version"] == "1.0"
    
    def test_config_has_rate_limits(self, nexus_server):
        """Config includes rate limits."""
        result = http_get(nexus_server["port"], "/status")
        
        config = result["data"]["config"]
        assert "rate_limit" in config
        assert "per_minute" in config["rate_limit"]
    
    def test_config_has_governance(self, nexus_server):
        """Config includes governance settings."""
        result = http_get(nexus_server["port"], "/status")
        
        config = result["data"]["config"]
        assert "governance" in config
        assert "min_confidence" in config["governance"]


class TestNexusLifeGoals:
    """Test life goals functionality."""
    
    def test_life_shows_goals_total(self, nexus_server):
        """Life endpoint shows goals count."""
        result = http_get(nexus_server["port"], "/life")
        
        assert "goals_total" in result["data"]
        assert isinstance(result["data"]["goals_total"], int)
    
    def test_life_shows_goals_completed(self, nexus_server):
        """Life endpoint shows completed goals."""
        result = http_get(nexus_server["port"], "/life")
        
        assert "goals_completed" in result["data"]
        assert isinstance(result["data"]["goals_completed"], int)
    
    def test_life_shows_pending_votes(self, nexus_server):
        """Life endpoint shows pending governance votes."""
        result = http_get(nexus_server["port"], "/life")
        
        assert "pending_votes" in result["data"]
        assert isinstance(result["data"]["pending_votes"], int)


class TestNexusCORS:
    """Test CORS headers for web integration."""
    
    def test_cors_header_present(self, nexus_server):
        """CORS header is present in responses."""
        conn = http.client.HTTPConnection("localhost", nexus_server["port"], timeout=5)
        try:
            conn.request("GET", "/health")
            resp = conn.getresponse()
            
            assert resp.getheader("Access-Control-Allow-Origin") == "*"
        finally:
            conn.close()


class TestNexusJSONResponses:
    """Test JSON response format."""
    
    def test_all_endpoints_return_json(self, nexus_server):
        """All endpoints return valid JSON."""
        endpoints = ["/health", "/status", "/connections", "/messages", "/context", "/life"]
        
        for ep in endpoints:
            result = http_get(nexus_server["port"], ep)
            assert result["status"] == 200
            assert isinstance(result["data"], (dict, list))
    
    def test_post_endpoints_return_json(self, nexus_server):
        """POST endpoints return valid JSON."""
        result = http_post(nexus_server["port"], "/sync", {"context": {}})
        assert result["status"] == 200
        assert isinstance(result["data"], dict)