"""Status bar for Ghostline Studio."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar

from ghostline.vcs.git_integration import GitIntegration


class StudioStatusBar(QStatusBar):
    def __init__(self, git: GitIntegration) -> None:
        super().__init__()
        self.git = git
        self.path_label = QLabel("Ready")
        self.ai_label = QLabel("")
        self.git_label = QLabel("")
        self.addPermanentWidget(self.ai_label)
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
            self.ai_label.setText("AI suggestions ready")
        else:
            self.ai_label.setText("")
