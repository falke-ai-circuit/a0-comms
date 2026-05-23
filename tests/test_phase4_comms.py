#!/usr/bin/env python3
"""Phase 4 Tests — forward, broadcast, cross-project permissions, auto-inbox extension"""
import sys
import os
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, "/a0/usr/plugins/a0_comms")
sys.path.insert(0, "/a0")

# Use full dotted path so we share the same module object as messenger.py
from usr.plugins.a0_comms.helpers.message_schema import Message
from usr.plugins.a0_comms.helpers.mailbox import Mailbox
from usr.plugins.a0_comms.helpers.registry import Registry


class FakeResponse:
    def __init__(self, message="", break_loop=False, additional=None):
        self.message = message
        self.break_loop = break_loop
        self.additional = additional or {}

class FakeTool:
    pass


def _create_messenger_tool(mailbox_base_dir: Path, mock_agent: Mock):
    """Helper to create a MessengerTool with test fixtures."""
    mock_tool_mod = MagicMock()
    mock_tool_mod.Tool = FakeTool
    mock_tool_mod.Response = FakeResponse

    p = patch.dict("sys.modules", {"helpers.tool": mock_tool_mod})
    p.start()
    from tools.messenger import MessengerTool
    p.stop()

    tool = MessengerTool()
    tool.agent = mock_agent
    tool._loaded_config = {"allowed_cross_project_messages": ["*"]}

    async def _mock_deliver(to_session, msg):
        from usr.plugins.a0_comms.helpers.mailbox import Mailbox
        mbox = Mailbox()
        await mbox.store(to_session, msg)
        return False
    tool._deliver_or_store = _mock_deliver

    mock_reg = Mock()
    mock_reg.registry = Registry()
    tool._registry = mock_reg
    return tool


# ============================================================
# Test: forward from inbox
# ============================================================
def test_forward_from_inbox():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()
                src_msg = Message(
                    from_session="sender:agent",
                    to_session="forwarder:agent",
                    from_agent="sender_agent",
                    content="Original message for forwarding test",
                    mode="async"
                )
                src_msg.message_id = "msg-test-001"
                await mailbox.store("forwarder:agent", src_msg)

                mock_agent = Mock()
                mock_agent.context_id = "forwarder:agent"
                mock_agent.profile_name = "forwarder"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                response = await tool.execute(
                    action="forward",
                    message_id="msg-test-001",
                    to_session="target:agent"
                )

                assert response.additional.get("status") == "forwarded"
                assert response.additional.get("original_message_id") == "msg-test-001"

                target_inbox = await mailbox.check("target:agent", mark_read=False, limit=20)
                assert len(target_inbox) == 1
                assert "Original message for forwarding test" in target_inbox[0]["content"]
                assert target_inbox[0]["mode"] == "forwarded"
                print("✓ test_forward_from_inbox passed")

    asyncio.run(run())


# ============================================================
# Test: forward message not found
# ============================================================
def test_forward_message_not_found():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "forwarder:agent"
                mock_agent.profile_name = "forwarder"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                response = await tool.execute(
                    action="forward",
                    message_id="nonexistent-id",
                    to_session="target:agent"
                )

                assert "not found" in response.message.lower()
                print("✓ test_forward_message_not_found passed")

    asyncio.run(run())


# ============================================================
# Test: forward with annotation
# ============================================================
def test_forward_with_annotation():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()
                src_msg = Message(
                    from_session="sender:agent",
                    to_session="forwarder:agent",
                    from_agent="sender_agent",
                    content="Original content",
                    mode="async"
                )
                src_msg.message_id = "msg-ann-001"
                await mailbox.store("forwarder:agent", src_msg)

                mock_agent = Mock()
                mock_agent.context_id = "forwarder:agent"
                mock_agent.profile_name = "forwarder"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                response = await tool.execute(
                    action="forward",
                    message_id="msg-ann-001",
                    to_session="target:agent",
                    message="FYI — check this out"
                )

                assert response.additional.get("status") == "forwarded"

                target_inbox = await mailbox.check("target:agent", mark_read=False, limit=20)
                assert len(target_inbox) == 1
                content = target_inbox[0]["content"]
                assert "FYI — check this out" in content
                assert "Original content" in content
                assert "--- Forwarded message ---" in content
                print("✓ test_forward_with_annotation passed")

    asyncio.run(run())


