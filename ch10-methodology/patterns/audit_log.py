"""Audit Log — append-only, tamper-evident record of every decision.

Required by §9 Governance: every guardrail decision, every trust update,
every tool invocation must be queryable for after-the-fact analysis.
Hash chain on each entry makes silent tampering detectable.
"""
import hashlib, json, time
from dataclasses import dataclass, field, asdict


@dataclass
class AuditEntry:
    timestamp: float
    actor: str
    action: str
    decision: str
    payload: dict = field(default_factory=dict)
    prev_hash: str = ""
    self_hash: str = ""

    def compute_hash(self) -> str:
        material = json.dumps(
            {k: v for k, v in asdict(self).items() if k != "self_hash"},
            sort_keys=True, default=str,
        )
        return hashlib.sha256(material.encode()).hexdigest()[:16]


class AuditLog:
    """Append-only audit log with hash chain. In production: persist + replicate."""

    def __init__(self):
        self.entries: list[AuditEntry] = []

    def record(self, actor: str, action: str, decision: str,
               **payload) -> AuditEntry:
        prev_hash = self.entries[-1].self_hash if self.entries else "GENESIS"
        entry = AuditEntry(
            timestamp=time.time(),
            actor=actor, action=action, decision=decision,
            payload=payload,
            prev_hash=prev_hash,
        )
        entry.self_hash = entry.compute_hash()
        self.entries.append(entry)
        return entry

    def verify_chain(self) -> tuple[bool, int]:
        """Walk the log, re-compute hashes, detect tampering."""
        prev = "GENESIS"
        for i, entry in enumerate(self.entries):
            if entry.prev_hash != prev:
                return False, i
            if entry.compute_hash() != entry.self_hash:
                return False, i
            prev = entry.self_hash
        return True, len(self.entries)
