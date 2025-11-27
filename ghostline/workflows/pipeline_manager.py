"""Manage autonomous pipelines triggered by workspace events."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

from ghostline.agents.agent_manager import AgentManager

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    kind: str
    args: dict[str, str] = field(default_factory=dict)


@dataclass
class PipelineDefinition:
    name: str
    triggers: list[str]
    steps: list[PipelineStep]
    enabled: bool = True
    last_run: datetime | None = None

    def should_run_on(self, event: str) -> bool:
        return self.enabled and event in self.triggers


class PipelineManager:
    """Load, schedule, and execute autonomous pipelines."""

    def __init__(self, config_path: Path, agent_manager: AgentManager) -> None:
        self.config_path = config_path
        self.agent_manager = agent_manager
        self.pipelines: list[PipelineDefinition] = []
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            return
        try:
            import yaml

            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
            for entry in raw.get("pipelines", []):
                steps = [PipelineStep(step.get("kind", "task"), step.get("args", {})) for step in entry.get("steps", [])]
                definition = PipelineDefinition(
                    name=entry.get("name", "pipeline"),
                    triggers=entry.get("triggers", []),
                    steps=steps,
                    enabled=bool(entry.get("enabled", True)),
                )
                self.pipelines.append(definition)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load pipeline configuration")

    def handle_event(self, event: str) -> list[str]:
        """Trigger pipelines based on filesystem or scheduler events."""

        triggered: list[str] = []
        for pipeline in self.pipelines:
            if pipeline.should_run_on(event):
                triggered.append(pipeline.name)
                self.run_pipeline(pipeline)
        return triggered

    def run_pipeline(self, pipeline: PipelineDefinition) -> None:
        logger.info("Running pipeline %s", pipeline.name)
        for step in pipeline.steps:
            self._execute_step(step)
        pipeline.last_run = datetime.utcnow()

    def _execute_step(self, step: PipelineStep) -> None:
        kind = step.kind
        if kind == "run agents":
            self.agent_manager.coordinate(step.args.get("task", "pipeline run"))
        elif kind == "run tests":
            logger.info("[pipeline] would run tests for %s", step.args)
        elif kind == "run formatter":
            logger.info("[pipeline] formatter scheduled")
        elif kind == "apply refactors":
            self.agent_manager.propose_plan(step.args.get("hint", "auto-refactor"))
        elif kind == "maintenance sweep":
            logger.info("[pipeline] maintenance sweep placeholder")
        else:
            logger.info("[pipeline] custom step %s", kind)

    def register_pipeline(self, definition: PipelineDefinition) -> None:
        self.pipelines.append(definition)

    def upcoming(self) -> list[str]:
        return [f"{pipeline.name} (enabled={pipeline.enabled})" for pipeline in self.pipelines]

    def scheduled_runs(self, now: datetime | None = None) -> list[str]:
        now = now or datetime.utcnow()
        names: list[str] = []
        for pipeline in self.pipelines:
            if pipeline.last_run and now - pipeline.last_run > timedelta(hours=1):
                names.append(pipeline.name)
        return names
