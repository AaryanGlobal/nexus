"""
Reinforcement Learning Module - Rewards and Punishments
Lightweight RL mechanism for the autonomous agent
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import json


class ActionType(Enum):
    """Types of actions the agent can take."""
    EXECUTE = "execute"
    DELEGATE = "delegate"
    SPLIT = "split"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    SKIP = "skip"


@dataclass
class RLConfig:
    """Configuration for RL module."""
    learning_rate: float = 0.1  # How fast to learn
    discount_factor: float = 0.9  # Future rewards importance
    exploration_rate: float = 0.2  # Epsilon-greedy exploration
    reward_success: float = 1.0  # Reward for successful action
    reward_failure: float = -1.0  # Penalty for failed action
    reward_efficiency: float = 0.1  # Bonus for efficient execution
    max_history: int = 1000  # Max experiences to store
    min_exploration: float = 0.05  # Minimum exploration rate
    
    def validate(self) -> list[str]:
        errors = []
        if not 0 <= self.learning_rate <= 1:
            errors.append("learning_rate must be 0-1")
        if not 0 <= self.discount_factor <= 1:
            errors.append("discount_factor must be 0-1")
        if not 0 <= self.exploration_rate <= 1:
            errors.append("exploration_rate must be 0-1")
        return errors


@dataclass
class Experience:
    """An experience for the agent to learn from."""
    state: str  # State description
    action: ActionType
    reward: float
    next_state: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class QValue:
    """Q-value for state-action pair."""
    action: ActionType
    value: float
    count: int = 0  # Number of times this action was taken


class ReinforcementLearning:
    """
    Lightweight RL module for rewards and punishments.
    
    Provides:
    - Q-learning for action selection
    - Epsilon-greedy exploration/exploitation
    - Reward/punishment for actions
    - Policy updates based on outcomes
    """
    
    def __init__(self, config: RLConfig | None = None):
        self.config = config or RLConfig()
        
        # Q-values: state -> {action -> (value, count)}
        self.q_table: dict[str, dict[ActionType, QValue]] = {}
        
        # Experience buffer for learning
        self.experiences: list[Experience] = []
        
        # Learning statistics
        self.total_rewards: float = 0.0
        self.total_punishments: float = 0.0
        self.actions_taken: dict[ActionType, int] = {a: 0 for a in ActionType}
        self.successes: dict[ActionType, int] = {a: 0 for a in ActionType}
        
        # Policy state
        self.current_state = "initial"
        self.best_actions: dict[str, ActionType] = {}  # Best action per state
    
    def get_q_value(self, state: str, action: ActionType) -> float:
        """Get Q-value for state-action pair."""
        if state not in self.q_table:
            return 0.0
        
        if action not in self.q_table[state]:
            return 0.0
        
        return self.q_table[state][action].value
    
    def update_q_value(self, state: str, action: ActionType, reward: float,
                      next_state: str) -> float:
        """
        Update Q-value using Q-learning formula.
        Q(s,a) = Q(s,a) + alpha * (r + gamma * max(Q(s',a')) - Q(s,a))
        """
        alpha = self.config.learning_rate
        gamma = self.config.discount_factor
        
        # Get current Q-value
        current_q = self.get_q_value(state, action)
        
        # Get max Q-value for next state
        max_next_q = max([self.get_q_value(next_state, a) for a in ActionType], default=0.0)
        
        # Q-learning update
        new_q = current_q + alpha * (reward + gamma * max_next_q - current_q)
        
        # Update Q-table
        if state not in self.q_table:
            self.q_table[state] = {}
        
        if action not in self.q_table[state]:
            self.q_table[state][action] = QValue(action=action, value=0.0, count=0)
        
        self.q_table[state][action].value = new_q
        self.q_table[state][action].count += 1
        
        return new_q
    
    def select_action(self, state: str, context: dict = None) -> tuple[ActionType, float]:
        """
        Select action using epsilon-greedy.
        Returns (action, confidence).
        """
        epsilon = self.config.exploration_rate
        context = context or {}
        
        # Exploration: random action
        if self._random() < epsilon:
            action = self._random_action()
            return action, 0.5  # Low confidence for exploration
        
        # Exploitation: best known action
        action = self._best_action(state)
        confidence = self._confidence(state, action)
        
        return action, confidence
    
    def _best_action(self, state: str) -> ActionType:
        """Get best action for state based on Q-values."""
        if state not in self.q_table:
            return ActionType.EXECUTE
        
        # Find action with highest Q-value
        best_action = ActionType.EXECUTE
        best_value = float('-inf')
        
        for action, q_value in self.q_table[state].items():
            if q_value.value > best_value:
                best_value = q_value.value
                best_action = action
        
        return best_action
    
    def _confidence(self, state: str, action: ActionType) -> float:
        """Calculate confidence based on Q-value and sample count."""
        q_value = self.get_q_value(state, action)
        
        if state not in self.q_table or action not in self.q_table[state]:
            return 0.5  # Unknown - 50% confidence
        
        count = self.q_table[state][action].count
        
        # More samples = higher confidence
        # Scale: 1 sample = 50%, 10 samples = 80%, 50+ samples = 95%
        base_confidence = min(q_value * 0.5 + 0.5, 0.95)  # Q-value influence
        sample_bonus = min(count / 50, 0.3)  # Up to 30% bonus for samples
        
        return min(base_confidence + sample_bonus, 0.95)
    
    def _random(self) -> float:
        """Get random float 0-1."""
        import random
        return random.random()
    
    def _random_action(self) -> ActionType:
        """Get random action."""
        import random
        return random.choice(list(ActionType))
    
    def reward(self, action: ActionType, success: bool, duration: float = 0,
              efficiency: float = 0, context: str = "default") -> float:
        """
        Apply reward or punishment based on action outcome.
        Returns total reward received.
        """
        reward = 0.0
        
        # Base reward/punishment
        if success:
            reward += self.config.reward_success
            self.total_rewards += reward
            self.successes[action] = self.successes.get(action, 0) + 1
        else:
            reward += self.config.reward_failure
            self.total_punishments += abs(reward)
        
        # Efficiency bonus (faster = better)
        if efficiency > 0:
            reward += self.config.reward_efficiency * efficiency
        
        # Update Q-value
        self.update_q_value(context, action, reward, "outcome")
        
        # Record experience
        experience = Experience(
            state=context,
            action=action,
            reward=reward,
            next_state="outcome"
        )
        self.experiences.append(experience)
        
        # Bound experience buffer
        if len(self.experiences) > self.config.max_history:
            self.experiences.pop(0)
        
        # Track action
        self.actions_taken[action] = self.actions_taken.get(action, 0) + 1
        
        return reward
    
    def get_policy(self, state: str) -> dict:
        """Get policy for a state."""
        if state not in self.q_table:
            return {"action": None, "confidence": 0.0, "q_values": {}}
        
        policy = {
            "action": self._best_action(state),
            "confidence": self._confidence(state, self._best_action(state)),
            "q_values": {
                a.value: qv.value for a, qv in self.q_table[state].items()
            }
        }
        
        return policy
    
    def get_statistics(self) -> dict:
        """Get RL statistics."""
        total_actions = sum(self.actions_taken.values())
        
        return {
            "total_rewards": self.total_rewards,
            "total_punishments": self.total_punishments,
            "reward_ratio": self.total_rewards / max(1, self.total_punishments),
            "actions_taken": dict(self.actions_taken),
            "success_rate": {
                a.value: self.successes.get(a, 0) / max(1, self.actions_taken.get(a, 0))
                for a in ActionType
            },
            "states_learned": len(self.q_table),
            "experiences": len(self.experiences),
            "exploration_rate": self.config.exploration_rate
        }
    
    def adjust_exploration(self, success_rate: float):
        """Adjust exploration rate based on performance."""
        if success_rate > 0.9:
            # High success = reduce exploration
            self.config.exploration_rate = max(0.05, self.config.exploration_rate - 0.01)
        elif success_rate < 0.5:
            # Low success = increase exploration
            self.config.exploration_rate = min(0.3, self.config.exploration_rate + 0.01)
    
    def reset(self):
        """Reset all learning."""
        self.q_table.clear()
        self.experiences.clear()
        self.total_rewards = 0.0
        self.total_punishments = 0.0
        self.actions_taken = {a: 0 for a in ActionType}
        self.successes = {a: 0 for a in ActionType}
    
    # === PERSISTENCE ===
    
    def save(self, path: str) -> bool:
        """Save Q-table and state to file."""
        import json
        from pathlib import Path
        
        data = {
            "q_table": {
                state: {
                    action.value: {"value": qv.value, "count": qv.count}
                    for action, qv in actions.items()
                }
                for state, actions in self.q_table.items()
            },
            "experiences": [
                {"state": e.state, "action": e.action.value, "reward": e.reward, "next_state": e.next_state}
                for e in self.experiences[-100:]  # Keep last 100
            ],
            "total_rewards": self.total_rewards,
            "total_punishments": self.total_punishments,
            "actions_taken": {a.value: count for a, count in self.actions_taken.items()},
            "successes": {a.value: count for a, count in self.successes.items()},
            "config": {
                "learning_rate": self.config.learning_rate,
                "discount_factor": self.config.discount_factor,
                "exploration_rate": self.config.exploration_rate
            },
            "saved_at": self._datetime_now().isoformat()
        }
        
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            return False
    
    def load(self, path: str) -> bool:
        """Load Q-table and state from file."""
        import json
        
        try:
            with open(path) as f:
                data = json.load(f)
            
            # Restore Q-table
            self.q_table.clear()
            for state, actions in data.get("q_table", {}).items():
                self.q_table[state] = {}
                for action_val, qv_data in actions.items():
                    action = ActionType(action_val)
                    self.q_table[state][action] = QValue(
                        action=action,
                        value=qv_data["value"],
                        count=qv_data["count"]
                    )
            
            # Restore experiences
            self.experiences = []
            for e_data in data.get("experiences", []):
                self.experiences.append(Experience(
                    state=e_data["state"],
                    action=ActionType(e_data["action"]),
                    reward=e_data["reward"],
                    next_state=e_data["next_state"]
                ))
            
            # Restore stats
            self.total_rewards = data.get("total_rewards", 0.0)
            self.total_punishments = data.get("total_punishments", 0.0)
            self.actions_taken = {
                ActionType(a): c for a, c in data.get("actions_taken", {}).items()
            }
            self.successes = {
                ActionType(a): c for a, c in data.get("successes", {}).items()
            }
            
            # Restore config
            cfg = data.get("config", {})
            if "learning_rate" in cfg:
                self.config.learning_rate = cfg["learning_rate"]
            if "exploration_rate" in cfg:
                self.config.exploration_rate = cfg["exploration_rate"]
            
            return True
        except Exception:
            return False
    
    # === STATS AND METRICS ===
    
    def get_stats(self) -> dict:
        """Get RL statistics as a dict."""
        return self.get_statistics()
    
    def get_metrics(self) -> dict:
        """Get detailed learning metrics."""
        return {
            "total_updates": sum(qv.count for state in self.q_table.values() for qv in state.values()),
            "q_values": {
                state: {a.value: qv.value for a, qv in actions.items()}
                for state, actions in self.q_table.items()
            },
            "best_actions": {
                state: self._best_action(state).value for state in self.q_table.keys()
            },
            "learning_history": [
                {"state": e.state, "action": e.action.value, "reward": e.reward}
                for e in self.experiences[-20:]
            ],
            "exploration_vs_exploitation": {
                "exploration_rate": self.config.exploration_rate,
                "exploitation_rate": 1.0 - self.config.exploration_rate
            }
        }
    
    def _datetime_now(self):
        """Get current datetime."""
        from datetime import datetime
        return datetime.now()