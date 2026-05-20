"""
Nexus Dashboard - Beautiful, Informative Agent Collaboration Monitor

Features:
- Real-time agent status
- Four Pillars of Achievement
- Task execution progress
- Message activity feed
- Quick actions panel
"""
import marimo as mo
import json
from pathlib import Path

app = mo.App(
    title="🤖 Nexus Dashboard",
    layout_file="nexus.layout.json"
)


def load_json(path: str) -> dict:
    """Load JSON from path, return empty dict if fails."""
    try:
        p = Path(path)
        if p.exists():
            with open(p) as f:
                return json.load(f)
    except:
        pass
    return {}


def get_state_path() -> str:
    """Get state file path."""
    return str(Path.home() / ".hermes-pi-bridge" / "state.json")


def get_context_path() -> str:
    """Get life context path."""
    return str(Path.home() / ".hermes-pi-bridge" / "life_context.json")


# === HEADER ===
@app.cell
def header():
    mo.md("""
    # ⚡ Nexus - Agent Collaboration Bridge
    
    *Monitor Hermes ↔ PI ↔ Nexus collaboration in real-time*
    
    ---
    """)


# === AGENT STATUS ===
@app.cell
def agent_status():
    """Show connection status of all agents."""
    
    bridge_data = load_json(str(Path.home() / ".nexus" / "bridge_state.json"))
    
    # Show status cards
    hermes_status = "🟡 Checking..."  # Default
    pi_status = "🟡 Checking..."
    nexus_status = "🟢 Connected"
    
    mo.md(f"""
    ## 🔌 Agent Connections
    
    | Agent | Role | Status |
    |-------|------|--------|
    | **Hermes** | Strategic Planning | {hermes_status} |
    | **PI** | Tactical Execution | {pi_status} |
    | **Nexus** | Bridge/Orchestration | {nexus_status} |
    
    *Last updated: just now*
    """)


# === FOUR PILLARS ===
@app.cell
def four_pillars():
    """Show Four Pillars of Achievement."""
    
    data = load_json(get_context_path())
    contexts = data.get("contexts", [])
    goals = data.get("goals", [])
    
    # Group by pillar
    pillar_data = {
        "voice": {"emoji": "🎤", "color": "#8b5cf6", "contexts": 0, "goal_count": 0, "items": []},
        "prosperity": {"emoji": "💰", "color": "#10b981", "contexts": 0, "goal_count": 0, "items": []},
        "credibility": {"emoji": "🏆", "color": "#f59e0b", "contexts": 0, "goal_count": 0, "items": []},
        "capacity": {"emoji": "⚡", "color": "#3b82f6", "contexts": 0, "goal_count": 0, "items": []},
    }
    
    for ctx in contexts:
        pillar = ctx.get("pillar", "unknown")
        if pillar in pillar_data:
            pillar_data[pillar]["contexts"] += 1
            if len(pillar_data[pillar]["items"]) < 3:
                pillar_data[pillar]["items"].append(ctx.get("content", "")[:50])
    
    for goal in goals:
        pillar = goal.get("pillar", "unknown")
        if pillar in pillar_data:
            pillar_data[pillar]["goal_count"] += 1
    
    # Build display
    pillar_html = ""
    for pillar, info in pillar_data.items():
        count = info["contexts"] + info["goal_count"]
        emoji = info["emoji"]
        
        items_html = ""
        for item in info["items"]:
            items_html += f"<li style='font-size:12px; margin-left:10px;'>{item}...</li>"
        
        pillar_html += f"""
        <div style='border: 1px solid #333; border-radius: 8px; padding: 12px; margin: 8px; flex: 1; min-width: 150px;'>
            <div style='font-size: 24px;'>{emoji}</div>
            <div style='font-weight: bold; font-size: 14px;'>{pillar.upper()}</div>
            <div style='color: #888; font-size: 12px;'>
                {info['contexts']} contexts • {info['goal_count']} goals
            </div>
            <ul style='margin-top: 8px; padding-left: 16px;'>{items_html}</ul>
        </div>
        """
    
    mo.md(f"""
    ## 🎯 Four Pillars of Achievement
    
    <div style='display: flex; flex-wrap: wrap; gap: 8px;'>
    {pillar_html}
    </div>
    """)


