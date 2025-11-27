"""AI-assisted navigation that understands user intent."""
from __future__ import annotations

from dataclasses import dataclass

from ghostline.ai.ai_client import AIClient
from ghostline.semantic.query import NavigationResult, SemanticQueryEngine


@dataclass
class PredictiveContext:
    """Signals about current user focus for predictive actions."""

    cursor_symbol: str | None = None
    recent_files: list[str] | None = None
    workflow_history: list[str] | None = None


@dataclass
class PredictedAction:
    label: str
    action: str


class NavigationAssistant:
    def __init__(self, client: AIClient, query: SemanticQueryEngine) -> None:
        self.client = client
        self.query = query
        self.autoflow_enabled = False

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

    def predict_actions(self, context: PredictiveContext) -> list[PredictedAction]:
        """Return predicted next steps based on user context."""

        predictions: list[PredictedAction] = []
        if context.cursor_symbol:
            predictions.append(
                PredictedAction(
                    label=f"Generate missing tests for {context.cursor_symbol}",
                    action="run related tests",
                )
            )
            predictions.append(
                PredictedAction(
                    label=f"Open module for {context.cursor_symbol}",
                    action="open referenced modules",
                )
            )
        if context.recent_files:
            last = context.recent_files[-1]
            predictions.append(
                PredictedAction(
                    label=f"Refactor related to {last}",
                    action="apply related refactors",
                )
            )
        if context.workflow_history:
            if any("debug" in step for step in context.workflow_history):
                predictions.append(
                    PredictedAction(
                        label="Watch failing variables",
                        action="propose watchpoints",
                    )
                )
        return predictions

    def autoflow(self, context: PredictiveContext) -> list[PredictedAction]:
        """Chain predicted actions into an ordered workflow."""

        actions = self.predict_actions(context)
        if context.cursor_symbol:
            actions.append(
                PredictedAction(
                    label=f"Run pipeline for {context.cursor_symbol}",
                    action="trigger pipeline",
                )
            )
        if self.autoflow_enabled:
            actions.append(PredictedAction(label="Apply smart refactor", action="run refactor agent"))
        return actions

