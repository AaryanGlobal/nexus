#!/usr/bin/env python3
"""
Nexus CLI - Control and manage the Nexus agent integration system

Usage:
    python nexus_cli.py status          # Show full status
    python nexus_cli.py connect <agent> # Connect to Hermes or PI
    python nexus_cli.py goals           # List goals
    python nexus_cli.py goal add <title> <pillar>  # Add goal
    python nexus_cli.py goal update <id> <progress>  # Update goal progress
    python nexus_cli.py pillars         # List pillars
    python nexus_cli.py capabilities    # List capabilities
    python nexus_cli.py sync            # Sync context with agents
    python nexus_cli.py health          # Check server health
"""
import argparse
import json
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.bridge import AgentBridge, AgentType, get_bridge
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.config import get_config

# Default to local server
DEFAULT_SERVER = "http://localhost:8080"


def do_get(endpoint):
    """Make GET request to Nexus server."""
    import urllib.request
    import urllib.error
    
    url = f"{DEFAULT_SERVER}{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error: {e}")
        return None


def do_post(endpoint, data):
    """Make POST request to Nexus server."""
    import urllib.request
    import urllib.error
    
    url = f"{DEFAULT_SERVER}{endpoint}"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error: {e}")
        return None


def cmd_status(args):
    """Show full system status."""
    status = do_get("/status")
    if not status:
        print("Failed to get status from server")
        return 1
    
    print("\n=== NEXUS STATUS ===")
    
    print("\n--- Bridges ---")
    for agent, info in status['bridge'].items():
        print(f"  {agent}: {info['status']} ({info['url']})")
    
    print("\n--- Capabilities ---")
    caps = status['life']['capabilities']
    print(f"  Hermes: {caps['hermes']} capabilities")
    print(f"  PI: {caps['pi']} capabilities")
    
    print("\n--- Life Pillars ---")
    pillars = status['life'].get('pillars', {})
    if pillars:
        for name, stats in pillars.items():
            print(f"  {name}: {stats['contexts']} contexts, {stats['goals']} goals")
    else:
        print("  (none yet)")
    
    print("\n--- Goals ---")
    print(f"  Total: {status['life']['goals_total']}")
    print(f"  Completed: {status['life']['goals_completed']}")
    
    print("\n--- Configuration ---")
    config = status['config']
    print(f"  Version: {config['version']}")
    print(f"  Rate limit: {config['rate_limit']['per_minute']}/min")
    print(f"  Min confidence: {config['governance']['min_confidence']}")
    
    return 0


def cmd_health(args):
    """Check server health."""
    health = do_get("/health")
    if health:
        print(f"OK - Server time: {health['time']}")
        return 0
    print("Server is not responding")
    return 1


def cmd_connect(args):
    """Connect to an agent."""
    agent = args.agent.lower()
    url = args.url or None
    
    data = {"agent": agent}
    if url:
        data["url"] = url
    
    result = do_post("/connect", data)
    if result:
        if result.get('success'):
            print(f"Successfully connected to {agent}")
            return 0
        else:
            print(f"Failed to connect to {agent}")
            return 1
    return 1


def cmd_pillars(args):
    """List life pillars."""
    status = do_get("/status")
    if not status:
        return 1
    
    pillars = status['life'].get('pillars', {})
    if not pillars:
        print("No pillars defined")
        return 0
    
    print("\n=== LIFE PILLARS ===")
    for name, stats in pillars.items():
        print(f"\n{name}")
        print(f"  Contexts: {stats['contexts']}")
        print(f"  Goals: {stats['goals']}")
    
    return 0


def cmd_capabilities(args):
    """List agent capabilities."""
    engine = LifeContextEngine()
    
    print("\n=== AGENT CAPABILITIES ===")
    
    h_caps = engine.get_capabilities("hermes")
    print(f"\nHermes ({len(h_caps)}):")
    for cap in h_caps:
        print(f"  - {cap}")
    
    p_caps = engine.get_capabilities("pi")
    print(f"\nPI ({len(p_caps)}):")
    for cap in p_caps:
        print(f"  - {cap}")
    
    return 0


def cmd_goals(args):
    """List goals."""
    life = do_get("/life")
    if not life:
        return 1
    
    print("\n=== GOALS ===")
    print(f"Total: {life['goals_total']}")
    print(f"Completed: {life['goals_completed']}")
    print(f"Pending votes: {life['pending_votes']}")
    
    return 0


