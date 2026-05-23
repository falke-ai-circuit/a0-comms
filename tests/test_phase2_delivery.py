#!/usr/bin/env python3
"""Phase 2 Live Delivery Tests — registry, bus, messenger list_sessions"""
import sys
import os
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock

sys.path.insert(0, "/a0/usr/plugins/a0_comms")
sys.path.insert(0, "/a0")

from helpers.message_schema import Message
from helpers.mailbox import Mailbox
from helpers.registry import Registry
from helpers.bus import MessageBus


def test_registry_register_and_get():
    """Register session, get returns correct info."""
    registry = Registry()
    mock_agent = Mock()
    registry.register("sess-1", "ctx-1", mock_agent, "test-project")
    entry = registry.get("sess-1")
    assert entry is not None
    assert entry["context_id"] == "ctx-1"
    assert entry["agent_instance"] == mock_agent
    assert entry["project"] == "test-project"
    print("✓ test_registry_register_and_get passed")


def test_registry_unregister():
    """Unregister removes session."""
    registry = Registry()
    mock_agent = Mock()
    registry.register("sess-2", "ctx-2", mock_agent)
    assert registry.unregister("sess-2") is True
    assert registry.get("sess-2") is None
    assert registry.unregister("sess-99") is False
    print("✓ test_registry_unregister passed")


def test_registry_list_active():
    """List returns only registered non-stale sessions."""
    registry = Registry()
    mock_agent = Mock()
    registry.register("sess-a", "ctx-a", mock_agent)
    registry.register("sess-b", "ctx-b", mock_agent)
    # Unregister one
    registry.unregister("sess-b")
    active = registry.list_active()
    assert "sess-a" in active
    assert "sess-b" not in active
    print("✓ test_registry_list_active passed")


def test_registry_stale():
    """Set timeout=0, get returns None immediately (stale)."""
    registry = Registry(timeout_seconds=0)
    mock_agent = Mock()
    registry.register("sess-stale", "ctx-stale", mock_agent)
    assert registry.get("sess-stale") is None
    print("✓ test_registry_stale passed")


def test_bus_direct_injection():
    """Mock agent with context.communicate, assert inject_message returns True."""
    async def run():
        import helpers.bus as bus_module
        bus_module.UserMessage = Mock()  # mock missing framework import
        with tempfile.TemporaryDirectory() as tmpdir:
            mailbox = Mailbox(base_dir=Path(tmpdir))
            registry = Registry()
            bus = MessageBus(mailbox, registry)

            mock_agent = Mock()
            mock_agent.context_id = "live-sess"
            mock_agent.context = Mock()
            mock_agent.context.communicate = Mock(return_value=True)

            registry.register("live-sess", "live-ctx", mock_agent)

            msg = Message(
                from_session="sender",
                to_session="live-sess",
                content="Hello, live agent!"
            )
            result = await bus.inject_message("live-sess", msg)
            assert result is True
            print("✓ test_bus_direct_injection passed")

    asyncio.run(run())


def test_bus_fallback_to_mailbox():
    """Agent context.communicate raises exception, assert returns False and message stored."""
    async def run():
        import helpers.bus as bus_module
        bus_module.UserMessage = Mock()  # mock missing framework import
        with tempfile.TemporaryDirectory() as tmpdir:
            mailbox = Mailbox(base_dir=Path(tmpdir))
            registry = Registry()
            bus = MessageBus(mailbox, registry)

            mock_agent = Mock()
            mock_agent.context_id = "broken-sess"
            mock_agent.context = Mock()
            mock_agent.context.communicate = Mock(side_effect=Exception("injection failed"))

            registry.register("broken-sess", "broken-ctx", mock_agent)

            msg = Message(
                from_session="sender",
                to_session="broken-sess",
                content="Fallback test"
            )
            result = await bus.inject_message("broken-sess", msg)
            assert result is False

            # Verify message landed in mailbox
            inbox = await mailbox.check("broken-sess", mark_read=False, limit=20)
            assert len(inbox) == 1
            assert inbox[0]["content"] == "Fallback test"
            print("✓ test_bus_fallback_to_mailbox passed")

    asyncio.run(run())


def test_messenger_list_sessions():
    """Instantiate MessengerTool, call execute(action='list_sessions'), assert returns session list."""
    async def run():
        from unittest.mock import patch, MagicMock

        class FakeResponse:
            def __init__(self, message="", break_loop=False, additional=None):
                self.message = message
                self.break_loop = break_loop
                self.additional = additional

        class FakeTool:
            pass

        mock_tool_mod = MagicMock()
        mock_tool_mod.Tool = FakeTool
        mock_tool_mod.Response = FakeResponse

        with patch.dict("sys.modules", {"helpers.tool": mock_tool_mod}):
            from tools.messenger import MessengerTool

            tool = MessengerTool()
            mock_agent = Mock()
            tool.agent = mock_agent

            agent_a = Mock()
            agent_b = Mock()
            tool.registry.register("sess-list-1", "ctx-list-1", agent_a, "p1")
            tool.registry.register("sess-list-2", "ctx-list-2", agent_b, "p2")

            response = await tool.execute(action="list_sessions")
            assert "sess-list-1" in response.message
            assert "sess-list-2" in response.message
            print("✓ test_messenger_list_sessions passed")

    asyncio.run(run())


if __name__ == "__main__":
    print("=== a0-comms Phase 2 Tests ===\n")
    test_registry_register_and_get()
    test_registry_unregister()
    test_registry_list_active()
    test_registry_stale()
    test_bus_direct_injection()
    test_bus_fallback_to_mailbox()
    test_messenger_list_sessions()
    print("\n=== All Phase 2 tests passed ✓ ===")