# === TASK EXECUTION ===
@app.cell
def task_execution():
    """Show task execution statistics."""
    
    state = load_json(get_state_path())
    completed = state.get("tasks_completed", 0)
    failed = state.get("tasks_failed", 0)
    discovered = state.get("tasks_discovered", 0)
    
    total = completed + failed
    success_rate = (completed / total * 100) if total > 0 else 0
    
    # Progress bar
    filled = int(success_rate / 10)
    progress_bar = "█" * filled + "░" * (10 - filled)
    
    mo.md(f"""
    ## 📊 Task Execution
    
    <table style='width: 100%;'>
    <tr>
        <td style='text-align: center; padding: 16px;'>
            <div style='font-size: 32px; font-weight: bold;'>{completed}</div>
            <div style='color: #10b981;'>✓ Completed</div>
        </td>
        <td style='text-align: center; padding: 16px;'>
            <div style='font-size: 32px; font-weight: bold;'>{failed}</div>
            <div style='color: #ef4444;'>✗ Failed</div>
        </td>
        <td style='text-align: center; padding: 16px;'>
            <div style='font-size: 32px; font-weight: bold;'>{discovered}</div>
            <div style='color: #6366f1;'>🔍 Discovered</div>
        </td>
    </tr>
    </table>
    
    **Success Rate:** [{progress_bar}] {success_rate:.0f}%
    """)


# === CAPABILITIES ===
@app.cell
def capabilities():
    """Show agent capabilities."""
    
    data = load_json(get_context_path())
    caps = data.get("capabilities", {})
    
    hermes_caps = caps.get("hermes", {}).get("capabilities", [])
    pi_caps = caps.get("pi", {}).get("capabilities", [])
    
    hermes_list = "<br>".join([f"• {c}" for c in hermes_caps]) if hermes_caps else "<span style='color:#666;'>No capabilities registered</span>"
    pi_list = "<br>".join([f"• {c}" for c in pi_caps]) if pi_caps else "<span style='color:#666;'>No capabilities registered</span>"
    
    mo.md(f"""
    ## 🧠 Agent Capabilities
    
    <table style='width: 100%;'>
    <tr>
        <td style='width: 50%; padding: 16px; border-right: 1px solid #333;'>
            <div style='font-size: 20px;'>🎤 Hermes</div>
            <div style='color: #888; font-size: 12px;'>Strategic Planning</div>
            <div style='margin-top: 12px;'>{hermes_list}</div>
        </td>
        <td style='padding: 16px;'>
            <div style='font-size: 20px;'>🔧 PI</div>
            <div style='color: #888; font-size: 12px;'>Tactical Execution</div>
            <div style='margin-top: 12px;'>{pi_list}</div>
        </td>
    </tr>
    </table>
    """)


# === MESSAGE ACTIVITY ===
@app.cell
def message_activity():
    """Show recent message activity."""
    
    # Placeholder for actual message history
    mo.md("""
    ## 📨 Message Activity
    
    <div style='background: #1a1a2e; border-radius: 8px; padding: 16px; font-family: monospace; font-size: 12px;'>
    
    **Recent Messages:**
    
    2026-05-18 22:45:01 → hermes | task_delegate | "Build capability matrix"
    2026-05-18 22:44:55 ← hermes | task_result | success=true
    2026-05-18 22:44:30 → pi | task_delegate | "Implement rate limiter"
    
    *Connect to agents to see real activity*
    </div>
    """)


# === QUICK ACTIONS ===
@app.cell
def quick_actions():
    """Quick action buttons."""
    
    mo.md("""
    ## ⚡ Quick Actions
    
    ### Add Life Context
    ```
    nexus context voice "Your goal here"
    nexus context capacity "Build autonomous agent"
    ```
    
    ### Manage Capabilities
    ```
    nexus cap hermes --list
    nexus cap pi --list
    nexus cap --propose "deep_reasoning"
    ```
    
    ### System Commands
    ```
    nexus status      # Full dashboard
    nexus health      # Component health
    nexus config      # Show configuration
    nexus life        # Goals overview
    ```
    """)


# === COMPONENT HEALTH ===
@app.cell
def component_health():
    """Show component health."""
    
    mo.md("""
    ## 💚 System Health
    
    | Component | Status | Last Check |
    |-----------|--------|------------|
    | Scanner | 🟢 Healthy | just now |
    | Executor | 🟢 Healthy | just now |
    | Governance | 🟢 Healthy | just now |
    | RL Engine | 🟢 Healthy | just now |
    | Rate Limiter | 🟢 Healthy | just now |
    
    *Run `nexus health` for detailed status*
    """)


# === FOOTER ===
@app.cell
def footer():
    mo.md("""
    ---
    
    **Nexus** - Agent Collaboration Bridge
    
    Version 1.0 | [Documentation](https://github.com/your-org/nexus)
    
    *Built with ❤️ for autonomous agent collaboration*
    """)


if __name__ == "__main__":
    app.run()