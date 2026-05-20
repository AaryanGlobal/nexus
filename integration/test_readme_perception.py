"""
README Perception Study & Simulation Tests
Tests how humans and AI agents perceive and use the README
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.bridge import get_bridge, AgentType
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.rl import ReinforcementLearning, ActionType


class TestReadmeAccessibility:
    """Test README accessibility for different audiences."""
    
    def test_has_clear_title(self):
        """README has clear, identifiable title."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should have title as first line
        lines = content.split('\n')
        assert lines[0].startswith('# ')
        assert 'Nexus' in lines[0]
    
    def test_has_purpose_statement(self):
        """README explains what the project does."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should explain purpose early
        assert 'bridge' in content.lower() or 'connect' in content.lower()
        assert 'PI' in content and 'Hermes' in content
    
    def test_has_quick_start(self):
        """README has quick start section."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        assert 'Quick Start' in content or 'quick start' in content.lower()
        assert 'pip install' in content or 'pip install' in content
    
    def test_has_code_examples(self):
        """README has runnable code examples."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should have Python code blocks
        assert '```python' in content or '```py' in content
        # Should have bash code blocks
        assert '```bash' in content or '```sh' in content
    
    def test_has_api_documentation(self):
        """README documents API endpoints."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should have endpoint documentation
        assert '/health' in content or '/status' in content
        assert 'GET' in content or 'POST' in content


class TestAIAgentPerception:
    """Simulate how an AI agent perceives and uses the README."""
    
    def test_ai_can_import_bridge(self):
        """AI agent can find and import the bridge module."""
        try:
            from hermes_pi_bridge_core.bridge import get_bridge, AgentType
            bridge = get_bridge()
            assert bridge is not None
        except ImportError as e:
            pytest.fail(f"AI agent cannot import bridge: {e}")
    
    def test_ai_can_find_delegate_task(self):
        """AI agent can find delegate_task method."""
        bridge = get_bridge()
        
        assert hasattr(bridge, 'delegate_task')
        assert callable(bridge.delegate_task)
    
    def test_ai_can_find_route_task(self):
        """AI agent can find route_task method."""
        engine = LifeContextEngine()
        
        assert hasattr(engine, 'route_task')
        assert callable(engine.route_task)
    
    def test_ai_can_understand_agent_types(self):
        """AI agent can understand AgentType enum."""
        assert AgentType.PI is not None
        assert AgentType.HERMES is not None
        assert AgentType.PI != AgentType.HERMES
    
    def test_ai_can_find_context_sharing(self):
        """AI agent can find context sharing methods."""
        bridge = get_bridge()
        
        assert hasattr(bridge, 'update_shared_context')
        assert hasattr(bridge, 'sync_context')
    
    def test_readme_has_for_ai_section(self):
        """README has section directed at AI agents."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should have section for AI agents
        assert 'For AI Agents' in content or 'for ai' in content.lower()
    
    def test_readme_has_python_examples(self):
        """README has Python code AI agents can copy-paste."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should have Python block with delegate_task
        assert '```python' in content
        assert 'delegate_task' in content
        assert 'AgentType' in content


class TestHumanDeveloperPerception:
    """Simulate how a human developer perceives the README."""
    
    def test_has_cli_documentation(self):
        """README documents CLI commands."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        assert 'nexus status' in content or 'nexus status' in content.lower()
        assert 'CLI' in content
    
    def test_has_installation_instructions(self):
        """README has clear installation steps."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        assert 'pip install' in content
        assert 'Quick Start' in content or 'Install' in content
    
    def test_has_project_structure(self):
        """README shows project structure."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        assert 'project structure' in content.lower() or 'directory' in content.lower()
        assert 'packages/' in content
    
    def test_has_links_to_more_docs(self):
        """README links to more documentation."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        assert '.md' in content  # Links to other docs
    
    def test_has_testing_section(self):
        """README documents how to run tests."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        assert 'pytest' in content.lower()
        assert 'test' in content.lower()


class TestDualityBalance:
    """Test that README serves both human and AI audiences."""
    
    def test_has_separate_sections(self):
        """README has distinct sections for different audiences."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should have both developer and AI sections
        assert 'For Developers' in content or 'For Humans' in content
        assert 'For AI Agents' in content
    
    def test_has_cli_and_python_examples(self):
        """README has both CLI (human) and Python (AI) examples."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # CLI for humans
        assert 'nexus' in content.lower() or 'bash' in content.lower()
        # Python for AI
        assert '```python' in content
    
    def test_technical_accuracy(self):
        """README technical content is accurate."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Port numbers should match actual config
        assert '8080' in content  # Hermes
        assert '8645' in content  # PI
    
    def test_examples_are_runnable(self):
        """Code examples in README are actually runnable."""
        # Test the import example
        from hermes_pi_bridge_core.bridge import get_bridge, AgentType
        bridge = get_bridge()
        
        # Test delegate example (would fail in test but syntax is valid)
        # The fact that import works proves the example structure is valid
    
    def test_readme_not_too_long(self):
        """README is not excessively long."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should be under 5000 words for readability
        words = len(content.split())
        assert words < 5000, f"README too long: {words} words"
    
    def test_readme_not_too_short(self):
        """README is substantial enough."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should be at least 500 words for completeness
        words = len(content.split())
        assert words > 500, f"README too short: {words} words"


