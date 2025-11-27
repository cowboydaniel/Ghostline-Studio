"""Prompt builder that merges multiple context sources."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ghostline.ai.workspace_memory import WorkspaceMemory
from ghostline.semantic.graph import SemanticGraph


@dataclass
class PromptSegments:
    semantic: str = ""
    memory: str = ""
    ast: str = ""
    last_response: str = ""

    def merge(self) -> str:
        blocks = [self.semantic, self.memory, self.ast, self.last_response]
        return "\n\n".join([block for block in blocks if block])


class PromptBuilder:
    """Merges semantic graph, workspace memory, and previous responses."""

    def __init__(self, memory: WorkspaceMemory | None = None, graph: SemanticGraph | None = None) -> None:
        self.memory = memory
        self.graph = graph
        self.last_ai_response: str = ""

    def build(self, user_prompt: str, mode: str = "sequential") -> str:
        segments = PromptSegments(
            semantic=self._semantic_block(),
            memory=self.memory.as_prompt_context() if self.memory else "",
            ast="(AST fragments omitted in stub)",
            last_response=self.last_ai_response,
        )
        if mode == "parallel":
            return f"[PARALLEL]\n{segments.merge()}\n\nUser: {user_prompt}"
        if mode == "cascade":
            return f"[CASCADE]\n{segments.memory}\n{segments.semantic}\nUser: {user_prompt}"
        return f"{segments.merge()}\n\nUser: {user_prompt}"

    def build_autoflow_prompt(self, intent: str, steps: list[str]) -> str:
        """Specialised builder for autoflow predictions."""

        semantic = self._semantic_block()
        memory = self.memory.as_prompt_context() if self.memory else ""
        chain = "\n".join(f"- {step}" for step in steps)
        return f"Autoflow intent: {intent}\n{semantic}\n{memory}\nPlanned chain:\n{chain}"

    def update_last_response(self, text: str) -> None:
        self.last_ai_response = text

    def _semantic_block(self) -> str:
        if not self.graph:
            return ""
        return f"Semantic graph fingerprint:\n{self.graph.pattern_fingerprint()}"
