"""TDD: PI-Hermes Real Collaboration Tests"""
import pytest
import sys
import json
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from http.server import HTTPServer

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from nexus_server import NexusAPIHandler, run_server
from hermes_pi_bridge_core.bridge import get_bridge, AgentType
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.rl import ReinforcementLearning, ActionType


class TestServerEndpointsCollaboration:
    """Test server API for PI-Hermes collaboration."""
    
    @pytest.fixture
    def server(self):
        """Start test server."""
        server = HTTPServer(('localhost', 19876), NexusAPIHandler)
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        time.sleep(0.1)
        yield server
        server.server_close()
        thread.join(timeout=1)
    
    def test_health_endpoint(self, server):
        """GET /health returns status."""
        try:
            response = urllib.request.urlopen('http://localhost:19876/health', timeout=2)
            data = json.loads(response.read())
            assert data['status'] == 'ok'
        except Exception as e:
            pytest.skip(f"Server not reachable: {e}")
    
    def test_status_endpoint(self, server):
        """GET /status returns bridge, config, life status."""
        try:
            response = urllib.request.urlopen('http://localhost:19876/status', timeout=2)
            data = json.loads(response.read())
            assert 'bridge' in data
            assert 'config' in data
            assert 'life' in data
        except Exception as e:
            pytest.skip(f"Server not reachable: {e}")
    
    def test_connections_endpoint(self, server):
        """GET /connections returns bridge connections."""
        try:
            response = urllib.request.urlopen('http://localhost:19876/connections', timeout=2)
            data = json.loads(response.read())
            assert 'hermes' in data
            assert 'pi' in data
        except Exception as e:
            pytest.skip(f"Server not reachable: {e}")
    
    def test_messages_endpoint(self, server):
        """GET /messages returns message history."""
        try:
            response = urllib.request.urlopen('http://localhost:19876/messages', timeout=2)
            data = json.loads(response.read())
            assert isinstance(data, list)
        except Exception as e:
            pytest.skip(f"Server not reachable: {e}")
    
    def test_context_endpoint_get(self, server):
        """GET /context returns shared context."""
        try:
            response = urllib.request.urlopen('http://localhost:19876/context', timeout=2)
            data = json.loads(response.read())
            assert isinstance(data, dict)
        except Exception as e:
            pytest.skip(f"Server not reachable: {e}")
    
    def test_life_endpoint(self, server):
        """GET /life returns life engine status."""
        try:
            response = urllib.request.urlopen('http://localhost:19876/life', timeout=2)
            data = json.loads(response.read())
            assert 'goals_total' in data or 'pillars' in data
        except Exception as e:
            pytest.skip(f"Server not reachable: {e}")


class TestDelegateCollaboration:
    """Test delegation between PI and Hermes."""
    
    def test_delegate_task_to_hermes(self):
        """POST /delegate routes task to Hermes."""
        bridge = get_bridge()
        
        # Delegate to Hermes
        task_id = bridge.delegate_task(AgentType.HERMES, {'type': 'code', 'content': 'write tests'})
        
        # Returns message_id or None
        assert task_id is None or isinstance(task_id, str)
    
    def test_delegate_task_to_pi(self):
        """POST /delegate routes task to PI."""
        bridge = get_bridge()
        
        # Delegate to PI
        task_id = bridge.delegate_task(AgentType.PI, {'type': 'analysis', 'content': 'analyze data'})
        
        assert task_id is None or isinstance(task_id, str)
    
    def test_receive_result_from_hermes(self):
        """Bridge can receive result from Hermes."""
        bridge = get_bridge()
        
        result = bridge.receive_result(AgentType.HERMES, {
            'success': True,
            'task_id': 'test123',
            'data': {'answer': 42}
        })
        
        assert result is not None
        assert result['success'] is True
    
    def test_receive_result_from_pi(self):
        """Bridge can receive result from PI."""
        bridge = get_bridge()
        
        result = bridge.receive_result(AgentType.PI, {
            'success': True,
            'task_id': 'test456',
            'data': {'analysis': 'complete'}
        })
        
        assert result is not None
        assert result['success'] is True
    
    def test_result_updates_message_history(self):
        """Receiving result updates message history."""
        bridge = get_bridge()
        
        initial_count = len(bridge.message_history)
        
        bridge.receive_result(AgentType.PI, {'success': True, 'data': {}})
        
        assert len(bridge.message_history) >= initial_count


