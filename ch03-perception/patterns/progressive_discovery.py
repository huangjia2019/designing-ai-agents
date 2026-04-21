from typing import List, Protocol

class FileTools(Protocol):
    def exists(self, path: str) -> bool: ...
    def read(self, path: str) -> str: ...
    def glob(self, pattern: str) -> List[str]: ...
    def grep(self, query: str) -> List[str]: ...

class ProgressiveDiscovery:
    def __init__(self, tools: FileTools,
                 max_forage: int = 15,  #A
                 max_focus: int = 5,
                 max_deepen: int = 3):
        self.tools = tools
        self.limits = (max_forage, max_focus, max_deepen)

    def explore(self, task: str) -> List[str]:
        targets = self._forage(task)  #B
        contents = self._focus(targets)
        return self._deepen(contents)

    def _forage(self, task: str) -> List[str]:
        """Phase 1: Cast a wide net with cheap tools."""
        targets = []

        # Strategy 1: Read project manifests
        for m in ["CLAUDE.md", "README.md", "package.json",
                   "pyproject.toml"]:
            if self.tools.exists(m):
                targets.append(m)

        # Strategy 2: Glob for task-related files
        keywords = [w for w in task.lower().split()
                    if len(w) > 4][:3]  #C
        for kw in keywords:
            targets.extend(self.tools.glob(f"**/*{kw}*")[:5])

        # Strategy 3: Grep for content matches
        for kw in keywords:
            targets.extend(self.tools.grep(kw)[:5])

        # Deduplicate, limit
        seen = set()
        return [t for t in targets
                if not (t in seen or seen.add(t))][:self.limits[0]]

    def _focus(self,
               targets: List[str]) -> List[str]:  #D
        """Phase 2: Read high-value targets in full."""
        contents = []
        for path in targets[:self.limits[1]]:
            content = self.tools.read(path)
            contents.append(f"### {path}\n{content}")
        return contents

    def _deepen(self,
                contents: List[str]) -> List[str]:  #E
        """Phase 3: Follow imports found in focused reads."""
        import re
        for content in list(contents):
            for match in re.finditer(
                r'^(?:from|import)\s+([\w.]+)', content, re.MULTILINE
            ):
                path = match.group(1).replace(".", "/") + ".py"
                if self.tools.exists(path) and self.limits[2] > 0:
                    contents.append(f"### {path} (import)\n"
                                    f"{self.tools.read(path)}")
        return contents
