#!/usr/bin/env python3
"""
Hermes Core Control Panel - Management Interface

Provides commands to manage the Hermes orchestration server:
- Start/stop server
- List, cancel, retry tasks
- Manage callbacks
- Monitor status
- Pause/resume processing

Usage:
    python hermes_control.py status
    python hermes_control.py list
    python hermes_control.py callbacks add http://localhost:9999/notify
    python hermes_control.py cancel <kanban_id>
    python hermes_control.py server --port 8080
"""
import argparse
import json
import sys
import time
from pathlib import Path

# Add nexus root to path
sys.path.insert(0, str(Path(__file__).parent))

from hermes_core import HermesCore, TaskStatus

# ANSI colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def color_status(status: str) -> str:
    """Color code task status."""
    if status == 'completed':
        return f"{GREEN}{status}{RESET}"
    elif status == 'failed':
        return f"{RED}{status}{RESET}"
    elif status == 'pending':
        return f"{YELLOW}{status}{RESET}"
    elif status == 'processing':
        return f"{BLUE}{status}{RESET}"
    return status

def cmd_status(hermes: HermesCore, args):
    """Show server status and summary."""
    status = hermes.get_status()
    
    print(f"\n{BOLD}=== Hermes Core Status ==={RESET}")
    print(f"  Running: {'Yes' if status['running'] else 'No'}")
    print(f"  Connected Pi clients: {status['connected_pis']}")
    print(f"  Tasks - Total: {status['tasks_total']} | Pending: {status['tasks_pending']} | Processing: {status['tasks_processing']} | Completed: {status['tasks_completed']}")
    print(f"  Callbacks registered: {len(hermes.callback_urls)}")
    print()

def cmd_list(hermes: HermesCore, args):
    """List tasks."""
    if args.filter == 'pending':
        tasks = hermes.get_pending_tasks()
        title = "Pending Tasks"
    elif args.filter == 'completed':
        tasks = hermes.get_completed_tasks(since_minutes=args.minutes)
        title = f"Recently Completed (last {args.minutes} min)"
    else:
        tasks = list(hermes.tasks.values())
        title = "All Tasks"
    
    print(f"\n{BOLD}=== {title} ({len(tasks)}) ==={RESET}\n")
    
    if not tasks:
        print("  No tasks")
        return
    
    for task in tasks[:args.limit]:
        status_color = color_status(task.status.value)
        print(f"  {task.kanban_id[:20]:<20} [{status_color}] {task.title[:40]}")
        if task.result:
            print(f"    Result: {task.result.get('summary', 'N/A')[:60]}")
        if task.error:
            print(f"    {RED}Error: {task.error[:60]}{RESET}")
        print()

def cmd_callbacks(hermes: HermesCore, args):
    """Manage callbacks."""
    if args.callback_action == 'list':
        print(f"\n{BOLD}=== Registered Callbacks ({len(hermes.callback_urls)}) ==={RESET}\n")
        if not hermes.callback_urls:
            print("  No callbacks registered")
        for url in hermes.callback_urls:
            print(f"  - {url}")
        print()
    
    elif args.callback_action == 'add':
        hermes.register_callback(args.url)
        print(f"{GREEN}✓{RESET} Callback registered: {args.url}")
    
    elif args.callback_action == 'remove':
        hermes.unregister_callback(args.url)
        print(f"{GREEN}✓{RESET} Callback removed: {args.url}")

def cmd_cancel(hermes: HermesCore, args):
    """Cancel a task."""
    kanban_id = args.kanban_id
    task = hermes.get_task(kanban_id)
    
    if not task:
        print(f"{RED}✗{RESET} Task not found: {kanban_id}")
        return
    
    if task.status == TaskStatus.COMPLETED:
        print(f"{RED}✗{RESET} Cannot cancel completed task")
        return
    
    # Mark as cancelled
    hermes.fail_task(kanban_id, "Cancelled by user")
    print(f"{GREEN}✓{RESET} Task cancelled: {kanban_id}")

def cmd_delegate(hermes: HermesCore, args):
    """Delegate a new task."""
    title = args.title or input("Task title: ").strip()
    description = args.description or input("Task description: ").strip()
    priority = args.priority or 'normal'
    
    if not title:
        print(f"{RED}✗{RESET} Title required")
        return
    
    if not description:
        print(f"{RED}✗{RESET} Description required")
        return
    
    task = hermes.create_task(title, description, priority)
    print(f"{GREEN}✓{RESET} Task created: {task.kanban_id}")