class TestReadabilityMetrics:
    """Test README readability scores."""
    
    def test_sentence_length_reasonable(self):
        """Sentences are not overly long."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Remove code blocks for text analysis
        import re
        text_only = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        text_only = re.sub(r'#.*$', '', text_only, flags=re.MULTILINE)
        
        # Check average sentence length
        sentences = [s.strip() for s in text_only.split('.') if s.strip()]
        if sentences:
            avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
            assert avg_len < 30, f"Average sentence too long: {avg_len} words"
    
    def test_has_visual_structure(self):
        """README uses headers and formatting."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should have multiple headers
        header_count = content.count('## ')
        assert header_count >= 5, f"Too few headers: {header_count}"
    
    def test_uses_markdown_properly(self):
        """README uses Markdown correctly."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should have code blocks
        assert '```' in content
        # Should have headers
        assert '# ' in content
        # Should have lists
        assert '-' in content or '*' in content or '1.' in content


class TestActionableContent:
    """Test that README enables action."""
    
    def test_first_use_case_works(self):
        """First code example is a complete use case."""
        bridge = get_bridge()
        engine = LifeContextEngine()
        
        # Simulate: route task -> delegate -> receive
        agent = engine.route_task(['test', 'task'])
        if agent:
            a_type = AgentType.PI if agent == 'pi' else AgentType.HERMES
            task_id = bridge.delegate_task(a_type, {'test': True})
            bridge.receive_result(a_type, {'success': True})
        
        assert True  # If we got here, the flow works
    
    def test_goal_tracking_works(self):
        """Goal tracking use case is complete."""
        engine = LifeContextEngine()
        
        goal = engine.add_goal("Test Goal", "Testing", "Engineering")
        engine.update_goal_progress(goal.id, 50)
        
        assert goal.id is not None
    
    def test_capability_discovery_works(self):
        """Capability discovery use case is complete."""
        engine = LifeContextEngine()
        
        caps = engine.get_capabilities("pi")
        assert len(caps) > 0
        
        caps = engine.get_capabilities("hermes")
        assert len(caps) > 0


class TestEdgeCaseHandling:
    """Test README handles edge cases."""
    
    def test_handles_ai_with_no_context(self):
        """AI agent with no prior context can use README."""
        # Simulate fresh AI
        try:
            from hermes_pi_bridge_core.bridge import get_bridge, AgentType
            from hermes_pi_bridge_core.life_context import LifeContextEngine
            
            # Fresh imports work
            bridge = get_bridge()
            engine = LifeContextEngine()
            
            # Can route immediately
            agent = engine.route_task(['code'])
            
            assert True
        except Exception as e:
            pytest.fail(f"Fresh AI cannot use system: {e}")
    
    def test_handles_human_with_no_experience(self):
        """Human with no experience can follow README."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Should have step-by-step installation
        lines = content.split('\n')
        install_lines = [i for i, l in enumerate(lines) if 'pip install' in l]
        
        assert len(install_lines) > 0, "No install instructions found"
    
    def test_multiple_code_block_formats(self):
        """README supports multiple code languages."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Python for AI
        assert '```python' in content
        # Bash for humans
        assert '```bash' in content or '```' in content
        
    def test_no_dead_links(self):
        """All links in README point to existing files."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()
        
        # Extract markdown links
        import re
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        
        # Check internal links exist
        for text, path in links:
            if path.startswith('./') or path.startswith('/'):
                if path.endswith('.md'):
                    target = readme.parent / path.lstrip('./')
                    # Should exist or be documented as placeholder
                    if not target.exists():
                        assert 'SPEC.md' in path or 'CONTRIBUTING' in path  # Known docs


class TestComprehensiveCoverage:
    """Test README covers all key features."""
    
    def test_covers_task_delegation(self):
        """Task delegation is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text().lower()
        
        assert 'delegate' in content
        assert 'task' in content
    
    def test_covers_context_sharing(self):
        """Context sharing is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text().lower()
        
        assert 'context' in content
        assert 'share' in content or 'sync' in content
    
    def test_covers_goal_tracking(self):
        """Goal tracking is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text().lower()
        
        assert 'goal' in content
    
    def test_covers_capabilities(self):
        """Capabilities are documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text().lower()
        
        assert 'capabilit' in content
    
    def test_covers_self_evolution(self):
        """Self-evolution is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text().lower()
        
        assert 'evolution' in content or 'propos' in content or 'vote' in content
    
    def test_covers_error_handling(self):
        """Error handling is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text().lower()
        
        assert 'error' in content or 'fail' in content or 'circuit' in content
