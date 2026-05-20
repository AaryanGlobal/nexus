"""TDD: Work Scanner Tests"""
import pytest
import tempfile
import os
from pathlib import Path
from hermes_pi_bridge_core.scanner import (
    WorkScanner, ScanConfig, DiscoveredTask
)


class TestTaskDiscovery:
    """Test task discovery from files."""
    
    def test_finds_todo_in_python_file(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        # Create test file with TODO
        test_file = tmp_path / "test.py"
        test_file.write_text("# TODO: Implement this feature")
        
        tasks = scanner.scan(force=True)
        
        assert any("Implement this feature" in t.description for t in tasks)
    
    def test_finds_fixes_in_js_file(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        test_file = tmp_path / "test.js"
        test_file.write_text("// FIXME: Memory leak in handler")
        
        tasks = scanner.scan(force=True)
        
        assert any("Memory leak" in t.description for t in tasks)
    
    def test_finds_multiple_todos(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        test_file = tmp_path / "test.py"
        test_file.write_text("""
# TODO: First task
# FIXME: Second task
// HACK: Third task
        """)
        
        tasks = scanner.scan(force=True)
        
        assert len(tasks) >= 3


class TestPriorityDetection:
    """Test priority detection from keywords."""
    
    def test_detects_high_priority_urgent(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        test_file = tmp_path / "test.py"
        test_file.write_text("# TODO: URGENT: Fix production bug")
        
        tasks = scanner.scan(force=True)
        
        high_priority = [t for t in tasks if t.priority == "high"]
        assert len(high_priority) >= 1
    
    def test_detects_low_priority_nice_to_have(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        test_file = tmp_path / "test.py"
        test_file.write_text("# TODO: Nice to have: Add animation")
        
        tasks = scanner.scan(force=True)
        
        low_priority = [t for t in tasks if t.priority == "low"]
        assert len(low_priority) >= 1


class TestDirectoryScanning:
    """Test directory scanning."""
    
    def test_scans_nested_directories(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        # Create nested structure
        nested = tmp_path / "src" / "utils"
        nested.mkdir(parents=True)
        (nested / "helper.py").write_text("# TODO: Helper function")
        
        tasks = scanner.scan(force=True)
        
        assert len(tasks) >= 1
    
    def test_skips_hidden_directories(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        # Hidden directory with TODO should be skipped
        hidden = tmp_path / ".git"
        hidden.mkdir()
        (hidden / "config").write_text("# TODO: Ignore this")
        
        tasks = scanner.scan(force=True)
        
        # Should not find the hidden .git TODO
        git_todos = [t for t in tasks if ".git" in t.location]
        assert len(git_todos) == 0
    
    def test_skips_node_modules(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.json").write_text("# TODO: Ignore this")
        
        tasks = scanner.scan(force=True)
        
        node_todos = [t for t in tasks if "node_modules" in t.location]
        assert len(node_todos) == 0


class TestRateLimiting:
    """Test scan rate limiting."""
    
    def test_respects_scan_interval(self, tmp_path):
        config = ScanConfig(scan_paths=[str(tmp_path)], scan_interval_seconds=300)
        scanner = WorkScanner(config)
        
        # First scan
        (tmp_path / "test.py").write_text("# TODO: Task 1")
        scanner.scan(force=False)
        
        # Second scan should return cached results
        (tmp_path / "test.py").write_text("# TODO: Task 2")
        results = scanner.scan(force=False)
        
        # Should still have old results
        assert scanner.last_scan_time > 0
    
    def test_force_bypasses_interval(self, tmp_path):
        config = ScanConfig(scan_paths=[str(tmp_path)], scan_interval_seconds=300)
        scanner = WorkScanner(config)
        
        (tmp_path / "test1.py").write_text("# TODO: Task 1")
        scanner.scan(force=True)
        
        (tmp_path / "test2.py").write_text("# TODO: Task 2")
        results = scanner.scan(force=True)
        
        # Should find both tasks
        assert len(results) >= 2


class TestGitIntegration:
    """Test git-based scanning."""
    
    def test_git_integration_enabled(self, tmp_path):
        scanner = WorkScanner(ScanConfig(
            scan_paths=[str(tmp_path)],
            include_git=True
        ))
        
        # This tests the config, actual git test would require a git repo
        assert scanner.config.include_git is True


class TestStatistics:
    """Test scanner statistics."""
    
    def test_scan_stats(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        (tmp_path / "test.py").write_text("# TODO: Task\n# URGENT: Task")
        scanner.scan(force=True)
        
        stats = scanner.get_scan_stats()
        
        assert stats["total_scans"] >= 1
        assert stats["tasks_found"] >= 1


class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_directory(self, tmp_path):
        config = ScanConfig(scan_paths=[str(tmp_path)], include_git=False)
        scanner = WorkScanner(config)
        
        tasks = scanner.scan(force=True)
        
        assert tasks == []
    
    def test_nonexistent_path(self):
        scanner = WorkScanner(ScanConfig(scan_paths=["/nonexistent/path"]))
        
        tasks = scanner.scan(force=True)
        
        # Should not crash, just return empty
        assert isinstance(tasks, list)
    
    def test_high_priority_tasks_only(self, tmp_path):
        scanner = WorkScanner(ScanConfig(scan_paths=[str(tmp_path)]))
        
        (tmp_path / "test.py").write_text("""
# TODO: Normal task
# CRITICAL: Important fix
# nice to have: Optional
        """)
        scanner.scan(force=True)
        
        high = scanner.get_high_priority_tasks()
        
        assert all(t.priority == "high" for t in high)