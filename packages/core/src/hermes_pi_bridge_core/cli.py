"""
CLI Interface - Control the Autonomous Agent

TDD Tests verify:
- Agent can be started/stopped via CLI
- Configuration can be loaded from file
- Status is displayed correctly
- Commands are executed properly
- Emergency stop works
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import os
import signal
from pathlib import Path
from typing import Any

from .autonomous import AutonomousNHIL, AutonomousConfig
from .executor import SafeExecutor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentCLI:
    """
    CLI interface for controlling the autonomous agent.
    
    Commands:
    - start: Start the agent
    - stop: Stop the agent
    - status: Show agent status
    - execute: Run a command
    - scan: Scan for work
    - config: Show/edit configuration
    - logs: Show recent logs
    - emergency-stop: Immediate halt
    """
    
    def __init__(self, config_path: str | None = None):
        self.config = self._load_config(config_path)
        self.agent: AutonomousNHIL | None = None
        self.executor = SafeExecutor()
        self._setup_signal_handlers()
    
    def _load_config(self, config_path: str | None) -> dict[str, Any]:
        """Load configuration from file or defaults."""
        default_config = {
            "storage_path": "~/.autonomous-nhil/state.json",
            "scan_interval_seconds": 300,
            "scan_paths": [str(Path.home() / "projects")],
            "max_execution_duration_seconds": 60,
            "enable_learning": True,
            "enable_evolution": True,
            "strict_mode": True,
            "log_level": "INFO",
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path) as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _setup_signal_handlers(self) -> None:
        """Setup handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    
    def _handle_signal(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self._emergency_stop()
        sys.exit(0)
    
    def _emergency_stop(self) -> None:
        """Emergency stop - immediate halt."""
        logger.critical("EMERGENCY STOP ACTIVATED")
        if self.agent:
            self.agent.stop()
        logger.info("Shutdown complete")
    
    def cmd_start(self) -> int:
        """Start the agent."""
        if self.agent and self.agent.running:
            print("Agent already running")
            return 1
        
        print("Starting autonomous agent...")
        
        # Convert dict to AutonomousConfig
        config = AutonomousConfig(**{
            k: v for k, v in self.config.items()
            if k in AutonomousConfig.__dataclass_fields__
        })
        
        self.agent = AutonomousNHIL(config=config)
        success = self.agent.start()
        
        if success:
            print("✓ Agent started successfully")
            print(f"  PID: {os.getpid()}")
            print(f"  Storage: {self.config['storage_path']}")
        else:
            print("✗ Failed to start agent")
            return 1
        
        return 0
    
    def cmd_stop(self) -> int:
        """Stop the agent."""
        if not self.agent or not self.agent.running:
            print("Agent not running")
            return 1
        
        print("Stopping agent...")
        self.agent.stop()
        print("✓ Agent stopped")
        return 0
    
    def cmd_status(self) -> int:
        """Show agent status."""
        if not self.agent:
            print("Agent not initialized. Run 'start' first.")
            return 1
        
        status = self.agent.get_status()
        
        print("┌─────────────────────────────────────────┐")
        print("│         AUTONOMOUS AGENT STATUS         │")
        print("├─────────────────────────────────────────┤")
        print(f"│ Running:     {'Yes' if status['running'] else 'No':<29} │")
        print(f"│ Uptime:      {status['uptime_seconds']:<29.1f}s │")
        print("├─────────────────────────────────────────┤")
        print(f"│ Discovered:  {status['tasks_discovered']:<29} │")
        print(f"│ Completed:   {status['tasks_completed']:<29} │")
        print(f"│ Failed:      {status['tasks_failed']:<29} │")
        print(f"│ Success Rate: {status['success_rate']*100:<27.1f}% │")
        print("├─────────────────────────────────────────┤")
        print("│ Scanner Stats                           │")
        scanner = status.get('scanner', {})
        print(f"│   Total Scans: {scanner.get('total_scans', 0):<25} │")
        print(f"│   Tasks Found: {scanner.get('tasks_found', 0):<25} │")
        print("├─────────────────────────────────────────┤")
        print("│ Executor Stats                          │")
        executor = status.get('executor', {})
        print(f"│   Executions: {executor.get('total_executions', 0):<25} │")
        print(f"│   Success Rate: {executor.get('success_rate', 0)*100:<23.1f}% │")
        print("└─────────────────────────────────────────┘")
        
        return 0
    
    def cmd_execute(self, command: str) -> int:
        """Execute a command."""
        if not command:
            print("Error: No command provided")
            return 1
        
        print(f"Executing: {command}")
        result = self.executor.execute(command)
        
        if result.success:
            print("✓ Command succeeded")
            if result.stdout:
                print("\nOutput:")
                print(result.stdout)
        else:
            print(f"✗ Command failed: {result.error}")
            if result.stderr:
                print("\nError output:")
                print(result.stderr)
        
        return 0 if result.success else 1
    
    def cmd_scan(self, force: bool = False) -> int:
        """Scan for work."""
        if not self.agent:
            print("Agent not initialized. Run 'start' first.")
            return 1
        
        print("Scanning for work...")
        tasks = self.agent.scanner.scan(force=force)
        
        if not tasks:
            print("No tasks found")
            return 0
        
        print(f"\nFound {len(tasks)} tasks:")
        print("┌─────────────────────────────────────────────────────────────┐")
        for i, task in enumerate(tasks[:10], 1):
            print(f"│ {i}. [{task.priority.upper():<6}] {task.title[:45]:<45} │")
        print("└─────────────────────────────────────────────────────────────┘")
        
        return 0
    
    def cmd_config(self, show: bool = True, set_key: str | None = None, set_value: str | None = None) -> int:
        """Show or modify configuration."""
        if show and not set_key:
            print("Current Configuration:")
            print(json.dumps(self.config, indent=2))
            return 0
        
        if set_key:
            if set_key not in self.config:
                print(f"Unknown config key: {set_key}")
                return 1
            
            # Try to parse value
            try:
                value = json.loads(set_value)
            except json.JSONDecodeError:
                value = set_value
            
            self.config[set_key] = value
            print(f"✓ Set {set_key} = {value}")
            return 0
        
        return 0
    
    def cmd_logs(self, lines: int = 20) -> int:
        """Show recent logs."""
        # This would read from a log file in production
        print(f"Last {lines} log entries (simulated):")
        print("  [INFO] Agent initialized")
        print("  [INFO] Components loaded")
        print("  [INFO] Ready for commands")
        return 0
    
    def cmd_emergency_stop(self) -> int:
        """Emergency stop - immediate halt."""
        print("⚠️  EMERGENCY STOP ACTIVATED")
        self._emergency_stop()
        return 0
    
    def cmd_health(self) -> int:
        """Health check."""
        checks = []
        
        # Check agent
        if self.agent and self.agent.running:
            checks.append(("Agent Running", True))
        else:
            checks.append(("Agent Running", False))
        
        # Check executor
        try:
            result = self.executor.execute("echo health_check")
            checks.append(("Executor Functional", result.success))
        except Exception:
            checks.append(("Executor Functional", False))
        
        # Check persistence
        if self.agent:
            persistence_ok = self.agent.persistence.exists()
            checks.append(("Persistence Available", persistence_ok))
        else:
            checks.append(("Persistence Available", False))
        
        # Print results
        print("Health Check Results:")
        all_healthy = True
        for name, status in checks:
            icon = "✓" if status else "✗"
            print(f"  {icon} {name}: {'HEALTHY' if status else 'UNHEALTHY'}")
            if not status:
                all_healthy = False
        
        return 0 if all_healthy else 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AutonomousNHIL - Self-Evolving Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s start              Start the agent
  %(prog)s stop               Stop the agent
  %(prog)s status             Show agent status
  %(prog)s execute "echo hi"  Run a command
  %(prog)s scan               Scan for work
  %(prog)s health             Health check
  %(prog)s emergency-stop     Immediate halt
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        help='Path to configuration file (JSON)',
        default=None
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Start command
    subparsers.add_parser('start', help='Start the agent')
    
    # Stop command
    subparsers.add_parser('stop', help='Stop the agent')
    
    # Status command
    subparsers.add_parser('status', help='Show agent status')
    
    # Execute command
    exec_parser = subparsers.add_parser('execute', help='Execute a command')
    exec_parser.add_argument('command', help='Command to execute')
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan for work')
    scan_parser.add_argument('-f', '--force', action='store_true', help='Force scan')
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Show/modify configuration')
    config_parser.add_argument('--set', nargs=2, metavar=('KEY', 'VALUE'), help='Set config value')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Show recent logs')
    logs_parser.add_argument('-n', '--lines', type=int, default=20, help='Number of lines')
    
    # Emergency stop
    subparsers.add_parser('emergency-stop', help='Immediate halt')
    
    # Health check
    subparsers.add_parser('health', help='Health check')
    
    args = parser.parse_args()
    
    # No command = show help
    if not args.command:
        parser.print_help()
        return 0
    
    # Create CLI
    cli = AgentCLI(config_path=args.config)
    
    # Dispatch command
    commands = {
        'start': cli.cmd_start,
        'stop': cli.cmd_stop,
        'status': cli.cmd_status,
        'execute': lambda: cli.cmd_execute(args.command),
        'scan': lambda: cli.cmd_scan(force=args.force) if hasattr(args, 'force') else cli.cmd_scan(),
        'config': lambda: cli.cmd_config(
            show=not args.set,
            set_key=args.set[0] if args.set else None,
            set_value=args.set[1] if args.set else None
        ) if hasattr(args, 'set') else cli.cmd_config(),
        'logs': lambda: cli.cmd_logs(args.lines) if hasattr(args, 'lines') else cli.cmd_logs(),
        'emergency-stop': cli.cmd_emergency_stop,
        'health': cli.cmd_health,
    }
    
    cmd_func = commands.get(args.command)
    if cmd_func:
        return cmd_func()
    
    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
