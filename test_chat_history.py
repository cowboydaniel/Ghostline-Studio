#!/usr/bin/env python3
"""
Integration test for chat history persistence.
Tests the ChatHistoryManager integration with ChatSession and ChatMessage.
"""

import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Add the project to the path
sys.path.insert(0, str(Path(__file__).parent))

from ghostline.ai.chat_history_manager import ChatHistoryManager

# Define minimal dataclasses for testing (to avoid PySide6 dependency)
@dataclass
class ContextChunk:
    title: str
    text: str
    path: Path | None = None
    reason: str | None = None

@dataclass
class ChatMessage:
    role: str
    text: str
    context: list[ContextChunk] | None = None

@dataclass
class ChatSession:
    title: str
    messages: list[ChatMessage]
    created_at: datetime


def test_chat_history_persistence():
    """Test that chat history can be saved and loaded correctly."""
    print("Testing chat history persistence...")

    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_dir = Path(temp_dir) / "chat_history"
        manager = ChatHistoryManager(storage_dir)

        # Create some test messages
        messages = [
            ChatMessage(
                role="You",
                text="Hello, can you help me with Python?",
                context=None,
            ),
            ChatMessage(
                role="AI",
                text="Of course! I'd be happy to help with Python. What do you need?",
                context=None,
            ),
            ChatMessage(
                role="You",
                text="How do I read a file?",
                context=[
                    ContextChunk(
                        title="example.py",
                        text="# Example file content",
                        path=Path("/tmp/example.py"),
                        reason="Pinned",
                    )
                ],
            ),
            ChatMessage(
                role="AI",
                text="You can use open() function with read() method.",
                context=None,
            ),
        ]

        # Create a test session
        session = ChatSession(
            title="Help with Python file reading",
            messages=messages,
            created_at=datetime.now(),
        )

        # Test 1: Save session
        print("  ✓ Creating test session")
        session_id = manager.save_session(session)
        print(f"  ✓ Saved session with ID: {session_id}")

        # Test 2: Load session
        loaded_session = manager.load_session(session_id)
        assert loaded_session is not None, "Failed to load session"
        print(f"  ✓ Loaded session: {loaded_session.title}")

        # Test 3: Verify session data
        assert loaded_session.title == session.title, "Title mismatch"
        assert len(loaded_session.messages) == len(messages), "Message count mismatch"
        print(f"  ✓ Session has {len(loaded_session.messages)} messages")

        # Test 4: Verify message content
        for i, (orig, loaded) in enumerate(zip(messages, loaded_session.messages)):
            assert orig.role == loaded.role, f"Role mismatch at message {i}"
            assert orig.text == loaded.text, f"Text mismatch at message {i}"
            if orig.context:
                assert loaded.context is not None, f"Context missing at message {i}"
                assert len(loaded.context) == len(orig.context), f"Context count mismatch at message {i}"
                for j, (orig_chunk, loaded_chunk) in enumerate(zip(orig.context, loaded.context)):
                    assert orig_chunk.title == loaded_chunk.title, f"Context chunk {j} title mismatch"
                    assert orig_chunk.text == loaded_chunk.text, f"Context chunk {j} text mismatch"
        print("  ✓ All messages verified")

        # Test 5: Load all sessions
        all_sessions = manager.load_all_sessions()
        assert len(all_sessions) == 1, f"Expected 1 session, got {len(all_sessions)}"
        print(f"  ✓ load_all_sessions() returned {len(all_sessions)} session(s)")

        # Test 6: Create another session
        session2 = ChatSession(
            title="Another conversation",
            messages=[
                ChatMessage(role="You", text="Test message", context=None),
            ],
            created_at=datetime.now(),
        )
        session_id2 = manager.save_session(session2)
        print(f"  ✓ Saved second session with ID: {session_id2}")

        # Test 7: Verify we have 2 sessions
        all_sessions = manager.load_all_sessions()
        assert len(all_sessions) == 2, f"Expected 2 sessions, got {len(all_sessions)}"
        print(f"  ✓ Now have {len(all_sessions)} sessions")

        # Test 8: Delete a session
        success = manager.delete_session(session_id)
        assert success, "Failed to delete session"
        print(f"  ✓ Deleted session {session_id}")

        # Test 9: Verify only 1 session remains
        all_sessions = manager.load_all_sessions()
        assert len(all_sessions) == 1, f"Expected 1 session after delete, got {len(all_sessions)}"
        assert all_sessions[0][0] == session_id2, "Wrong session remaining"
        print(f"  ✓ Correct session remaining after delete")

        # Test 10: Update existing session
        updated_messages = session2.messages + [
            ChatMessage(role="AI", text="Response", context=None)
        ]
        updated_session = ChatSession(
            title=session2.title,
            messages=updated_messages,
            created_at=session2.created_at,
        )
        manager.save_session(updated_session, session_id2)
        reloaded = manager.load_session(session_id2)
        assert len(reloaded.messages) == 2, "Updated session should have 2 messages"
        print("  ✓ Session update works correctly")

    print("\n✅ All chat history persistence tests passed!\n")


if __name__ == "__main__":
    try:
        test_chat_history_persistence()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
