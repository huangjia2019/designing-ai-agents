from dataclasses import dataclass
from typing import List

@dataclass
class Turn:
    role: str           # "user", "assistant", "tool_result"
    content: str
    tokens: int
    is_error: bool = False

class SemanticCompactor:
    def __init__(self, llm, preserve_recent: int = 5):
        self.llm = llm
        self.preserve_recent = preserve_recent  #A

    def compact(self, turns: List[Turn], target: int):
        total = sum(t.tokens for t in turns)
        if total <= target:
            return turns  #B

        # Split: old compactable vs protected (recent + errors)
        boundary = len(turns) - self.preserve_recent
        old = [t for t in turns[:boundary] if not t.is_error]
        errors = [t for t in turns[:boundary]
                  if t.is_error]  #C
        recent = turns[boundary:]

        # Level 1: Clear verbose tool results
        cleared = self._clear_tools(old)
        if self._fits(cleared + errors + recent, target):
            return cleared + errors + recent

        # Level 2: Summarize old turns into one block
        summary = self._summarize(old)  #D
        return [summary] + errors + recent

    def _clear_tools(self, turns):
        result = []
        for t in turns:
            if t.role == "tool_result" and t.tokens > 500:
                result.append(Turn(
                    "tool_result",
                    f"[Cleared: {t.tokens} tokens. Re-run to retrieve.]",
                    tokens=25, is_error=False,
                ))
            else:
                result.append(t)
        return result

    def _summarize(self, turns):
        text = "\n".join(f"[{t.role}]: {t.content}" for t in turns)
        summary = self.llm.generate(  #E
            f"Summarize, preserving:\n"
            f"- All decisions made\n"
            f"- All file paths and function names\n"
            f"- Current progress and remaining work\n"
            f"Discard: redundant tool outputs, abandoned approaches.\n\n"
            f"{text}"
        )
        return Turn("system", f"[Summary]\n{summary}",
                    tokens=len(summary) // 4)

    def _fits(self, turns, target):
        return sum(t.tokens for t in turns) <= target