# ============================================================
# Test: broadcast to multiple sessions
# ============================================================
def test_broadcast_to_multiple():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()

                mock_agent = Mock()
                mock_agent.context_id = "broadcaster:agent"
                mock_agent.profile_name = "broadcaster"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                # Override registry.list_active for broadcast
                tool._registry.list_active = Mock(return_value=[
                    "broadcaster:agent",
                    "target1:agent",
                    "target2:agent",
                    "target3:agent"
                ])

                response = await tool.execute(
                    action="broadcast",
                    message="⚠️ System broadcast test"
                )

                assert response.additional.get("status") == "broadcast"
                assert response.additional.get("delivered_count") == 3
                assert response.additional.get("target_count") == 3

                for target in ["target1:agent", "target2:agent", "target3:agent"]:
                    inbox = await mailbox.check(target, mark_read=False, limit=20)
                    assert len(inbox) == 1, f"{target} should have 1 message, got {len(inbox)}"
                    assert "System broadcast test" in inbox[0]["content"]

                self_inbox = await mailbox.check("broadcaster:agent", mark_read=False, limit=20)
                assert len(self_inbox) == 0
                print("✓ test_broadcast_to_multiple passed")

    asyncio.run(run())


# ============================================================
# Test: broadcast with no active sessions
# ============================================================
def test_broadcast_no_active():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "loner:agent"
                mock_agent.profile_name = "loner"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                tool._registry.list_active = Mock(return_value=["loner:agent"])

                response = await tool.execute(
                    action="broadcast",
                    message="Test msg"
                )

                assert "No active sessions" in response.message
                print("✓ test_broadcast_no_active passed")

    asyncio.run(run())


# ============================================================
# Test: cross-project same project → allowed
# ============================================================
def test_cross_project_allowed():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "project-a:agent1"
                mock_agent.profile_name = "agent1"
                tool = _create_messenger_tool(tmp_path, mock_agent)
                # Restrict cross-project but same project should pass
                tool._loaded_config = {"allowed_cross_project_messages": ["project-b"]}

                response = await tool.execute(
                    action="send",
                    to_session="project-a:agent2",
                    message="Hello same project"
                )

                assert "blocked" not in response.message.lower()
                print("✓ test_cross_project_allowed passed")

    asyncio.run(run())


# ============================================================
# Test: cross-project blocked
# ============================================================
def test_cross_project_blocked():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "project-alpha:agent1"
                mock_agent.profile_name = "agent1"
                tool = _create_messenger_tool(tmp_path, mock_agent)
                tool._loaded_config = {"allowed_cross_project_messages": ["project-beta"]}

                response = await tool.execute(
                    action="send",
                    to_session="project-gamma:agent2",
                    message="cross-project attempt"
                )

                assert "blocked" in response.message.lower()
                print("✓ test_cross_project_blocked passed")

    asyncio.run(run())


# ============================================================
# Test: cross-project wildcard allows all
# ============================================================
def test_cross_project_wildcard():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "project-x:agent1"
                mock_agent.profile_name = "agent1"
                tool = _create_messenger_tool(tmp_path, mock_agent)
                tool._loaded_config = {"allowed_cross_project_messages": ["*"]}

                response = await tool.execute(
                    action="send",
                    to_session="project-y:agent2",
                    message="Wildcard cross-project"
                )

                assert "blocked" not in response.message.lower()
                print("✓ test_cross_project_wildcard passed")

    asyncio.run(run())


# ============================================================
# Test: auto inbox extension triggers on loop end
# ============================================================
def test_auto_inbox_check():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "ext_mailboxes"
            tmp_path.mkdir(parents=True)

            # Patch the Mailbox class that extension code uses (full dotted path)
            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                # Create message in target inbox
                mailbox = Mailbox()
                msg = Message(
                    from_session="notifier:agent",
                    to_session="target:agent",
                    from_agent="notifier",
                    content="You have a new task!",
                    mode="async"
                )
                await mailbox.store("target:agent", msg)

                # Mock agent module for UserMessage import
                mock_agent_mod = MagicMock()
                mock_agent_mod.UserMessage = Mock(return_value="mock_user_msg")

                with patch.dict("sys.modules", {"agent": mock_agent_mod}):
                    import importlib
                    ext_module = importlib.import_module(
                        "extensions.python.agent_loop_end"
                    )

                    mock_context = Mock()
                    mock_context.id = "target:agent"
                    mock_context.communicate = Mock()

                    mock_agent = Mock()
                    mock_agent.context_id = "target:agent"

                    mock_response = Mock()

                    with patch.object(ext_module, "_load_config", return_value={"auto_check_inbox": True}):
                        await ext_module.on_agent_loop_end(mock_context, mock_agent, mock_response)

                        mock_context.communicate.assert_called_once()
                        print("✓ test_auto_inbox_check passed")

    asyncio.run(run())


# ============================================================
# Test runner
# ============================================================
if __name__ == "__main__":
    print("=== a0-comms Phase 4 Tests ===\n")
    tests = [
        test_forward_from_inbox,
        test_forward_message_not_found,
        test_forward_with_annotation,
        test_broadcast_to_multiple,
        test_broadcast_no_active,
        test_cross_project_allowed,
        test_cross_project_blocked,
        test_cross_project_wildcard,
        test_auto_inbox_check,
    ]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test_fn.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
    print(f"\n=== Phase 4: {passed}/{len(tests)} passed, {failed} failed {'✓' if failed == 0 else '✗'} ===")
