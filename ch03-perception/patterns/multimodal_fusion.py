from dataclasses import dataclass
from enum import Enum
from typing import List, Union

class Modality(Enum):
    TEXT = "text"
    IMAGE = "image"
    STRUCTURED = "structured"

@dataclass
class ModalInput:
    modality: Modality
    content: Union[str, bytes]
    description: str
    token_estimate: int

@dataclass
class FusedContext:
    text_parts: List[str]
    image_refs: List[bytes]
    total_tokens: int
    decisions: List[str]  #A

class MultiModalFusion:
    def fuse(self, inputs: List[ModalInput]) -> FusedContext:
        text_parts, image_refs, decisions = [], [], []
        total = 0

        for inp in inputs:
            if inp.modality == Modality.TEXT:
                text_parts.append(inp.content)  #B
                total += inp.token_estimate
                decisions.append(
                    f"{inp.description}: text passthrough")

            elif inp.modality == Modality.STRUCTURED:
                compact = self._to_compact_table(inp.content)
                text_parts.append(compact)  #C
                total += len(compact) // 4
                decisions.append(
                    f"{inp.description}: structured to table")

            elif inp.modality == Modality.IMAGE:
                if self._needs_spatial(inp.description):
                    image_refs.append(inp.content)  #D
                    total += inp.token_estimate
                    decisions.append(
                        f"{inp.description}: spatial, keep image")
                else:
                    text_parts.append(f"[{inp.description}]")
                    total += 50
                    decisions.append(
                        f"{inp.description}: no spatial, text")

        return FusedContext(text_parts, image_refs, total, decisions)

    def _needs_spatial(self, desc: str) -> bool:
        spatial = ["layout", "screenshot", "diagram", "UI",
                   "wireframe", "position", "alignment"]
        return any(kw in desc.lower()
                   for kw in spatial)  #E

    def _to_compact_table(self, data) -> str:
        # Convert JSON/CSV to a compact markdown table
        ...
