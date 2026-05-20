#!/usr/bin/env python3
"""Simple entry point - run the agent."""
from hermes_pi_bridge_core.autonomous import AutonomousNHIL, AutonomousConfig

if __name__ == "__main__":
    agent = AutonomousNHIL()
    agent.start()
    
    print("Agent running. Press Ctrl+C to stop.")
    try:
        import time
        while agent.running:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop()
        print("Stopped.")
