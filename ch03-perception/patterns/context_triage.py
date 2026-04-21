from dataclasses import dataclass
from enum import IntEnum
from typing import List

class Priority(IntEnum):
    CRITICAL = 4     # System prompt, safety rules, active task
    IMPORTANT = 3    # Active files, recent results, error traces
    SUPPORTING = 2   # Background docs, older conversation
    DEFERRABLE = 1   # Available via tools, not loaded

@dataclass
class ContextItem:
    name: str
    content: str
    priority: Priority
    token_estimate: int = 0
    is_error: bool = False       # Error traces get special protection

    def __post_init__(self):
        if self.token_estimate == 0:
            self.token_estimate = \
                len(self.content) // 4  #A

class ContextTriage:
    def __init__(self, budget: int = 180_000):  #B
        self.budget = budget

    def triage(self, items: List[ContextItem]):
        sorted_items = sorted(  #C
            items,
            key=lambda x: (
                x.priority.value,
                2.0 if x.is_error else 0.0,
                len(x.content),
            ),
            reverse=True,
        )

        selected, deferred, tokens_used = [], [], 0

        for item in sorted_items:
            if item.priority == Priority.DEFERRABLE:
                deferred.append(item)  #D
                continue
            if tokens_used + item.token_estimate <= self.budget:
                selected.append(item)
                tokens_used += item.token_estimate

        return selected, deferred
