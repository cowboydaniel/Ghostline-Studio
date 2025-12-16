from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class CreditsDialog(QDialog):
    """Lightweight dialog for the Ghostline easter egg credits."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ghostline Credits")
        self.setModal(False)

        layout = QVBoxLayout(self)

        ascii_art = (
            "      .-.'  '.-\n"
            "     ( ^      ^ )\n"
            "      )  '  '  (\n"
            "     (  (__)  )\n"
            "      '._.--._.'\n"
            "        |  |\n"
            "        |  |\n"
            "        )  (\n"
            "       /____\\\n"
        )
        layout.addWidget(QLabel(ascii_art))

        credits_text = (
            "Ghostline Studio is crafted by the Ghostline team and contributors.\n"
            "Thanks for exploring the studio—happy haunting!"
        )
        layout.addWidget(QLabel(credits_text))