def cmd_complete(hermes: HermesCore, args):
    """Manually complete a task (for testing)."""
    kanban_id = args.kanban_id
    result = {"summary": args.summary or "Manually completed"}
    
    if hermes.complete_task(kanban_id, result):
        print(f"{GREEN}✓{RESET} Task completed: {kanban_id}")
    else:
        print(f"{RED}✗{RESET} Failed to complete task")

def cmd_wait(hermes: HermesCore, args):
    """Wait for tasks to complete (polling loop)."""
    print(f"\n{BOLD}=== Waiting for completion (Ctrl+C to stop) ==={RESET}\n")
    
    since = time.time()
    last_count = 0
    
    try:
        while True:
            results = hermes.get_results_since(since)
            
            if len(results) > last_count:
                for r in results[last_count:]:
                    print(f"{GREEN}✓{RESET} {r['kanban_id'][:20]:<20} [{color_status(r['status'])}] {r.get('summary', '')[:50]}")
                last_count = len(results)
            
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\n\nStopped. Total completed: {last_count}")

def cmd_server(hermes: HermesCore, args):
    """Start the HTTP server."""
    from http.server import HTTPServer
    from hermes_core import HermesAPIHandler, HermesAPIServer
    
    port = args.port
    host = args.host
    
    print(f"\n{BOLD}=== Starting Hermes Core Server ==={RESET}\n")
    print(f"  Host: {host}:{port}")
    print(f"  Endpoints:")
    print(f"    GET  /health - Health check")
    print(f"    GET  /status - Server status")
    print(f"    GET  /tasks - List tasks")
    print(f"    POST /delegate - Create task")
    print(f"    POST /complete - Complete task")
    print(f"    GET  /tasks?since=<ts> - Get results since timestamp")
    print(f"\n  Press Ctrl+C to stop\n")
    
    server = HermesAPIServer(host, port, hermes)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        server.shutdown()

def main():
    parser = argparse.ArgumentParser(description="Hermes Core Control Panel")
    parser.add_argument('--host', default='127.0.0.1', help='Hermes Core host (for remote control)')
    parser.add_argument('--port', type=int, default=8080, help='Hermes Core port')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # status command
    subparsers.add_parser('status', help='Show server status')
    
    # list command
    list_parser = subparsers.add_parser('list', help='List tasks')
    list_parser.add_argument('--filter', choices=['all', 'pending', 'completed'], default='all')
    list_parser.add_argument('--minutes', type=int, default=60, help='For completed filter')
    list_parser.add_argument('--limit', type=int, default=20, help='Max tasks to show')
    
    # callbacks command
    callbacks_parser = subparsers.add_parser('callbacks', help='Manage callbacks')
    callbacks_parser.add_argument('callback_action', choices=['list', 'add', 'remove'])
    callbacks_parser.add_argument('url', nargs='?', help='Callback URL')
    
    # cancel command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a task')
    cancel_parser.add_argument('kanban_id', help='Task kanban_id')
    
    # delegate command
    delegate_parser = subparsers.add_parser('delegate', help='Delegate a new task')
    delegate_parser.add_argument('--title', '-t', help='Task title')
    delegate_parser.add_argument('--description', '-d', help='Task description')
    delegate_parser.add_argument('--priority', choices=['low', 'normal', 'high'], default='normal')
    
    # complete command
    complete_parser = subparsers.add_parser('complete', help='Manually complete a task')
    complete_parser.add_argument('kanban_id', help='Task kanban_id')
    complete_parser.add_argument('--summary', '-s', help='Result summary')
    
    # wait command
    wait_parser = subparsers.add_parser('wait', help='Wait for task completions')
    wait_parser.add_argument('--interval', type=float, default=1.0, help='Poll interval (seconds)')
    
    # server command
    server_parser = subparsers.add_parser('server', help='Start HTTP server')
    server_parser.add_argument('--host', default='0.0.0.0', help='Bind host')
    server_parser.add_argument('--port', type=int, default=8080, help='Listen port')
    
    args = parser.parse_args()
    
    # Create Hermes Core instance
    hermes = HermesCore(host=args.host, port=args.port)
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to command handler
    commands = {
        'status': cmd_status,
        'list': cmd_list,
        'callbacks': cmd_callbacks,
        'cancel': cmd_cancel,
        'delegate': cmd_delegate,
        'complete': cmd_complete,
        'wait': cmd_wait,
        'server': cmd_server,
    }
    
    commands[args.command](hermes, args)

if __name__ == '__main__':
    main()