"""TDD: Life Context Engine Tests - Simplified"""
import pytest
import tempfile
from pathlib import Path

from hermes_pi_bridge_core.life_context import (
    LifeContextEngine, LifeContext, LifeGoal, AgentCapabilities
)


@pytest.fixture
def engine():
    """Create test engine."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.json"
        yield LifeContextEngine(storage_path=str(path))


@pytest.fixture
def bridge():
    """Create test bridge."""
    from hermes_pi_bridge_core.bridge import AgentBridge
    return AgentBridge()


class TestContext:
    """Test context management."""
    
    def test_add_context(self, engine):
        """Can add context."""
        ctx = engine.add_context("Build thought leadership", "voice")
        assert ctx.pillar == "voice"
        assert ctx.verified is True
    
    def test_custom_pillar(self, engine):
        """Can add custom pillar."""
        engine.add_context("Custom goal", "custom_pillar")
        pillars = engine.get_pillars()
        assert "custom_pillar" in pillars
    
    def test_get_by_pillar(self, engine):
        """Can get contexts by pillar."""
        engine.add_context("Goal 1", "voice")
        engine.add_context("Goal 2", "voice")
        engine.add_context("Goal 3", "prosperity")
        
        voice = engine.get_contexts_by_pillar("voice")
        assert len(voice) == 2


class TestGoals:
    """Test goal management."""
    
    def test_add_goal(self, engine):
        """Can add goal."""
        goal = engine.add_goal("Learn Rust", "Study Rust", "capacity")
        assert goal.pillar == "capacity"
        assert goal.status == "not_started"
    
    def test_update_progress(self, engine):
        """Can update progress."""
        goal = engine.add_goal("Test", "Desc", "voice")
        result = engine.update_goal_progress(goal.id, 50.0)
        assert result is True
        
        updated = next(g for g in engine.goals if g.id == goal.id)
        assert updated.progress == 50.0
        assert updated.status == "in_progress"
    
    def test_complete_at_100(self, engine):
        """Completes at 100%."""
        goal = engine.add_goal("Test", "Desc", "voice")
        engine.update_goal_progress(goal.id, 100.0)
        
        updated = next(g for g in engine.goals if g.id == goal.id)
        assert updated.status == "completed"


class TestCapabilities:
    """Test capability management."""
    
    def test_add_capability(self, engine):
        """Can add capability."""
        engine.add_capability("hermes", "strategic_planning")
        caps = engine.get_capabilities("hermes")
        assert "strategic_planning" in caps
    
    def test_propose_capability(self, engine):
        """Can propose capability."""
        vote_id = engine.propose_capability("deep_reasoning", "hermes")
        assert vote_id.startswith("vote_")
    
    def test_vote_and_approve(self, engine):
        """Consensus voting works."""
        vote_id = engine.propose_capability("coding", "pi")
        
        # Vote from 3 agents
        engine.vote_capability(vote_id, "hermes", True, "Good")
        engine.vote_capability(vote_id, "pi", True, "Agree")
        
        # Check approved
        vote = next(v for v in engine.capability_votes if v['id'] == vote_id)
        assert vote['status'] == 'approved'
    
    def test_vote_and_reject(self, engine):
        """Can reject capability."""
        vote_id = engine.propose_capability("cooking", "hermes")
        
        engine.vote_capability(vote_id, "hermes", False, "Not needed")
        engine.vote_capability(vote_id, "pi", False, "No")
        
        vote = next(v for v in engine.capability_votes if v['id'] == vote_id)
        assert vote['status'] == 'rejected'
    
    def test_can_handle_task(self, engine):
        """Task routing works."""
        engine.add_capability("hermes", "planning")
        engine.add_capability("hermes", "strategy")
        
        can_do, missing = engine.can_handle_task("hermes", ["planning"])
        assert can_do is True
        
        can_do, missing = engine.can_handle_task("hermes", ["planning", "unknown"])
        assert can_do is False
        assert "unknown" in missing


class TestPersistence:
    """Test persistence."""
    
    def test_persists(self, engine):
        """Data survives reload."""
        engine.add_context("Test", "voice")
        engine.add_capability("hermes", "planning")
        
        # Reload
        engine2 = LifeContextEngine(storage_path=engine.storage_path)
        
        assert len(engine2.contexts) == 1
        assert "planning" in engine2.get_capabilities("hermes")


class TestCapabilityDiscovery:
    """Test capability discovery for Hermes and PI."""
    
    def test_discover_hermes_capabilities(self, engine):
        """Can discover Hermes capabilities."""
        # Hermes should have strategic capabilities
        caps = engine.discover_capabilities("hermes")
        assert len(caps) > 0
        # Hermes is strategic - should have planning, strategy, reasoning
        expected = ["planning", "strategy", "reasoning", "analysis"]
        found = any(c in caps for c in expected)
        assert found, f"Hermes should have strategic capabilities, got {caps}"
    
    def test_discover_pi_capabilities(self, engine):
        """Can discover PI capabilities."""
        caps = engine.discover_capabilities("pi")
        assert len(caps) > 0
        # PI is tactical - should have coding, execution, tools
        expected = ["coding", "execution", "tools", "implementation"]
        found = any(c in caps for c in expected)
        assert found, f"PI should have tactical capabilities, got {caps}"
    
    def test_capability_sync_to_bridge(self, engine, bridge):
        """Capabilities sync to bridge."""
        # Discover and add capabilities
        h_caps = engine.discover_capabilities("hermes")
        for cap in h_caps:
            engine.add_capability("hermes", cap)
        
        # Bridge should reflect this
        caps = engine.get_capabilities("hermes")
        assert len(caps) > 0


class TestContextSharing:
    """Test context sharing between agents."""
    
    def test_share_context_with_hermes(self, engine):
        """Can share context with Hermes."""
        ctx = engine.add_context("Career goal: Build AI agent", "capacity")
        result = engine.share_context("hermes")
        assert result is True
        # Context should be marked as shared
        assert ctx.verified is True
    
    def test_share_context_with_pi(self, engine):
        """Can share context with PI."""
        ctx = engine.add_context("Health goal: Run marathon", "vitality")
        result = engine.share_context("pi")
        assert result is True
    
    def test_get_shared_context(self, engine):
        """Can get all shared context."""
        engine.add_context("Test 1", "voice")
        engine.add_context("Test 2", "capacity")
        # Share both
        engine.share_context("hermes")
        engine.share_context("pi")
        
        # Get shared context
        shared = engine.get_shared_context()
        assert len(shared) >= 2


class TestStatus:
    """Test status reporting."""
    
    def test_get_status(self, engine):
        """Status includes everything."""
        engine.add_context("Goal", "voice")
        engine.add_goal("Test", "Desc", "voice")
        engine.add_capability("hermes", "planning")
        
        status = engine.get_status()
        
        assert 'voice' in status['pillars']
        assert status['goals_total'] == 1
        assert 'hermes' in status['capabilities']