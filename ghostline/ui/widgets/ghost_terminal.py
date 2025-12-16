from __future__ import annotations

import random
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget


class GhostTerminalWidget(QWidget):
    """A lightweight typing mini-game shown from the Help menu."""

    def __init__(self, parent: QWidget | None = None, prompts: List[str] | None = None) -> None:
        super().__init__(parent)
        self._prompts = prompts or [
            "shadow packet",
            "midnight deploy",
            "ghostline ready",
            "type until dawn",
            "silent commit",
            "phantom refactor",
            "stealth build",
            "trace the signal",
            "echoes in code",
        ]
        self._score = 0
        self._current_prompt = ""

        self._title_label = QLabel("Ghost Terminal")
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setProperty("class", "h3")

        self._prompt_label = QLabel()
        self._prompt_label.setAlignment(Qt.AlignCenter)
        self._prompt_label.setWordWrap(True)

        self._status_label = QLabel("Type the prompt exactly and press Enter to score.")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)

        self._score_label = QLabel()
        self._score_label.setAlignment(Qt.AlignCenter)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Start typing...")
        self._input.returnPressed.connect(self._check_entry)

        self._reset_button = QPushButton("Reset Game")
        self._reset_button.clicked.connect(self.reset_game)

        self._new_prompt_button = QPushButton("New Prompt")
        self._new_prompt_button.clicked.connect(self._next_prompt)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._reset_button)
        button_row.addWidget(self._new_prompt_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title_label)
        layout.addWidget(self._prompt_label)
        layout.addWidget(self._score_label)
        layout.addWidget(self._status_label)
        layout.addWidget(self._input)
        layout.addLayout(button_row)
        layout.addStretch(1)

        self.reset_game()

    def reset_game(self) -> None:
        """Reset the game so it can be replayed without restarting."""

        self._score = 0
        self._update_score()
        self._status_label.setText("Type the prompt exactly and press Enter to score.")
        self._input.clear()
        self._next_prompt()
        self._input.setFocus(Qt.OtherFocusReason)

    def _check_entry(self) -> None:
        if not self._current_prompt:
            self._next_prompt()
            return

        attempt = self._input.text().strip()
        if attempt == self._current_prompt:
            self._score += 1
            self._status_label.setText("Correct! A new prompt awaits.")
            self._update_score()
            self._input.clear()
            self._next_prompt()
        else:
            self._status_label.setText("Close! Keep typing to match the prompt.")

    def _next_prompt(self) -> None:
        self._current_prompt = random.choice(self._prompts)
        self._prompt_label.setText(f"Prompt: <b>{self._current_prompt}</b>")

    def _update_score(self) -> None:
        self._score_label.setText(f"Score: {self._score}")
