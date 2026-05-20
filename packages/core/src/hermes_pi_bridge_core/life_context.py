"""
Life Context Engine - Deep Context for Personal Goals
Tracks Hermes and PI capabilities for task routing
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentCapabilities:
    """Capabilities for an agent (Hermes or PI)."""
    agent: str
    capabilities: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class LifeContext:
    """A piece of verified life context."""
    id: str
    content: str
    pillar: str  # Simple string - user can add any
    category: str
    created_at: datetime = field(default_factory=datetime.now)
    verified: bool = True
    tags: list[str] = field(default_factory=list)
    shared_with: list[str] = field(default_factory=list)  # Track which agents received this


@dataclass
class LifeGoal:
    """A life goal."""
    id: str
    title: str
    description: str
    pillar: str
    status: str = "not_started"
    progress: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    shared_with: list[str] = field(default_factory=list)  # Track which agents received this


class LifeContextEngine:
    """
    Deep Context Engine - Tracks life goals and agent capabilities.
    
    Simple, pragmatic design:
    - Life goals in pillars (user can add any pillar)
    - Hermes and PI capabilities tracked separately
    - Consensus voting for capability additions
    - No hardcoded enums - use strings
    """
    
    def __init__(self, storage_path: str | None = None):
        self.storage_path = storage_path or str(Path.home() / ".nexus" / "life_context.json")
        self.contexts: list[LifeContext] = []
        self.goals: list[LifeGoal] = []
        self.capabilities: dict[str, AgentCapabilities] = {
            "hermes": AgentCapabilities(agent="hermes"),
            "pi": AgentCapabilities(agent="pi"),
        }
        self.capability_votes: list[dict] = []
        self._load()
        
        # Auto-discover capabilities for all agents on init
        self.discover_capabilities("hermes")
        self.discover_capabilities("pi")
    
    # === ERROR RECOVERY ===
    
    def reset(self) -> None:
        """Reset engine to clean state (preserves storage path)."""
        self.contexts.clear()
        self.goals.clear()
        self.capability_votes.clear()
        # Re-initialize capabilities
        self.capabilities = {
            "hermes": AgentCapabilities(agent="hermes"),
            "pi": AgentCapabilities(agent="pi"),
        }
        logger.info("Life context engine reset")
    
    def repair(self) -> bool:
        """Attempt to repair corrupted storage."""
        try:
            self._load()
            return True
        except Exception as e:
            logger.error(f"Repair failed: {e}")
            return False
    
    def recover(self) -> bool:
        """Recover from error state."""
        return self.repair()
    
    def handle_error(self, error: Exception, context: str = "") -> None:
        """Handle and log errors."""
        logger.error(f"Life engine error in {context}: {error}")
    
    def _load(self):
        """Load from storage."""
        try:
            path = Path(self.storage_path)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                    
                    # Load contexts (handle extra fields gracefully)
                    self.contexts = []
                    for c in data.get('contexts', []):
                        # Filter to only known fields
                        valid_fields = ['id', 'content', 'pillar', 'category', 'created_at', 
                                        'verified', 'tags', 'shared_with']
                        filtered = {k: v for k, v in c.items() if k in valid_fields}
                        self.contexts.append(LifeContext(**filtered))
                    
                    # Load goals (handle extra fields gracefully)
                    self.goals = []
                    for g in data.get('goals', []):
                        valid_fields = ['id', 'title', 'description', 'pillar', 'status',
                                       'progress', 'created_at', 'completed_at', 'shared_with']
                        filtered = {k: v for k, v in g.items() if k in valid_fields}
                        self.goals.append(LifeGoal(**filtered))
                    
                    # Load capabilities
                    caps_data = data.get('capabilities', {})
                    for agent, caps in caps_data.items():
                        self.capabilities[agent] = AgentCapabilities(
                            agent=agent,
                            capabilities=caps.get('capabilities', []),
                            skills=caps.get('skills', [])
                        )
                    
                    self.capability_votes = data.get('capability_votes', [])
                    logger.info(f"Loaded {len(self.contexts)} contexts, {len(self.goals)} goals")
        except Exception as e:
            logger.warning(f"Could not load context: {e}")
    
    def _save(self):
        """Save to storage atomically."""
        import tempfile
        path = Path(self.storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'contexts': [c.__dict__ for c in self.contexts],
            'goals': [g.__dict__ for g in self.goals],
            'capabilities': {
                agent: {'capabilities': caps.capabilities, 'skills': caps.skills}
                for agent, caps in self.capabilities.items()
            },
            'capability_votes': self.capability_votes,
            'saved_at': datetime.now().isoformat()
        }
        
        tmp = path.with_suffix('.tmp')
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        tmp.rename(path)
    
    # === CONTEXT ===
    
    def add_context(self, content: str, pillar: str, category: str = "goal") -> LifeContext:
        """Add verified context."""
        ctx = LifeContext(
            id=f"ctx_{len(self.contexts)}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            content=content,
            pillar=pillar,
            category=category
        )
        self.contexts.append(ctx)
        self._save()
        return ctx
    
    def get_pillars(self) -> list[str]:
        """Get all unique pillars."""
        return list(set(c.pillar for c in self.contexts))
    
    def get_contexts_by_pillar(self, pillar: str) -> list[LifeContext]:
        """Get contexts for a pillar."""
        return [c for c in self.contexts if c.pillar == pillar]
    
    # === GOALS ===
    
    def add_goal(self, title: str, description: str, pillar: str) -> LifeGoal:
        """Add a goal."""
        goal = LifeGoal(
            id=f"goal_{len(self.goals)}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            title=title,
            description=description,
            pillar=pillar
        )
        self.goals.append(goal)
        self._save()
        return goal
    
    def update_goal_progress(self, goal_id: str, progress: float) -> bool:
        """Update goal progress."""
        goal = next((g for g in self.goals if g.id == goal_id), None)
        if not goal:
            return False
        
        goal.progress = max(0, min(100, progress))
        if progress >= 100:
            goal.status = "completed"
            goal.completed_at = datetime.now()
        elif progress > 0:
            goal.status = "in_progress"
        
        self._save()
        return True
    
    def get_goals_by_pillar(self, pillar: str) -> list[LifeGoal]:
        """Get goals for a pillar."""
        return [g for g in self.goals if g.pillar == pillar]
    
    # === CAPABILITIES ===
    
    def add_capability(self, agent: str, capability: str, skill: str | None = None):
        """Add capability to an agent."""
        if agent not in self.capabilities:
            self.capabilities[agent] = AgentCapabilities(agent=agent)
        
        caps = self.capabilities[agent]
        if capability not in caps.capabilities:
            caps.capabilities.append(capability)
        if skill and skill not in caps.skills:
            caps.skills.append(skill)
        
        caps.last_updated = datetime.now()
        self._save()
    
    def propose_capability(self, capability: str, proposed_by: str) -> str:
        """Propose capability for consensus."""
        vote_id = f"vote_{len(self.capability_votes)}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        vote = {
            'id': vote_id,
            'capability': capability,
            'proposed_by': proposed_by,
            'votes': [],
            'status': 'pending'
        }
        self.capability_votes.append(vote)
        self._save()
        return vote_id
    
    def vote_capability(self, vote_id: str, voter: str, approve: bool, reasoning: str = ""):
        """Vote on capability proposal."""
        vote = next((v for v in self.capability_votes if v['id'] == vote_id), None)
        if not vote:
            return False
        
        vote['votes'].append({
            'voter': voter,
            'approve': approve,
            'reasoning': reasoning,
            'timestamp': datetime.now().isoformat()
        })
        
        # Check consensus (2 of 3 agree)
        approvals = len([v for v in vote['votes'] if v['approve']])
        rejections = len([v for v in vote['votes'] if not v['approve']])
        
        if approvals >= 2:
            vote['status'] = 'approved'
            self.add_capability('hermes', vote['capability'])
            self.add_capability('pi', vote['capability'])
        elif rejections >= 2:
            vote['status'] = 'rejected'
        
        self._save()
        return True
    
    def get_capabilities(self, agent: str) -> list[str]:
        """Get capabilities for an agent."""
        return self.capabilities.get(agent, AgentCapabilities(agent=agent)).capabilities
    
    def can_handle_task(self, agent: str, task_requirements: list[str]) -> tuple[bool, list[str]]:
        """Check if agent can handle task requirements."""
        caps = self.get_capabilities(agent)
        missing = [req for req in task_requirements if req not in caps]
        return len(missing) == 0, missing
    
    # === STATUS ===
    
    def get_status(self) -> dict:
        """Get full status."""
        pillar_stats = {}
        for pillar in self.get_pillars():
            pillar_stats[pillar] = {
                'contexts': len(self.get_contexts_by_pillar(pillar)),
                'goals': len(self.get_goals_by_pillar(pillar))
            }
        
        return {
            'pillars': pillar_stats,
            'goals_total': len(self.goals),
            'goals_completed': len([g for g in self.goals if g.status == 'completed']),
            'capabilities': {
                agent: len(caps.capabilities)
                for agent, caps in self.capabilities.items()
            },
            'pending_votes': len([v for v in self.capability_votes if v['status'] == 'pending'])
        }
    
    # === TASK ROUTING ===
    
    def route_task(self, requirements: list[str]) -> str | None:
        """Route a task to the best available agent.
        
        Args:
            requirements: List of required capabilities
            
        Returns:
            Agent name ('hermes' or 'pi') or None if no agent can handle
        """
        # Find the best agent
        agent = self.find_best_agent(requirements)
        return agent
    
    def find_best_agent(self, requirements: list[str]) -> str | None:
        """Find the best agent for given requirements.
        
        Args:
            requirements: List of required capabilities
            
        Returns:
            Agent name or None if no agent can handle
        """
        candidates = []
        
        # Check both agents
        for agent_name in ["hermes", "pi"]:
            can_handle, missing = self.can_handle_task(agent_name, requirements)
            if can_handle:
                # Score based on how well it matches
                caps = self.get_capabilities(agent_name)
                score = len([c for c in caps if c in requirements])
                candidates.append((agent_name, score))
        
        if candidates:
            # Return the one with highest match score
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        
        return None
    
    def best_agent_for(self, requirements: list[str]) -> str | None:
        """Alias for find_best_agent."""
        return self.find_best_agent(requirements)
    
    def get_stats(self) -> dict:
        """Get life engine statistics."""
        return {
            'total_contexts': len(self.contexts),
            'total_goals': len(self.goals),
            'completed_goals': len([g for g in self.goals if g.status == 'completed']),
            'total_pillars': len(self.get_pillars()),
            'pending_votes': len([v for v in self.capability_votes if v['status'] == 'pending']),
            'hermes_capabilities': len(self.get_capabilities('hermes')),
            'pi_capabilities': len(self.get_capabilities('pi')),
        }
    
    # === CAPABILITY DISCOVERY ===
    
    def discover_capabilities(self, agent: str) -> list[str]:
        """Auto-discover capabilities based on agent type.
        
        Hermes (strategic): planning, strategy, reasoning, analysis, long-term thinking
        PI (tactical): coding, execution, tools, implementation, rapid response
        """
        if agent == "hermes":
            # Hermes is strategic - has planning and reasoning capabilities
            strategic_caps = [
                "planning", "strategy", "reasoning", "analysis",
                "long_term_thinking", "goal_setting", "decision_making",
                "resource_allocation", "risk_assessment", "pattern_recognition"
            ]
            for cap in strategic_caps:
                self.add_capability("hermes", cap)
            return strategic_caps
        
        elif agent == "pi":
            # PI is tactical - has execution and tool capabilities
            tactical_caps = [
                "coding", "execution", "implementation", "tools",
                "rapid_response", "code_generation", "debugging",
                "testing", "deployment", "documentation"
            ]
            for cap in tactical_caps:
                self.add_capability("pi", cap)
            return tactical_caps
        
        return []
    
    def share_context(self, agent: str) -> bool:
        """Share context with an agent (mark as shared)."""
        # Mark all current contexts as shared with this agent
        shared_count = 0
        for ctx in self.contexts:
            # Add shared tag if not already present
            if not hasattr(ctx, 'shared_with') or ctx.shared_with is None:
                ctx.shared_with = []
            if agent not in ctx.shared_with:
                ctx.shared_with.append(agent)
                shared_count += 1
        
        # Mark goals as shared too
        for goal in self.goals:
            if not hasattr(goal, 'shared_with') or goal.shared_with is None:
                goal.shared_with = []
            if agent not in goal.shared_with:
                goal.shared_with.append(agent)
        
        if shared_count > 0:
            self._save()
        
        return True
    
    def get_shared_context(self) -> list[dict]:
        """Get all shared context as dict."""
        shared = []
        
        # Include contexts with share info
        for ctx in self.contexts:
            shared.append({
                'id': ctx.id,
                'content': ctx.content,
                'pillar': ctx.pillar,
                'category': ctx.category,
                'shared_with': getattr(ctx, 'shared_with', []),
                'verified': ctx.verified
            })
        
        # Include goals
        for goal in self.goals:
            shared.append({
                'id': goal.id,
                'title': goal.title,
                'description': goal.description,
                'pillar': goal.pillar,
                'status': goal.status,
                'progress': goal.progress,
                'shared_with': getattr(goal, 'shared_with', [])
            })
        
        return shared
    
    # === SAMPLE DATA ===
    
    def add_sample_data(self) -> dict:
        """Add sample life context data for demonstration.
        
        Returns dict with what was added.
        """
        added = {'contexts': 0, 'goals': 0, 'capabilities': 0}
        
        # Add sample context for common pillars
        sample_contexts = [
            ("Build thought leadership in AI agent development", "voice"),
            ("Master full-stack development with modern tools", "capacity"),
            ("Achieve financial independence through smart investments", "prosperity"),
            ("Maintain physical and mental health for peak performance", "vitality"),
            ("Build meaningful relationships and network", "relationships"),
        ]
        
        for content, pillar in sample_contexts:
            self.add_context(content, pillar, "goal")
            added['contexts'] += 1
        
        # Add sample goals
        sample_goals = [
            ("Build AI Agent System", "Create autonomous agent with learning capabilities", "capacity"),
            ("Run Half Marathon", "Complete 13.1 mile race in under 2 hours", "vitality"),
            ("Publish Technical Blog", "Write 12 technical articles about AI and development", "voice"),
        ]
        
        for title, desc, pillar in sample_goals:
            self.add_goal(title, desc, pillar)
            added['goals'] += 1
        
        # Auto-discover capabilities
        self.discover_capabilities("hermes")
        self.discover_capabilities("pi")
        added['capabilities'] = 10
        
        return added