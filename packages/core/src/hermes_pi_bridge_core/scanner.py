"""
Work Scanner - Proactively Discovers Tasks

TDD Tests verify:
- Project directory scanning
- Task file detection
- Priority extraction
- Git integration
- Scheduled task discovery
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path
import time
import subprocess


@dataclass
class DiscoveredTask:
    """A task discovered by the scanner."""
    title: str
    description: str
    priority: str  # "high", "medium", "low"
    source: str  # Where it was found
    location: str  # File path or URL
    age_days: int = 0  # How old the task is
    metadata: dict = field(default_factory=dict)


@dataclass
class ScanConfig:
    """Configuration for work scanner."""
    scan_paths: list[str] = None
    scan_interval_seconds: int = 300  # 5 minutes
    include_git: bool = True
    include_todos: bool = True
    include_tickets: bool = True
    priority_keywords: dict[str, str] = None
    
    def __post_init__(self):
        self.scan_paths = self.scan_paths or [
            str(Path.home() / "projects"),
            str(Path.home() / "work"),
        ]
        self.priority_keywords = self.priority_keywords or {
            "urgent": "high",
            "critical": "high",
            "asap": "high",
            "important": "medium",
            "soon": "medium",
            "nice to have": "low",
            "low priority": "low",
            "eventually": "low",
        }


class WorkScanner:
    """
    Proactively discovers work to be done.
    
    Sources:
    - Git: branches, uncommitted changes, issues
    - TODO/FIXME: in code files
    - Ticket files: .tasks, .todo, kanban exports
    - Project boards: GitHub/GitLab issues
    """
    
    # Patterns for task discovery
    TODO_PATTERNS = [
        r'#\s*(TODO|FIXME|HACK|XXX|BUG|NOTE):\s*(.+)',
        r'//\s*(TODO|FIXME|HACK|XXX|BUG|NOTE):\s*(.+)',
        r'/\*\s*(TODO|FIXME|HACK|XXX|BUG|NOTE):\s*(.+)\*/',
        r'<!--\s*(TODO|FIXME|HACK):\s*(.+)',
    ]
    
    # File patterns to scan
    SCAN_EXTENSIONS = [
        '.py', '.js', '.ts', '.go', '.rs', '.java',
        '.c', '.cpp', '.h', '.hpp', '.cs',
        '.md', '.txt', '.todo', '.tasks',
    ]
    
    def __init__(self, config: ScanConfig | None = None):
        self.config = config or ScanConfig()
        self.last_scan_time = 0
        self.last_results: list[DiscoveredTask] = []
        self.scan_count = 0
    
    def scan(self, force: bool = False) -> list[DiscoveredTask]:
        """
        Perform a full scan for work.
        
        Args:
            force: Skip time check and scan anyway
            
        Returns:
            List of discovered tasks
        """
        # Rate limit scans
        if not force and time.time() - self.last_scan_time < self.config.scan_interval_seconds:
            return self.last_results
        
        results = []
        
        # Scan configured paths
        for path in self.config.scan_paths:
            if os.path.exists(path):
                results.extend(self._scan_directory(path))
        
        # Git integration
        if self.config.include_git:
            results.extend(self._scan_git())
        
        # Deduplicate
        seen = set()
        unique_results = []
        for task in results:
            key = (task.title, task.location)
            if key not in seen:
                seen.add(key)
                unique_results.append(task)
        
        # Sort by priority and age
        unique_results.sort(key=lambda t: (
            {"high": 0, "medium": 1, "low": 2}.get(t.priority, 3),
            -t.age_days  # Older tasks first
        ))
        
        self.last_results = unique_results
        self.last_scan_time = time.time()
        self.scan_count += 1
        
        return unique_results
    
    def _scan_directory(self, path: str) -> list[DiscoveredTask]:
        """Scan a directory for task markers."""
        tasks = []
        
        for root, dirs, files in os.walk(path):
            # Skip hidden and common non-source directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in [
                'node_modules', '__pycache__', 'venv', '.venv', 'build', 'dist'
            ]]
            
            for file in files:
                if any(file.endswith(ext) for ext in self.SCAN_EXTENSIONS):
                    file_path = os.path.join(root, file)
                    tasks.extend(self._scan_file(file_path))
        
        return tasks
    
    def _scan_file(self, file_path: str) -> list[DiscoveredTask]:
        """Scan a single file for task markers."""
        tasks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            for i, line in enumerate(lines):
                for pattern in self.TODO_PATTERNS:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        task_type = match.group(1).upper()
                        description = match.group(2).strip()
                        
                        # Calculate age (simplified - would need git blame for accuracy)
                        age_days = self._estimate_file_age(file_path)
                        
                        # Determine priority
                        priority = self._determine_priority(description)
                        
                        tasks.append(DiscoveredTask(
                            title=f"{task_type}: {description[:50]}",
                            description=description,
                            priority=priority,
                            source="TODO/FIXME in code",
                            location=file_path,
                            age_days=age_days,
                            metadata={"line_number": i + 1},
                        ))
        
        except Exception:
            pass
        
        return tasks
    
    def _scan_git(self) -> list[DiscoveredTask]:
        """Scan git for pending work."""
        tasks = []
        
        # Get current directory as project root
        try:
            cwd = os.getcwd()
            
            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                uncommitted = len(result.stdout.strip().split('\n'))
                tasks.append(DiscoveredTask(
                    title=f"Uncommitted changes ({uncommitted} files)",
                    description=f"There are {uncommitted} uncommitted files in the current branch",
                    priority="medium",
                    source="git status",
                    location=cwd,
                ))
            
            # Check for branches with unmerged work
            result = subprocess.run(
                ['git', 'branch', '-v'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if '*' in line and ('WIP' in line or 'draft' in line.lower()):
                        branch = line.strip()
                        tasks.append(DiscoveredTask(
                            title=f"WIP branch: {branch[:50]}",
                            description="This branch appears to be work in progress",
                            priority="low",
                            source="git branch",
                            location=cwd,
                        ))
        
        except Exception:
            pass
        
        return tasks
    
    def _estimate_file_age(self, file_path: str) -> int:
        """Estimate file age in days."""
        try:
            stat = os.stat(file_path)
            age_seconds = time.time() - stat.st_mtime
            return int(age_seconds / 86400)
        except Exception:
            return 0
    
    def _determine_priority(self, description: str) -> str:
        """Determine priority from keywords in description."""
        desc_lower = description.lower()
        
        for keyword, priority in self.config.priority_keywords.items():
            if keyword in desc_lower:
                return priority
        
        return "medium"
    
    def get_scan_stats(self) -> dict[str, Any]:
        """Get scanner statistics."""
        return {
            "total_scans": self.scan_count,
            "last_scan_ago_seconds": int(time.time() - self.last_scan_time),
            "tasks_found": len(self.last_results),
            "high_priority": sum(1 for t in self.last_results if t.priority == "high"),
            "medium_priority": sum(1 for t in self.last_results if t.priority == "medium"),
            "low_priority": sum(1 for t in self.last_results if t.priority == "low"),
        }
    
    def get_high_priority_tasks(self) -> list[DiscoveredTask]:
        """Get only high priority tasks from last scan."""
        return [t for t in self.last_results if t.priority == "high"]