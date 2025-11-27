"""Live documentation generator using AI and the semantic index."""
from __future__ import annotations

from pathlib import Path

from ghostline.ai.ai_client import AIClient
from ghostline.semantic.query import SemanticQueryEngine


class DocGenerator:
    def __init__(self, client: AIClient, query: SemanticQueryEngine) -> None:
        self.client = client
        self.query = query
        self._demo_log: list[str] = []

    def summarise_module(self, path: Path) -> str:
        prompt = f"Summarise the following module succinctly: {path.name}"
        response = self.client.send(prompt)
        return response.text

    def describe_symbol(self, symbol: str) -> str:
        usages = self.query.find_usages(symbol)
        prompt = f"Explain the role of symbol {symbol}. References: {[n.file.name for n in usages]}"
        return self.client.send(prompt).text

    def generate_diagram(self, function: str) -> str:
        return self.query.find_cycles() and "Diagram showing cycles" or f"Sequence for {function}"

    def narrate_event(self, event: str) -> str:
        """Used by demo mode to explain ongoing actions."""

        self._demo_log.append(event)
        prompt = f"Narrate the following user events: {'; '.join(self._demo_log[-5:])}"
        return self.client.send(prompt).text