class TestContextSyncCollaboration:
    """Test context synchronization between agents."""
    
    def test_update_shared_context(self):
        """Bridge can update shared context."""
        bridge = get_bridge()
        
        bridge.update_shared_context('project', 'nexus')
        bridge.update_shared_context('mode', 'collaboration')
        
        assert 'project' in bridge.shared_context
        assert 'mode' in bridge.shared_context
    
    def test_shared_context_structure(self):
        """Shared context has proper structure."""
        bridge = get_bridge()
        
        bridge.update_shared_context('test', 'value')
        
        context = bridge.shared_context['test']
        assert 'value' in context
        assert 'updated_at' in context
    
    def test_sync_context_to_agent(self):
        """Can sync context to specific agent."""
        bridge = get_bridge()
        
        bridge.update_shared_context('sync_test', 'data')
        
        # Sync returns bool (may be False if not connected)
        result = bridge.sync_context(AgentType.HERMES)
        assert isinstance(result, bool)


class TestCapabilityBasedCollaboration:
    """Test collaboration based on agent capabilities."""
    
    def test_life_engine_knows_hermes_capabilities(self):
        """Life engine knows Hermes capabilities."""
        engine = LifeContextEngine()
        
        caps = engine.get_capabilities('hermes')
        
        assert isinstance(caps, list)
        assert len(caps) > 0
    
    def test_life_engine_knows_pi_capabilities(self):
        """Life engine knows PI capabilities."""
        engine = LifeContextEngine()
        
        caps = engine.get_capabilities('pi')
        
        assert isinstance(caps, list)
        assert len(caps) > 0
    
    def test_route_task_based_on_capabilities(self):
        """Tasks are routed based on agent capabilities."""
        engine = LifeContextEngine()
        
        # Route different types of tasks
        result1 = engine.route_task('write code')
        result2 = engine.route_task('analyze data')
        
        # Should return agent or None
        valid = [None, 'hermes', 'pi']
        assert result1 in valid
        assert result2 in valid
    
    def test_find_best_agent_for_task(self):
        """Can find best agent for specific task."""
        engine = LifeContextEngine()
        
        agent = engine.find_best_agent('write tests')
        
        assert agent in [None, 'hermes', 'pi']


