import math
import random
from dataclasses import dataclass, field
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]

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
