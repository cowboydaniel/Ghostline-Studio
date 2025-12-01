"""Status bar for Ghostline Studio."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar

from ghostline.vcs.git_integration import GitIntegration


class StudioStatusBar(QStatusBar):
    def __init__(self, git: GitIntegration) -> None:
        super().__init__()
        self.git = git
        self.state_label = QLabel("IDE: Ready")
        self.state_label.setContentsMargins(0, 0, 8, 0)
        self.path_label = QLabel("")
        self.ai_label = QLabel("AI: Ready")
        self.prediction_label = QLabel("")
        self.git_label = QLabel("")
        self.addPermanentWidget(self.state_label)
        self.addPermanentWidget(self.ai_label)
        self.addPermanentWidget(self.prediction_label)
        self.addPermanentWidget(self.git_label)
        self.addPermanentWidget(self.path_label)

    def show_path(self, path: str) -> None:
        self.path_label.setText(path)

    def show_message(self, message: str) -> None:  # type: ignore[override]
        super().showMessage(message, 3000)

    def update_git(self, workspace: str | None) -> None:
        branch = self.git.branch_name(workspace) if workspace else None
        if branch:
            dirty = "*" if self.git.is_dirty(workspace) else ""
            self.git_label.setText(f"{branch}{dirty}")
        else:
            self.git_label.setText("")

    def set_ai_suggestions_available(self, available: bool) -> None:
        if available:
            # Explicitly mention "AI suggestions" so downstream checks can
            # detect when assistant recommendations are ready.
            self.ai_label.setText("AI: Ready — AI suggestions available")
        else:
            self.ai_label.setText("AI: Ready")

    def show_predicted_actions(self, actions: list[str]) -> None:
        """Render predicted actions in the status bar."""

        if actions:
            self.prediction_label.setText(f"Next: {actions[0]}")
        else:
            self.prediction_label.setText("")
