"""Bounded parallel exploration with a small UCT search."""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]

from patterns.response_text import first_text


MODEL = "claude-sonnet-4-6"

EXPAND_PROMPT = """The reasoning so far:
{path}

Propose {n} genuinely different ways to continue from here.
Different means a different approach, not the same idea in
new words: if two branches would be checked the same way,
they are one branch and you owe another one.

Each line is one step, not a whole solution. Stop at the
next decision worth making, and leave it open.

One per line, each starting with "- ". No preamble, no
numbering, no commentary.
"""

EVAL_PROMPT = """A partial line of reasoning:
{path}

Score how promising this path looks, from 0.00 (a dead end,
or already wrong) to 1.00 (all but solved). The path is
unfinished by design. Judge its direction, not whether it
has arrived.

Reply in exactly this format:
SCORE: <a number between 0.00 and 1.00>
WHY: <one sentence>
"""

_UNSCORED = 0.5
_SCORE_RE = re.compile(
    r"SCORE:\s*([+-]?[0-9]*\.?[0-9]+)\s*(%?)",
    re.IGNORECASE,
)


class ReasoningPath(list):
    """A root-to-node path that also renders cleanly in prompts."""

    def __str__(self) -> str:
        if not self:
            return "(nothing yet)"
        problem, *thoughts = self
        lines = [f"Problem: {problem}"]
        lines.extend(
            f"Step {index}: {thought}"
            for index, thought in enumerate(thoughts, 1)
        )
        return "\n".join(lines)


@dataclass
class ThoughtNode:
    id: str
    content: str
    parent_id: str | None = None
    children_ids: list[str] = field(default_factory=list)
    score: float = 0.0
    visits: int = 0
    total_value: float = 0.0


class ParallelReasoner:
    def __init__(self, client: Anthropic):
        self.client = client
        self.nodes: dict[str, ThoughtNode] = {}

    def expand(
        self,
        node: ThoughtNode,
        n_branches: int = 3,
    ) -> list[ThoughtNode]:
        limit = max(0, n_branches)
        if limit == 0:
            return []
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": EXPAND_PROMPT.format(
                    path=self._path_to_node(node),
                    n=limit,
                ),
            }],
        )
        return self._parse_thoughts(response, node, limit)

    @staticmethod
    def _parse_score(response) -> float:
        try:
            text = first_text(response)
        except ValueError:
            return _UNSCORED
        match = _SCORE_RE.search(text)
        if not match:
            return _UNSCORED
        value = float(match.group(1))
        if match.group(2) == "%":
            value /= 100.0
        if not 0.0 <= value <= 1.0:
            return _UNSCORED
        return value

    def evaluate(self, node: ThoughtNode) -> float:
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": EVAL_PROMPT.format(
                    path=self._path_to_node(node)
                ),
            }],
        )
        node.score = self._parse_score(response)
        return node.score

    def _parse_thoughts(
        self,
        response,
        parent: ThoughtNode,
        limit: int,
    ) -> list[ThoughtNode]:
        try:
            text = first_text(response)
        except ValueError:
            return []
        children = []
        for line in text.splitlines():
            if len(children) >= max(0, limit):
                break
            line = line.replace("**", "").strip()
            if not line.startswith(("-", "*", "•")):
                continue
            content = line.lstrip("-*• ").strip()
            if not content:
                continue
            child = ThoughtNode(
                id=f"n{len(self.nodes)}",
                content=content,
                parent_id=parent.id,
            )
            self.nodes[child.id] = child
            parent.children_ids.append(child.id)
            children.append(child)
        return children

    def uct_select(
        self,
        node: ThoughtNode,
        c: float = 1.41,
    ) -> ThoughtNode | None:
        best = None
        best_uct = -float("inf")
        for child_id in node.children_ids:
            child = self.nodes[child_id]
            if child.visits == 0:
                return child
            exploit = child.total_value / child.visits
            explore = c * math.sqrt(
                math.log(max(node.visits, 1)) / child.visits
            )
            if exploit + explore > best_uct:
                best_uct = exploit + explore
                best = child
        return best

    def search(
        self,
        problem: str,
        max_depth: int = 4,
        n_iter: int = 10,
        n_branches: int = 3,
    ) -> ReasoningPath:
        root = self._create_root(problem)
        for _ in range(max(0, n_iter)):
            node = root
            while node.children_ids:
                selected = self.uct_select(node)
                if selected is None:
                    break
                node = selected
            depth = max(0, len(self._path_to_node(node)) - 1)
            if depth < max(0, max_depth):
                children = self.expand(node, n_branches)
                if children:
                    node = random.choice(children)
            score = self.evaluate(node)
            self._backpropagate(node, score)
        return self._best_path(root)

    def _create_root(self, problem: str) -> ThoughtNode:
        self.nodes.clear()
        root = ThoughtNode(id="n0", content=problem)
        self.nodes[root.id] = root
        return root

    def _path_to_node(self, node: ThoughtNode) -> ReasoningPath:
        chain = []
        current: ThoughtNode | None = node
        seen = set()
        while current is not None and current.id not in seen:
            seen.add(current.id)
            chain.append(current.content)
            current = (
                self.nodes.get(current.parent_id)
                if current.parent_id
                else None
            )
        chain.reverse()
        return ReasoningPath(chain)

    def _backpropagate(self, node: ThoughtNode, score: float) -> None:
        current: ThoughtNode | None = node
        seen = set()
        while current is not None and current.id not in seen:
            seen.add(current.id)
            current.visits += 1
            current.total_value += score
            current = (
                self.nodes.get(current.parent_id)
                if current.parent_id
                else None
            )

    def _best_path(self, root: ThoughtNode) -> ReasoningPath:
        node = root
        while node.children_ids:
            visited = [
                self.nodes[child_id]
                for child_id in node.children_ids
                if self.nodes[child_id].visits > 0
            ]
            if not visited:
                break
            node = max(
                visited,
                key=lambda child: (
                    child.visits,
                    child.total_value / child.visits,
                ),
            )
        return self._path_to_node(node)


def parse_score(response) -> float:
    """Backward-compatible public helper."""
    return ParallelReasoner._parse_score(response)
