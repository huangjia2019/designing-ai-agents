"""CollaborationTrace — observable record of multi-agent coordination."""
from dataclasses import dataclass, field


@dataclass
class AgentMessage:
    """One message between agents in a collaboration."""
    sender: str
    recipient: str
    content: str
    timestamp: float = 0.0


@dataclass
class CollaborationTrace:
    handoffs: int = 0
    parallel_calls: int = 0
    conflicts_detected: int = 0
    total_tokens: int = 0
    messages: list[AgentMessage] = field(default_factory=list)
