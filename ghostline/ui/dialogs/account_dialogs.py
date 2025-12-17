"""Account management dialogs for Ghostline Studio."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFormLayout,
    QWidget,
)

from ghostline.core.account import AccountStore


class SignInDialog(QDialog):
    """Dialog for signing in to Ghostline Account."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.account_store = AccountStore()
        self.setWindowTitle("Sign In to Ghostline")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Instructions
        info_label = QLabel("Sign in with your Ghostline Account")
        layout.addWidget(info_label)

        # Form
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your name")
        form.addRow("Display Name:", self.name_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@example.com")
        form.addRow("Email:", self.email_input)

        layout.addLayout(form)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        sign_in_btn = QPushButton("Sign In")
        sign_in_btn.clicked.connect(self._on_sign_in)
        button_layout.addWidget(sign_in_btn)

        layout.addLayout(button_layout)

    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    def _on_sign_in(self) -> None:
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter a display name.")
            return

        if not email:
            QMessageBox.warning(self, "Validation Error", "Please enter an email address.")
            return

        if not self._validate_email(email):
            QMessageBox.warning(
                self, "Validation Error", "Please enter a valid email address."
            )
            return

        if self.account_store.sign_in(name, email):
            QMessageBox.information(
                self, "Success", f"Welcome, {name}!\nYour account has been created."
            )
            self.accept()
        else:
            QMessageBox.warning(
                self, "Error", "Failed to sign in. Please try again."
            )


class ManageAccountDialog(QDialog):
    """Dialog for managing account information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.account_store = AccountStore()
        self.setWindowTitle("Manage Ghostline Account")
        self.setMinimumWidth(400)
        self._setup_ui()
        self._load_current_account()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Instructions
        info_label = QLabel("Update your Ghostline Account information")
        layout.addWidget(info_label)

        # Form
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your name")
        form.addRow("Display Name:", self.name_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@example.com")
        form.addRow("Email:", self.email_input)

        layout.addLayout(form)

        # Status
        signed_in_label = QLabel()
        self.signed_in_label = signed_in_label
        layout.addWidget(signed_in_label)

        # Buttons
        button_layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(save_btn)

        sign_out_btn = QPushButton("Sign Out")
        sign_out_btn.clicked.connect(self._on_sign_out)
        button_layout.addWidget(sign_out_btn)

        layout.addLayout(button_layout)

    def _load_current_account(self) -> None:
        """Load current account info into fields."""
        name = self.account_store.get_display_name()
        email = self.account_store.get_email()

        self.name_input.setText(name if name != "Guest" else "")
        self.email_input.setText(email or "")

        is_signed_in = self.account_store.is_signed_in()
        status = "Status: Signed in" if is_signed_in else "Status: Not signed in"
        self.signed_in_label.setText(status)

    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter a display name.")
            return

        if not email:
            QMessageBox.warning(self, "Validation Error", "Please enter an email address.")
            return

        if not self._validate_email(email):
            QMessageBox.warning(
                self, "Validation Error", "Please enter a valid email address."
            )
            return

        if self.account_store.update_account(name, email):
            QMessageBox.information(self, "Success", "Account information updated.")
            self.accept()
        else:
            QMessageBox.warning(
                self, "Error", "Failed to update account. Please try again."
            )

    def _on_sign_out(self) -> None:
        reply = QMessageBox.question(
            self, "Confirm Sign Out", "Are you sure you want to sign out?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.account_store.sign_out()
            QMessageBox.information(self, "Signed Out", "You have been signed out.")
            self.accept()


class AccountDetailsWindow(QDialog):
    """Window showing account details and management options."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.account_store = AccountStore()
        self.setWindowTitle("Ghostline Account")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        self._setup_ui()
        self._update_display()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Account info section
        info_layout = QFormLayout()

        self.name_label = QLabel()
        info_layout.addRow("Display Name:", self.name_label)

        self.email_label = QLabel()
        info_layout.addRow("Email:", self.email_label)

        self.status_label = QLabel()
        info_layout.addRow("Status:", self.status_label)

        layout.addLayout(info_layout)

        layout.addSpacing(20)

        # Config path
        config_path = self.account_store.get_config_path()
        path_label = QLabel(f"Account File: {config_path}")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(path_label)

        layout.addSpacing(20)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        if self.account_store.is_signed_in():
            manage_btn = QPushButton("Manage Account")
            manage_btn.clicked.connect(self._on_manage)
            button_layout.addWidget(manage_btn)

            sign_out_btn = QPushButton("Sign Out")
            sign_out_btn.clicked.connect(self._on_sign_out)
            button_layout.addWidget(sign_out_btn)
        else:
            sign_in_btn = QPushButton("Sign In")
            sign_in_btn.clicked.connect(self._on_sign_in)
            button_layout.addWidget(sign_in_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _update_display(self) -> None:
        """Update account information display."""
        name = self.account_store.get_display_name()
        email = self.account_store.get_email()
        is_signed_in = self.account_store.is_signed_in()

        self.name_label.setText(name)
        self.email_label.setText(email or "Not provided")
        self.status_label.setText("Signed in" if is_signed_in else "Not signed in")

    def _on_sign_in(self) -> None:
        dialog = SignInDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_display()
            self._setup_ui()  # Rebuild UI with new buttons

    def _on_manage(self) -> None:
        dialog = ManageAccountDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_display()
            # Refresh parent window
            if self.parent():
                self.parent().update()

    def _on_sign_out(self) -> None:
        reply = QMessageBox.question(
            self, "Confirm Sign Out", "Are you sure you want to sign out?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.account_store.sign_out()
            QMessageBox.information(self, "Signed Out", "You have been signed out.")
            self._update_display()
            self._setup_ui()  # Rebuild UI with new buttons
