"""
Chat history persistence manager.

Handles saving and loading chat sessions to/from disk using JSON files.
Follows the WorkspaceMemory pattern for consistency with existing storage.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ghostline.ai.ai_chat_panel import ChatMessage, ChatSession
    from ghostline.ai.context_engine import ContextChunk


class ChatHistoryManager:
    """Manages persistent storage of chat history."""

    def __init__(self, storage_dir: Path | None = None):
        """
        Initialize the chat history manager.

        Args:
            storage_dir: Directory to store chat history files.
                        If None, uses ~/.config/ghostline/chat_history/
        """
        if storage_dir is None:
            from ghostline.core.config import CONFIG_DIR
            storage_dir = CONFIG_DIR / "chat_history"

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.storage_dir / "index.json"

        # In-memory index: {session_id: metadata}
        self._index: dict[str, dict] = self._load_index()

    def _load_index(self) -> dict[str, dict]:
        """Load the session index from disk."""
        if not self.index_path.exists():
            return {}

        try:
            content = self.index_path.read_text(encoding="utf-8")
            return json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Failed to load chat history index: {e}")
            return {}

    def _save_index(self) -> None:
        """Save the session index to disk."""
        try:
            self.index_path.write_text(
                json.dumps(self._index, indent=2, default=str),
                encoding="utf-8"
            )
        except OSError as e:
            print(f"Warning: Failed to save chat history index: {e}")

    def _session_to_dict(self, session: ChatSession) -> dict:
        """Convert a ChatSession to a JSON-serializable dict."""
        def message_to_dict(msg) -> dict:
            result = {
                "role": msg.role,
                "text": msg.text,
            }
            if msg.context:
                result["context"] = [
                    {
                        "title": chunk.title,
                        "text": chunk.text,
                        "path": str(chunk.path) if chunk.path else None,
                        "reason": chunk.reason,
                    }
                    for chunk in msg.context
                ]
            else:
                result["context"] = None
            return result

        return {
            "title": session.title,
            "messages": [message_to_dict(msg) for msg in session.messages],
            "created_at": session.created_at.isoformat(),
        }

    def _dict_to_session(self, data: dict):
        """
        Convert a dict back to a ChatSession.

        Note: This returns a dict-like object that can be used to construct
        the actual ChatSession/ChatMessage/ContextChunk instances in the caller.
        We avoid importing here to prevent circular dependencies and PySide6 requirements.
        """
        # Import the actual classes only when they're available
        # This allows the manager to work in both production and test environments
        try:
            from ghostline.ai.ai_chat_panel import ChatMessage, ChatSession
            from ghostline.ai.context_engine import ContextChunk
            classes_available = True
        except ImportError:
            classes_available = False
            # Fallback: create simple dataclass-like objects
            from dataclasses import dataclass

            @dataclass
            class ContextChunk:  # type: ignore
                title: str
                text: str
                path: Path | None = None
                reason: str | None = None

            @dataclass
            class ChatMessage:  # type: ignore
                role: str
                text: str
                context: list | None = None

            @dataclass
            class ChatSession:  # type: ignore
                title: str
                messages: list
                created_at: datetime

        def dict_to_message(msg_data: dict):
            context = None
            if msg_data.get("context"):
                context = [
                    ContextChunk(
                        title=chunk["title"],
                        text=chunk["text"],
                        path=Path(chunk["path"]) if chunk["path"] else None,
                        reason=chunk["reason"],
                    )
                    for chunk in msg_data["context"]
                ]

            return ChatMessage(
                role=msg_data["role"],
                text=msg_data["text"],
                context=context,
            )

        return ChatSession(
            title=data["title"],
            messages=[dict_to_message(msg) for msg in data["messages"]],
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def save_session(self, session: ChatSession, session_id: str | None = None) -> str:
        """
        Save a chat session to disk.

        Args:
            session: The ChatSession to save
            session_id: Optional session ID. If None, generates a new UUID.

        Returns:
            The session ID used for storage
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        # Save session data
        session_path = self.storage_dir / f"{session_id}.json"
        session_data = self._session_to_dict(session)

        try:
            session_path.write_text(
                json.dumps(session_data, indent=2, default=str),
                encoding="utf-8"
            )
        except OSError as e:
            print(f"Warning: Failed to save chat session {session_id}: {e}")
            return session_id

        # Update index
        self._index[session_id] = {
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "message_count": len(session.messages),
            "file": f"{session_id}.json",
        }
        self._save_index()

        return session_id

    def load_session(self, session_id: str) -> ChatSession | None:
        """
        Load a chat session from disk.

        Args:
            session_id: The ID of the session to load

        Returns:
            The ChatSession, or None if not found or failed to load
        """
        session_path = self.storage_dir / f"{session_id}.json"

        if not session_path.exists():
            return None

        try:
            content = session_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return self._dict_to_session(data)
        except (json.JSONDecodeError, OSError, KeyError) as e:
            print(f"Warning: Failed to load chat session {session_id}: {e}")
            return None

    def load_all_sessions(self) -> list[tuple[str, ChatSession]]:
        """
        Load all chat sessions from disk.

        Returns:
            List of (session_id, ChatSession) tuples, sorted by created_at (newest first)
        """
        sessions = []

        for session_id in self._index.keys():
            session = self.load_session(session_id)
            if session:
                sessions.append((session_id, session))

        # Sort by created_at, newest first
        sessions.sort(key=lambda x: x[1].created_at, reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a chat session from disk.

        Args:
            session_id: The ID of the session to delete

        Returns:
            True if successfully deleted, False otherwise
        """
        session_path = self.storage_dir / f"{session_id}.json"

        # Remove from index
        if session_id in self._index:
            del self._index[session_id]
            self._save_index()

        # Remove file
        try:
            if session_path.exists():
                session_path.unlink()
            return True
        except OSError as e:
            print(f"Warning: Failed to delete chat session {session_id}: {e}")
            return False

    def get_all_session_ids(self) -> list[str]:
        """Get all session IDs, sorted by created_at (newest first)."""
        sessions = sorted(
            self._index.items(),
            key=lambda x: x[1]["created_at"],
            reverse=True
        )
        return [session_id for session_id, _ in sessions]

    def clear_all(self) -> None:
        """Delete all chat sessions. Use with caution!"""
        for session_id in list(self._index.keys()):
            self.delete_session(session_id)

    def get_storage_path(self) -> Path:
        """Get the storage directory path."""
        return self.storage_dir
