import math
import random
import re
from dataclasses import dataclass, field
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]

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
unfinished by design — judge the direction it is heading,
not whether it has arrived. Reserve scores above 0.90 for
paths whose remaining steps you could name.

Reply in exactly this format:
SCORE: <a number between 0.00 and 1.00>
WHY: <one sentence>
"""

class ReasoningPath(list):
    """A root-to-node chain: counts like a list, reads
    like a prompt.

    expand() and evaluate() drop this straight into a
    prompt with {path}, while search() measures depth with
    len(path). A plain list would satisfy the second and
    render as a bracketed repr in the first. Holding the
    rendering here lets both call sites stay as they are.
    """

    def __str__(self) -> str:
        if not self:
            return "(nothing yet)"
        problem, *thoughts = self
        lines = [f"Problem: {problem}"]
        lines += [f"Step {i}: {t}"
                  for i, t in enumerate(thoughts, 1)]
        return "\n".join(lines)


@dataclass
class ThoughtNode:
    id: str
    content: str
    parent_id: str | None = None
    children_ids: list[str] = field(
        default_factory=list)
    score: float = 0.0  #A
    visits: int = 0
    total_value: float = 0.0

class ParallelReasoner:
    def __init__(self, client: Anthropic):
        self.client = client
        self.nodes: dict[str, ThoughtNode] = {}

    def expand(self, node: ThoughtNode,  #B
               n_branches: int = 3):
        path = self._path_to_node(node)
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user",
                "content": EXPAND_PROMPT.format(
                    path=path, n=n_branches)}],
        )
        return self._parse_thoughts(
            response, node)

    def evaluate(self, node):  #C
        path = self._path_to_node(node)
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{"role": "user",
                "content": EVAL_PROMPT.format(
                    path=path)}],
        )
        node.score = parse_score(response)
        return node.score

    def uct_select(self, node,  #D
                   c: float = 1.41):
        best = None
        best_uct = -float("inf")
        for cid in node.children_ids:
            child = self.nodes[cid]
            if child.visits == 0:
                return child
            exploit = (child.total_value
                       / child.visits)
            explore = c * math.sqrt(
                math.log(node.visits)
                / child.visits)
            if exploit + explore > best_uct:
                best_uct = exploit + explore
                best = child
        return best

    def search(self, problem: str,  #E
               max_depth=4, n_iter=10):
        root = self._create_root(problem)
        for _ in range(n_iter):
            node = root
            while node.children_ids:
                node = self.uct_select(node)
            depth = len(self._path_to_node(node))
            if depth < max_depth:
                children = self.expand(node)
                node = (random.choice(children)
                        if children else node)
            score = self.evaluate(node)
            self._backpropagate(node, score)  #F
        return self._best_path(root)

    # --- engine behind the search above -----------------
    # Listings 5.4 and 5.4b print the four MCTS phases;
    # these are the methods they call. Kept below the
    # listing boundary so the search above still reads as
    # it does in the book.

    def _create_root(self, problem: str) -> ThoughtNode:
        """Seed a fresh tree with the problem statement.

        Clearing first makes a second search() independent
        of the first: stale nodes would otherwise keep
        their visit counts and skew UCT from the start.
        """
        self.nodes.clear()
        root = ThoughtNode(id="n0", content=problem)
        self.nodes[root.id] = root
        return root

    def _path_to_node(self, node: ThoughtNode
                      ) -> ReasoningPath:
        """Contents from the root down to node, root first."""
        chain = []
        current = node
        seen = set()
        while current is not None and current.id not in seen:
            seen.add(current.id)  # a cycle would hang
            chain.append(current.content)
            current = (self.nodes.get(current.parent_id)
                       if current.parent_id else None)
        chain.reverse()
        return ReasoningPath(chain)

    def _parse_thoughts(self, response,
                        parent: ThoughtNode
                        ) -> list[ThoughtNode]:
        """Register one child per "- " line of the reply.

        A reply with no readable branches returns [], which
        search() reads as "no expansion" and falls back to
        evaluating the parent. A barren node stops growing
        instead of taking the whole search down with it.
        """
        children = []
        for line in _first_text(response).splitlines():
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

    def _backpropagate(self, node: ThoughtNode,
                       score: float) -> None:
        """Credit node and every ancestor with this result.

        Each ancestor's visit count therefore covers all
        the visits below it, which is the invariant
        uct_select's math.log(node.visits) rests on.
        """
        current = node
        seen = set()
        while current is not None and current.id not in seen:
            seen.add(current.id)
            current.visits += 1
            current.total_value += score
            current = (self.nodes.get(current.parent_id)
                       if current.parent_id else None)

    def _best_path(self, root: ThoughtNode
                   ) -> ReasoningPath:
        """Follow the most-visited child at each level.

        Visits, not score: a high score from one visit is a
        lucky sample, while a high visit count means UCT
        kept choosing that branch against competition.
        """
        node = root
        while node.children_ids:
            visited = [self.nodes[cid]
                       for cid in node.children_ids
                       if self.nodes[cid].visits > 0]
            if not visited:
                break
            node = max(visited, key=lambda c: c.visits)
        return self._path_to_node(node)


# --- parser behind evaluate above -----------------------
# Listing 5.4 prints the call to parse_score(); this is the
# function it calls.

# An unreadable score is no information. Scoring it 0.0
# would tell the search that the evaluator's silence is
# evidence against the branch, and UCT would prune a path
# nobody actually judged.
_UNSCORED = 0.5

_SCORE_RE = re.compile(
    r"score\s*[:=]\s*([0-9]*\.?[0-9]+)\s*(%?)", re.I)
_BARE_RE = re.compile(r"([0-9]*\.?[0-9]+)\s*(%?)")


def _first_text(response) -> str:
    """The reply's first text block, or "" if it has none."""
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) in (None, "text"):
            text = getattr(block, "text", None)
            if isinstance(text, str):
                return text
    return ""


def parse_score(response) -> float:
    """Read SCORE: out of an evaluator's reply.

    Takes the response rather than its text because that is
    how evaluate() calls it. A bare number is accepted only
    when it is the entire reply: hunting for the first float
    inside prose would read "3 steps from done" as 0.03.

    A score outside 0.00-1.00 without a percent sign is off
    contract on an unknowable scale, so it reads as no score
    rather than as a guess. Clamping "SCORE: 85" to 1.00
    would hand the search a near-perfect branch on the
    strength of a formatting slip.
    """
    text = _first_text(response).strip()
    match = _SCORE_RE.search(text) or _BARE_RE.fullmatch(text)
    if not match:
        return _UNSCORED
    value = float(match.group(1))
    if match.group(2) == "%":
        value /= 100.0
    if not 0.0 <= value <= 1.0:
        return _UNSCORED
    return value