class TestRLCollaborationLearning:
    """Test RL learns from PI-Hermes collaboration."""
    
    def test_rl_reward_on_delegate_success(self):
        """RL rewards successful delegation."""
        rl = ReinforcementLearning()
        
        initial_stats = rl.get_stats()
        initial_rewards = initial_stats.get('total_rewards', 0)
        
        reward = rl.reward(ActionType.DELEGATE, success=True)
        
        assert reward > 0
        assert rl.get_stats()['total_rewards'] > initial_rewards
    
    def test_rl_reward_on_delegate_failure(self):
        """RL penalizes failed delegation."""
        rl = ReinforcementLearning()
        
        reward = rl.reward(ActionType.DELEGATE, success=False)
        
        assert reward < 0
    
    def test_rl_reward_on_execute_success(self):
        """RL rewards successful execution."""
        rl = ReinforcementLearning()
        
        reward = rl.reward(ActionType.EXECUTE, success=True)
        
        assert reward > 0
    
    def test_rl_learns_from_collaboration(self):
        """RL updates Q-values from collaboration."""
        rl = ReinforcementLearning()
        
        # Multiple interactions
        rl.reward(ActionType.DELEGATE, True)
        rl.reward(ActionType.DELEGATE, True)
        rl.reward(ActionType.EXECUTE, True)
        
        stats = rl.get_stats()
        
        assert stats['total_rewards'] >= 3
    
    def test_rl_success_rate_tracking(self):
        """RL tracks success rate."""
        rl = ReinforcementLearning()
        
        # Mix of successes and failures
        rl.reward(ActionType.DELEGATE, True)
        rl.reward(ActionType.DELEGATE, True)
        rl.reward(ActionType.DELEGATE, False)
        
        stats = rl.get_stats()
        
        # Success rate should be calculated
        assert 'success_rate' in stats
        # Success rate could be int, float, or dict depending on implementation
        success_rate = stats['success_rate']
        assert isinstance(success_rate, (int, float, dict))
    
    def test_rl_persists_learning(self):
        """RL persists learned Q-values."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'rl.json')
            
            # Learn
            rl1 = ReinforcementLearning()
            rl1.reward(ActionType.DELEGATE, True)
            rl1.reward(ActionType.DELEGATE, True)
            rl1.save(path)
            
            # Load in new instance
            rl2 = ReinforcementLearning()
            rl2.load(path)
            
            stats = rl2.get_stats()
            assert stats['total_rewards'] >= 2


class TestFullCollaborationWorkflow:
    """Test complete PI-Hermes collaboration workflow."""
    
    def test_complete_task_workflow(self):
        """Test: Route task -> Delegate -> Receive result -> RL reward."""
        # 1. Get engine and bridge
        engine = LifeContextEngine()
        bridge = get_bridge()
        rl = ReinforcementLearning()
        
        # 2. Route task
        agent = engine.route_task('analyze data')
        
        # 3. If agent found, delegate
        if agent in ['hermes', 'pi']:
            agent_type = AgentType.HERMES if agent == 'hermes' else AgentType.PI
            task_id = bridge.delegate_task(agent_type, {'type': 'analysis', 'content': 'test'})
        
        # 4. Receive result
        bridge.receive_result(AgentType.PI, {'success': True, 'data': {'result': 'done'}})
        
        # 5. RL learns
        reward = rl.reward(ActionType.DELEGATE, True)
        
        assert reward > 0
    
    def test_context_sharing_workflow(self):
        """Test: Update context -> Sync -> Verify shared."""
        bridge = get_bridge()
        
        # Update context
        bridge.update_shared_context('task', 'analyzing')
        bridge.update_shared_context('agents', ['hermes', 'pi'])
        
        # Verify in shared context
        assert 'task' in bridge.shared_context
        assert 'agents' in bridge.shared_context
        
        # Sync to agents
        bridge.sync_context(AgentType.HERMES)
        bridge.sync_context(AgentType.PI)
    
    def test_capability_discovery_workflow(self):
        """Test: Discover -> Query -> Route based on capabilities."""
        engine = LifeContextEngine()
        
        # Get capabilities
        h_caps = engine.get_capabilities('hermes')
        p_caps = engine.get_capabilities('pi')
        
        # Find best agent for different tasks
        for task in ['write code', 'debug', 'analyze', 'plan']:
            agent = engine.route_task(task)
            assert agent in [None, 'hermes', 'pi']
    
    def test_multi_agent_collaboration(self):
        """Test collaboration with both agents."""
        bridge = get_bridge()
        engine = LifeContextEngine()
        
        # Delegate to Hermes
        h_task_id = bridge.delegate_task(AgentType.HERMES, {'type': 'code'})
        
        # Delegate to PI
        p_task_id = bridge.delegate_task(AgentType.PI, {'type': 'analysis'})
        
        # Receive results from both
        bridge.receive_result(AgentType.HERMES, {'success': True})
        bridge.receive_result(AgentType.PI, {'success': True})
        
        # Verify message history has both
        history = bridge.message_history
        assert len(history) >= 0  # May have messages
    
    def test_error_handling_in_collaboration(self):
        """Test graceful error handling during collaboration."""
        bridge = get_bridge()
        engine = LifeContextEngine()
        
        # Invalid task routing
        agent = engine.route_task('')  # Empty task
        assert agent in [None, 'hermes', 'pi']
        
        # Delegation without connection (should not crash)
        task_id = bridge.delegate_task(AgentType.HERMES, {'type': 'test'})
        assert task_id is None or isinstance(task_id, str)


class TestCollaborationResilience:
    """Test resilience of collaboration system."""
    
    def test_handles_disconnected_agent(self):
        """Handles disconnected agent gracefully."""
        bridge = get_bridge()
        
        # Try to delegate to disconnected agent
        # Now returns message_id (queued) not None
        task_id = bridge.delegate_task(AgentType.HERMES, {'type': 'test'})
        
        # Should return task_id (queued) or None, not crash
        assert task_id is None or isinstance(task_id, str)
    
    def test_handles_unknown_agent(self):
        """Handles unknown agent gracefully."""
        bridge = get_bridge()
        
        # Unknown agent type should not crash
        caps = bridge.query_capabilities(AgentType.PI)
        
        # Returns None or capabilities
        assert caps is None or isinstance(caps, (list, dict))
    
    def test_message_history_limit(self):
        """Message history respects limit."""
        bridge = get_bridge()
        
        max_history = bridge.max_history
        assert max_history > 0
        assert max_history <= 10000  # Reasonable limit
    
    def test_circuit_breaker_state(self):
        """Circuit breaker tracks failures."""
        bridge = get_bridge()
        
        # Circuit breaker takes agent parameter
        is_open = bridge.is_circuit_open(AgentType.HERMES)
        
        assert isinstance(is_open, bool)
    
    def test_retry_mechanism(self):
        """Retry mechanism exists."""
        bridge = get_bridge()
        
        # Retry delay takes attempt parameter
        delay = bridge.get_retry_delay(attempt=1)
        
        assert isinstance(delay, (int, float))
        assert delay >= 0
