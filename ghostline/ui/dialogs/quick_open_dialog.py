from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class QuickOpenDialog(QDialog):
    """Lightweight Ctrl+P quick-open dialog with fuzzy matching."""

    fileSelected = Signal(Path)

    def __init__(self, files: Iterable[Path], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Open")
        self.resize(600, 420)
        self._all_files: list[Path] = list(dict.fromkeys(files))
        self.selected: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        input_row = QHBoxLayout()
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Type a filename or path...")
        self.search.textChanged.connect(self._update_results)
        self.search.returnPressed.connect(self._activate_current)
        input_row.addWidget(self.search)

        self.go_to_line_btn = QPushButton("Go to Line", self)
        self.go_to_line_btn.clicked.connect(self._trigger_goto_line)
        input_row.addWidget(self.go_to_line_btn)
        layout.addLayout(input_row)

        self.list = QListWidget(self)
        self.list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self.list)

        self._update_results()

    def _trigger_goto_line(self) -> None:
        self.selected = None
        self.accept()

    def _activate_current(self) -> None:
        current = self.list.currentItem()
        if current:
            self._on_item_activated(current)
        else:
            self._trigger_goto_line()

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if isinstance(path, Path):
            self.selected = path
            self.fileSelected.emit(path)
            self.accept()

    def _update_results(self) -> None:
        query = self.search.text().strip()
        self.list.clear()
        matches = self._filter(query) if query else list(self._all_files)
        for path in matches[:200]:
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.UserRole, path)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _filter(self, query: str) -> list[Path]:
        query_lower = query.lower()
        results: list[tuple[int, Path]] = []
        for path in self._all_files:
            name = path.name.lower()
            full = str(path).lower()
            score = self._fuzzy_score(name, query_lower)
            if score is None:
                score = self._fuzzy_score(full, query_lower)
                if score is None:
                    continue
                score += 50  # prefer filename matches first
            results.append((score, path))
        results.sort(key=lambda item: (item[0], len(item[1].name)))
        return [path for _, path in results]

    def _fuzzy_score(self, text: str, query: str) -> int | None:
        pos = -1
        score = 0
        for char in query:
            pos = text.find(char, pos + 1)
            if pos == -1:
                return None
            score += pos
        return score
