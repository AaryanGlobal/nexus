#!/usr/bin/env python3
"""
Hermes-Nexus Orchestrator - Bridges Hermes Core with Pi

This daemon:
1. Connects to Hermes Core
2. Registers a callback URL for your server
3. Listens for task completions
4. Triggers next steps when tasks complete

Usage:
    python hermes_orchestrator.py --hermes-url http://localhost:8080 --callback-url http://localhost:9999/notify
    
Requirements:
    - Hermes Core server running
    - Your callback URL accessible from this machine
"""
import argparse
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Add nexus root
sys.path.insert(0, str(Path(__file__).parent))

from hermes_core import HermesCore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('orchestrator')


class HermesOrchestrator:
    """
    Orchestrates the Hermes-Pi loop.
    
    Monitors Hermes Core for task completions and triggers next steps.
    """
    
    def __init__(self, hermes_url: str, callback_url: str):
        self.hermes_url = hermes_url.rstrip('/')
        self.callback_url = callback_url
        self.hermes = HermesCore(host='localhost', port=8080)
        self.last_check = time.time()
        
        # Register our callback with Hermes Core
        self.hermes.register_callback(self.callback_url)
        logger.info(f"Registered callback: {self.callback_url}")
        
    def send_to_hermes(self, endpoint: str, data: dict):
        """Send request to Hermes Core."""
        url = f"{self.hermes_url}{endpoint}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode(),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def poll_for_results(self):
        """Poll Hermes for new results since last check."""
        since = self.last_check
        self.last_check = time.time()
        
        try:
            url = f"{self.hermes_url}/tasks?since={since}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
                return data.get('results', [])
        except Exception as e:
            logger.debug(f"Poll failed (using callback instead): {e}")
            return []
    
    def notify_me(self, task_result: dict):
        """
        Send notification to your callback URL when task completes.
        This is the KEY piece - you get notified immediately!
        """
        try:
            payload = {
                'type': 'task_completed',
                'kanban_id': task_result.get('kanban_id'),
                'title': task_result.get('title'),
                'status': task_result.get('status'),
                'result': task_result.get('result'),
                'artifacts': task_result.get('artifacts', []),
                'timestamp': time.time(),
            }
            
            req = urllib.request.Request(
                self.callback_url,
                data=json.dumps(payload).encode(),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"✓ Notified: {task_result.get('kanban_id')} → {self.callback_url}")
                return True
        except urllib.error.URLError as e:
            logger.warning(f"Callback failed (will retry): {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
    
    def run_loop(self, poll_interval: float = 5.0):
        """
        Main orchestration loop.
        
        1. Poll for new results (backup to callback)
        2. When task completes, notify you
        3. You decide next action
        """
        logger.info("=" * 50)
        logger.info("Hermes Orchestrator Started")
        logger.info(f"  Hermes Core: {self.hermes_url}")
        logger.info(f"  Your callback: {self.callback_url}")
        logger.info(f"  Poll interval: {poll_interval}s")
        logger.info("=" * 50)
        logger.info("")
        logger.info("When Pi completes a task:")
        logger.info(f"  1. Hermes Core calls {self.callback_url}")
        logger.info("  2. You receive notification instantly")
        logger.info("  3. Evaluate result → delegate next task")
        logger.info("")
        logger.info("Press Ctrl+C to stop")
        logger.info("")
        
        while True:
            try:
                # Poll for results (backup to callback)
                results = self.poll_for_results()
                
                for result in results:
                    kanban = result.get('kanban_id', '?')[:20]
                    status = result.get('status', '?')
                    logger.info(f"📬 Result: {kanban} [{status}]")
                    
                    # Notify you (redundant with callback, but ensures delivery)
                    self.notify_me(result)
                
                # Sleep before next poll
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                logger.info("\nStopping orchestrator...")
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="Hermes Orchestrator")
    parser.add_argument(
        '--hermes-url',
        default='http://localhost:8080',
        help='Hermes Core URL'
    )
    parser.add_argument(
        '--callback-url',
        required=True,
        help='Your callback URL to receive notifications'
    )
    parser.add_argument(
        '--poll-interval',
        type=float,
        default=5.0,
        help='Poll interval in seconds (default: 5)'
    )
    
    args = parser.parse_args()
    
    orchestrator = HermesOrchestrator(args.hermes_url, args.callback_url)
    orchestrator.run_loop(args.poll_interval)


if __name__ == '__main__':
    main()
