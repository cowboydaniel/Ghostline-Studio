"""AI-assisted navigation that understands user intent."""
from __future__ import annotations

from ghostline.ai.ai_client import AIClient
from ghostline.semantic.query import NavigationResult, SemanticQueryEngine


class NavigationAssistant:
    def __init__(self, client: AIClient, query: SemanticQueryEngine) -> None:
        self.client = client
        self.query = query

    def go_to_function_generating(self, concept: str) -> list[NavigationResult]:
        prompt = f"Identify the function that generates {concept}. Respond with candidate names."
        response = self.client.send(prompt)
        candidates = response.text.splitlines()
        results: list[NavigationResult] = []
        for candidate in candidates:
            results.extend(self.query.find_related_functions(candidate.strip()))
        return results

    def find_module_handling(self, topic: str) -> list[NavigationResult]:
        prompt = f"Which module is responsible for {topic}?"
        response = self.client.send(prompt)
        modules = response.text.split()
        results: list[NavigationResult] = []
        for module in modules:
            for node in self.query.search_by_kind("module"):
                if module.lower() in node.name.lower():
                    results.append(NavigationResult(f"Module {node.name}", node))
        return results

    def jump_to_error_construction(self) -> list[NavigationResult]:
        results: list[NavigationResult] = []
        for node in self.query.search_by_kind("function"):
            if "error" in node.name.lower():
                results.append(NavigationResult(f"Error factory {node.name}", node))
        return results

