import os, re, logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("argus.perception")

@dataclass
class FileContext:
    path: str
    content: str
    relevance: str       # "modified", "imported", "test", "config"    #A
    tokens: int = 0

    def __post_init__(self):
        if self.tokens == 0:
            self.tokens = len(self.content) // 4                       #B

@dataclass
class PerceptionTrace:
    """Observable record of perception decisions."""
    files_discovered: int = 0
    files_selected: int = 0
    files_dropped: int = 0
    tokens_considered: int = 0
    tokens_selected: int = 0
    dropped_files: list = field(default_factory=list)

    @property
    def selectivity(self) -> float:
        if self.tokens_considered == 0: return 0
        return self.tokens_selected / self.tokens_considered           #C

def gather_review_context(
    diff: str,
    repo_root: str,
    budget: int = 50_000,                                              #A
) -> tuple[list[FileContext], PerceptionTrace]:
    contexts: list[FileContext] = []
    trace = PerceptionTrace()

    # Step 1: Modified files (always included)
    modified = _extract_modified_files(diff)                           #B
    for fpath in modified:
        full = os.path.join(repo_root, fpath)
        if os.path.exists(full):
            content = Path(full).read_text(errors="ignore")
            contexts.append(FileContext(fpath, content, "modified"))

    # Step 2: Follow imports from modified files
    for ctx in list(contexts):
        if ctx.path.endswith(".py"):
            for imp in _find_imports(ctx.content):
                imp_path = os.path.join(repo_root, imp)
                if os.path.exists(imp_path) and imp not in modified:
                    content = Path(imp_path).read_text(errors="ignore")
                    contexts.append(FileContext(imp, content, "imported"))  #C

    # Step 3: Find test files for modified modules
    for test in _find_test_files(modified, repo_root):
        if test not in [c.path for c in contexts]:
            full = os.path.join(repo_root, test)
            if os.path.exists(full):
                content = Path(full).read_text(errors="ignore")
                contexts.append(FileContext(test, content, "test"))    #A

    # Step 4: Load project configuration
    for cfg in ["pyproject.toml", "setup.cfg", ".flake8"]:            #B
        cfg_path = os.path.join(repo_root, cfg)
        if os.path.exists(cfg_path):
            content = Path(cfg_path).read_text(errors="ignore")
            contexts.append(FileContext(cfg, content, "config"))       #C

    # Triage: sort by priority, fill greedily
    priority_order = {"modified": 0, "imported": 1, "test": 1, "config": 2}  #A
    contexts.sort(key=lambda c: priority_order.get(c.relevance, 3))

    trace.files_discovered = len(contexts)
    trace.tokens_considered = sum(c.tokens for c in contexts)

    selected, used = [], 0
    for ctx in contexts:
        if used + ctx.tokens <= budget:
            selected.append(ctx)
            used += ctx.tokens
        else:
            trace.dropped_files.append((ctx.path, ctx.relevance))     #B

    trace.files_selected = len(selected)
    trace.files_dropped = trace.files_discovered - trace.files_selected
    trace.tokens_selected = used
    logger.info(
        "Perception: %d/%d files selected (%.0f%% selectivity), "
        "%d tokens used of %d budget",
        trace.files_selected, trace.files_discovered,
        trace.selectivity * 100, used, budget,
    )
    if trace.dropped_files:
        logger.warning("Dropped: %s", trace.dropped_files)            #C

    return selected, trace

def _extract_modified_files(diff: str) -> list[str]:
    return re.findall(r'^(?:\+\+\+|---) [ab]/(.+)$', diff, re.MULTILINE)  #A

def _find_imports(source: str) -> list[str]:
    imports = []
    for m in re.finditer(
            r'^(?:from|import)\s+([\w.]+)',
            source, re.MULTILINE):
        path = m.group(1).replace(".", "/") + ".py"                    #B
        imports.append(path)
    return imports

def _find_test_files(modified: list[str], repo_root: str) -> list[str]:
    tests = []
    for fpath in modified:
        name = Path(fpath).stem
        candidates = [
            f"tests/test_{name}.py",
            f"test/test_{name}.py",
            f"{Path(fpath).parent}/test_{name}.py",                    #C
        ]
        for c in candidates:
            if os.path.exists(os.path.join(repo_root, c)):
                tests.append(c)
    return tests
