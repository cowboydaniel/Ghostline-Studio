"""Local account management for Ghostline Studio."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ghostline.core.config import CONFIG_DIR

logger = logging.getLogger(__name__)

ACCOUNT_FILE = CONFIG_DIR / "account.json"


class AccountStore:
    """Manages local user account information."""

    DEFAULT_ACCOUNT = {
        "display_name": "Guest",
        "email": None,
        "signed_in": False,
        "created_at": None,
    }

    def __init__(self) -> None:
        self._account = self._load_account()

    def _load_account(self) -> dict[str, Any]:
        """Load account from persistent storage."""
        if not ACCOUNT_FILE.exists():
            return dict(self.DEFAULT_ACCOUNT)
        try:
            with ACCOUNT_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all required fields exist
                for key, value in self.DEFAULT_ACCOUNT.items():
                    if key not in data:
                        data[key] = value
                return data
        except Exception as e:
            logger.warning(f"Failed to load account: {e}, using defaults")
            return dict(self.DEFAULT_ACCOUNT)

    def save(self) -> None:
        """Save account to persistent storage."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with ACCOUNT_FILE.open("w", encoding="utf-8") as f:
                json.dump(self._account, f, indent=2)
            logger.debug(f"Account saved to {ACCOUNT_FILE}")
        except Exception as e:
            logger.error(f"Failed to save account: {e}")

    def sign_in(self, display_name: str, email: str) -> bool:
        """Sign in with display name and email.

        Args:
            display_name: User's display name
            email: User's email address

        Returns:
            True if sign-in was successful
        """
        if not display_name.strip() or not email.strip():
            return False

        self._account["display_name"] = display_name.strip()
        self._account["email"] = email.strip()
        self._account["signed_in"] = True
        if not self._account["created_at"]:
            self._account["created_at"] = datetime.now().isoformat()

        self.save()
        logger.info(f"User signed in: {display_name}")
        return True

    def sign_out(self) -> None:
        """Sign out current user."""
        self._account["email"] = None
        self._account["display_name"] = "Guest"
        self._account["signed_in"] = False
        self.save()
        logger.info("User signed out")

    def update_account(self, display_name: str, email: str) -> bool:
        """Update existing account information.

        Args:
            display_name: New display name
            email: New email address

        Returns:
            True if update was successful
        """
        if not display_name.strip() or not email.strip():
            return False

        self._account["display_name"] = display_name.strip()
        self._account["email"] = email.strip()
        self.save()
        logger.info(f"Account updated: {display_name}")
        return True

    def get_display_name(self) -> str:
        """Get current display name."""
        return self._account.get("display_name", "Guest")

    def get_email(self) -> str | None:
        """Get current email."""
        return self._account.get("email")

    def is_signed_in(self) -> bool:
        """Check if user is signed in."""
        return self._account.get("signed_in", False)

    def get_account_info(self) -> dict[str, Any]:
        """Get full account info."""
        return dict(self._account)

    def get_config_path(self) -> Path:
        """Get the account config file path."""
        return ACCOUNT_FILE