def cmd_goal_add(args):
    """Add a new goal."""
    title = args.title
    pillar = args.pillar
    description = args.description or title
    
    engine = LifeContextEngine()
    goal = engine.add_goal(title, description, pillar)
    
    print(f"Added goal: {goal.id}")
    print(f"  Title: {goal.title}")
    print(f"  Pillar: {goal.pillar}")
    print(f"  Status: {goal.status}")
    
    return 0


def cmd_goal_update(args):
    """Update goal progress."""
    goal_id = args.goal_id
    progress = float(args.progress)
    
    engine = LifeContextEngine()
    result = engine.update_goal_progress(goal_id, progress)
    
    if result:
        goal = next((g for g in engine.goals if g.id == goal_id), None)
        if goal:
            print(f"Updated {goal_id}:")
            print(f"  Progress: {goal.progress}%")
            print(f"  Status: {goal.status}")
            return 0
    
    print(f"Goal {goal_id} not found")
    return 1


def cmd_sample_data(args):
    """Add sample data for demo."""
    engine = LifeContextEngine()
    result = engine.add_sample_data()
    
    print("\n=== SAMPLE DATA ADDED ===")
    print(f"Contexts: {result['contexts']}")
    print(f"Goals: {result['goals']}")
    print(f"Capabilities: {result['capabilities']}")
    
    return 0


def cmd_sync(args):
    """Sync context with connected agents."""
    result = do_post("/sync", {"context": {}})
    
    if result and result.get('success'):
        print("Context synced successfully")
        return 0
    print("Failed to sync context")
    return 1


def cmd_discover(args):
    """Force capability discovery."""
    engine = LifeContextEngine()
    
    engine.discover_capabilities("hermes")
    engine.discover_capabilities("pi")
    
    h_caps = len(engine.get_capabilities("hermes"))
    p_caps = len(engine.get_capabilities("pi"))
    
    print(f"Discovered {h_caps} Hermes capabilities")
    print(f"Discovered {p_caps} PI capabilities")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Nexus CLI - Control and manage the Nexus agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Status
    subparsers.add_parser('status', help='Show full system status')
    
    # Health
    subparsers.add_parser('health', help='Check server health')
    
    # Connect
    connect_parser = subparsers.add_parser('connect', help='Connect to an agent')
    connect_parser.add_argument('agent', choices=['hermes', 'pi'], help='Agent to connect to')
    connect_parser.add_argument('--url', '-u', help='Agent URL (optional)')
    
    # Pillars
    subparsers.add_parser('pillars', help='List life pillars')
    
    # Capabilities
    subparsers.add_parser('capabilities', help='List agent capabilities')
    
    # Goals
    subparsers.add_parser('goals', help='Show goal summary')
    
    # Goal add
    goal_add = subparsers.add_parser('goal', help='Goal management')
    goal_sub = goal_add.add_subparsers(dest='goal_command')
    
    add_parser = goal_sub.add_parser('add', help='Add a new goal')
    add_parser.add_argument('title', help='Goal title')
    add_parser.add_argument('pillar', help='Pillar name')
    add_parser.add_argument('--description', '-d', help='Goal description')
    
    update_parser = goal_sub.add_parser('update', help='Update goal progress')
    update_parser.add_argument('goal_id', help='Goal ID')
    update_parser.add_argument('progress', type=float, help='Progress (0-100)')
    
    # Sample data
    sample_parser = subparsers.add_parser('sample', help='Add sample data')
    
    # Sync
    subparsers.add_parser('sync', help='Sync context with agents')
    
    # Discover
    subparsers.add_parser('discover', help='Force capability discovery')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    commands = {
        'status': cmd_status,
        'health': cmd_health,
        'connect': cmd_connect,
        'pillars': cmd_pillars,
        'capabilities': cmd_capabilities,
        'goals': cmd_goals,
        'goal': cmd_goal_add if hasattr(args, 'goal_command') and args.goal_command == 'add' else cmd_goal_update if hasattr(args, 'goal_command') and args.goal_command == 'update' else None,
        'sample': cmd_sample_data,
        'sync': cmd_sync,
        'discover': cmd_discover,
    }
    
    # Handle goal subcommand
    if args.command == 'goal':
        if hasattr(args, 'goal_command'):
            if args.goal_command == 'add':
                return cmd_goal_add(args)
            elif args.goal_command == 'update':
                return cmd_goal_update(args)
    
    cmd = commands.get(args.command)
    if cmd:
        return cmd(args)
    
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())