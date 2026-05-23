#!/usr/bin/env python3
"""Phase 1 Mailbox Core Tests"""
import sys
import os
import asyncio
import tempfile
from pathlib import Path

# Add plugin helpers to path
sys.path.insert(0, "/a0/usr/plugins/a0_comms")

from helpers.message_schema import Message
from helpers.mailbox import Mailbox


def test_message_serialization():
    """Test Message serialize/deserialize round-trip."""
    msg = Message(
        from_session="test-sender",
        to_session="test-recipient",
        from_agent="tester",
        content="Hello, world!"
    )
    data = msg.serialize()
    assert data["from_session"] == "test-sender"
    assert data["content"] == "Hello, world!"
    assert data["status"] == "unread"
    assert data["mode"] == "async"
    assert "message_id" in data
    assert "thread_id" in data
    assert "timestamp" in data

    # Deserialize round-trip
    msg2 = Message.deserialize(data)
    assert msg2.message_id == msg.message_id
    assert msg2.thread_id == msg.thread_id
    assert msg2.content == msg.content
    print("✓ test_message_serialization passed")


def test_mailbox_store_and_check():
    """Test Mailbox store and check."""
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            mailbox = Mailbox(base_dir=Path(tmpdir))
            msg = Message(
                from_session="sender-session",
                to_session="recipient-session",
                from_agent="sender-agent",
                content="Test message from sender"
            )
            message_id = await mailbox.store("recipient-session", msg)
            assert message_id == msg.message_id

            # Check mailbox
            inbox = await mailbox.check("recipient-session", mark_read=True, limit=20)
            assert len(inbox) == 1
            assert inbox[0]["content"] == "Test message from sender"
            assert inbox[0]["status"] == "read"  # marked read after check

            # Check again — should be empty (already read)
            inbox2 = await mailbox.check("recipient-session", mark_read=True, limit=20)
            assert len(inbox2) == 0

            print("✓ test_mailbox_store_and_check passed")

    asyncio.run(run())


def test_mailbox_get_thread():
    """Test Mailbox.get_thread for reply functionality."""
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            mailbox = Mailbox(base_dir=Path(tmpdir))
            thread_id = "test-thread-123"

            # Store two messages in same thread
            msg1 = Message(
                thread_id=thread_id,
                from_session="alice",
                to_session="bob",
                from_agent="alice-agent",
                content="First message"
            )
            msg2 = Message(
                thread_id=thread_id,
                from_session="bob",
                to_session="alice",
                from_agent="bob-agent",
                content="Reply message"
            )
            await mailbox.store("bob", msg1)
            await mailbox.store("alice", msg2)

            # Get thread from bob's mailbox
            thread = await mailbox.get_thread("bob", thread_id)
            assert len(thread) == 1
            assert thread[0]["content"] == "First message"

            # Get thread from alice's mailbox
            thread2 = await mailbox.get_thread("alice", thread_id)
            assert len(thread2) == 1
            assert thread2[0]["content"] == "Reply message"

            print("✓ test_mailbox_get_thread passed")

    asyncio.run(run())


def test_empty_mailbox():
    """Test empty mailbox returns []"""
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            mailbox = Mailbox(base_dir=Path(tmpdir))
            inbox = await mailbox.check("nonexistent-session", mark_read=True)
            assert inbox == []

            thread = await mailbox.get_thread("nonexistent-session", "any-thread")
            assert thread == []

            print("✓ test_empty_mailbox passed")

    asyncio.run(run())


def test_message_defaults():
    """Test Message default values."""
    msg = Message()
    assert msg.status == "unread"
    assert msg.mode == "async"
    assert msg.from_session == ""
    assert msg.message_id  # auto-generated
    assert msg.thread_id  # auto-generated
    assert msg.timestamp  # auto-generated
    print("✓ test_message_defaults passed")


if __name__ == "__main__":
    print("=== a0-comms Phase 1 Tests ===\n")
    test_message_serialization()
    test_message_defaults()
    test_mailbox_store_and_check()
    test_mailbox_get_thread()
    test_empty_mailbox()
    print("\n=== All tests passed ✓ ===")
