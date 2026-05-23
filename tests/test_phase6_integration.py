#!/usr/bin/env python3
"""Phase 6 Integration Tests — switch_session, multi-step flows, cross-project,
broadcast, auto-inbox extension, parallel sessions, routing state persistence,
and edge cases for forward/reply/broadcast"""
import sys
import os
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock

sys.path.insert(0, "/a0/usr/plugins/a0_comms")
sys.path.insert(0, "/a0")

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

    # Mock session_manager to avoid importing agent/AgentContext
    mock_sm = MagicMock()
    mock_sm.SessionManager = MagicMock()
    sm_patch = patch.dict(
        "sys.modules",
        {"usr.plugins.a0_comms.helpers.session_manager": mock_sm},
    )
    sm_patch.start()

    from tools.messenger import MessengerTool
    p.stop()
    sm_patch.stop()

    tool = MessengerTool()
    tool.agent = mock_agent
    tool._loaded_config = {"allowed_cross_project_messages": ["*"]}

    # Wire _deliver_or_store so it stores into the real tempdir mailbox
    async def _mock_deliver(to_session, msg):
        mbox = Mailbox()
        await mbox.store(to_session, msg)
        return False
    tool._deliver_or_store = _mock_deliver

    mock_reg = Mock()
    mock_reg.registry = Registry()
    tool._registry = mock_reg
    return tool


# ============================================================
# Test 1: switch_session spawns session and returns response
# Fixed: verify spawn_session call args, two return shapes, resilience
# ============================================================
def test_switch_session_success():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "conductor:agent"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                # --- Shape 1: standard success response ---
                mock_sm_class = MagicMock()
                spawn_mock = AsyncMock(return_value={
                    "session_id": "a0-circuit:default",
                    "response": "System check complete. All services operational.",
                    "context_id": "a0-circuit:default-ctx",
                    "timed_out": False,
                })
                mock_sm_class.spawn_session = spawn_mock
                mock_sm_mod = MagicMock()
                mock_sm_mod.SessionManager = mock_sm_class

                with patch.dict("sys.modules", {
                    "usr.plugins.a0_comms.helpers.session_manager": mock_sm_mod,
                }):
                    response = await tool.execute(
                        action="switch_session",
                        project="a0-circuit",
                        message="run system check",
                    )

                # Verify spawn_session called with correct args
                spawn_mock.assert_called_once_with(
                    project="a0-circuit",
                    agent_profile="default",
                    message="run system check",
                    timeout=120,
                )

                # Verify Response correctly transforms the result dict
                assert "a0-circuit:default" in response.message
                assert "System check complete" in response.message
                assert response.additional.get("status") == "completed"
                assert response.additional.get("session_id") == "a0-circuit:default"
                assert response.additional.get("context_id") == "a0-circuit:default-ctx"

                # --- Shape 2: different data + extra unexpected keys (resilience) ---
                spawn_mock.reset_mock()
                spawn_mock.return_value = {
                    "session_id": "my-prod:researcher",
                    "response": "Analysis complete. Found 3 anomalies.",
                    "context_id": "my-prod:researcher-ctx-456",
                    "timed_out": False,
                    "extra_key": "should_be_ignored",
                    "debug_info": "not_relevant",
                }

                with patch.dict("sys.modules", {
                    "usr.plugins.a0_comms.helpers.session_manager": mock_sm_mod,
                }):
                    response2 = await tool.execute(
                        action="switch_session",
                        project="my-prod",
                        message="analyze anomalies",
                        agent_profile="researcher",
                    )

                spawn_mock.assert_called_once_with(
                    project="my-prod",
                    agent_profile="researcher",
                    message="analyze anomalies",
                    timeout=120,
                )

                # Verify tool extracts only the expected fields
                assert "my-prod:researcher" in response2.message
                assert "Analysis complete" in response2.message
                assert response2.additional.get("status") == "completed"
                assert response2.additional.get("session_id") == "my-prod:researcher"
                assert response2.additional.get("context_id") == "my-prod:researcher-ctx-456"

                print("✓ test_switch_session_success passed")

    asyncio.run(run())


# ============================================================
# Test 2: switch_session timeout
# Fixed: verify spawn_session call args, custom and default timeout
# ============================================================
def test_switch_session_timeout():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "conductor:agent"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                # --- Test timed_out=True with custom timeout ---
                mock_sm_class = MagicMock()
                spawn_mock = AsyncMock(return_value={
                    "session_id": "a0-circuit:default",
                    "response": None,
                    "context_id": "a0-circuit:default-ctx",
                    "timed_out": True,
                })
                mock_sm_class.spawn_session = spawn_mock
                mock_sm_mod = MagicMock()
                mock_sm_mod.SessionManager = mock_sm_class

                with patch.dict("sys.modules", {
                    "usr.plugins.a0_comms.helpers.session_manager": mock_sm_mod,
                }):
                    response = await tool.execute(
                        action="switch_session",
                        project="a0-circuit",
                        message="run system check",
                        timeout=30,
                    )

                # Verify spawn_session called with custom timeout
                spawn_mock.assert_called_once_with(
                    project="a0-circuit",
                    agent_profile="default",
                    message="run system check",
                    timeout=30,
                )

                # Verify timeout response formatting
                assert "timed out" in response.message.lower()
                assert "30" in response.message
                assert response.additional.get("status") == "timeout"
                assert response.additional.get("session_id") == "a0-circuit:default"

                # --- Test default timeout (120s) ---
                spawn_mock.reset_mock()
                spawn_mock.return_value = {
                    "session_id": "a0-evol:evol",
                    "response": None,
                    "context_id": "a0-evol:ctx-999",
                    "timed_out": True,
                }

                with patch.dict("sys.modules", {
                    "usr.plugins.a0_comms.helpers.session_manager": mock_sm_mod,
                }):
                    response2 = await tool.execute(
                        action="switch_session",
                        project="a0-evol",
                        message="self-evaluate",
                    )

                # Verify default timeout of 120 is passed
                spawn_mock.assert_called_once_with(
                    project="a0-evol",
                    agent_profile="default",
                    message="self-evaluate",
                    timeout=120,
                )

                assert "timed out" in response2.message.lower()
                assert "120" in response2.message
                assert response2.additional.get("status") == "timeout"
                assert response2.additional.get("session_id") == "a0-evol:evol"

                print("✓ test_switch_session_timeout passed")

    asyncio.run(run())


# ============================================================
# Test 3: evol → conductor inbox → forward → a0-circuit → reply
# ============================================================
def test_evol_conductor_forward_reply_chain():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()

                # Step 1: evol sends update to conductor's mailbox
                evol_msg = Message(
                    from_session="a0-evol:evol",
                    to_session="a0-comms:conductor",
                    from_agent="evol",
                    content="§ AGENT-SELFEVAL complete. Drift detected in minimalism bias.",
                    mode="async",
                )
                await mailbox.store("a0-comms:conductor", evol_msg)

                conductor_agent = Mock()
                conductor_agent.context_id = "a0-comms:conductor"
                conductor_agent.profile_name = "conductor"
                tool_conductor = _create_messenger_tool(tmp_path, conductor_agent)

                # Step 2: Read inbox WITHOUT marking read (to get IDs for forward)
                inbox = await mailbox.check("a0-comms:conductor", mark_read=False, limit=20)
                assert len(inbox) == 1
                msg_id = inbox[0]["message_id"]
                thread_id = inbox[0]["thread_id"]
                assert "§ AGENT-SELFEVAL" in inbox[0]["content"]

                # Step 3: conductor forwards to a0-circuit (while still unread)
                fwd_resp = await tool_conductor.execute(
                    action="forward",
                    message_id=msg_id,
                    to_session="a0-circuit:analyst",
                )
                assert fwd_resp.additional.get("status") == "forwarded"

                # Verify forwarded message in a0-circuit's mailbox
                circuit_inbox = await mailbox.check("a0-circuit:analyst", mark_read=False, limit=20)
                assert len(circuit_inbox) == 1
                assert "AGENT-SELFEVAL" in circuit_inbox[0]["content"]
                assert "Forwarded from evol" in circuit_inbox[0]["content"]

                # Step 4: a0-circuit replies back to conductor
                circuit_agent = Mock()
                circuit_agent.context_id = "a0-circuit:analyst"
                circuit_agent.profile_name = "analyst"
                tool_circuit = _create_messenger_tool(tmp_path, circuit_agent)

                # a0-circuit stores a direct reply message (thread preserved)
                reply_msg = Message(
                    thread_id=thread_id,
                    from_session="a0-circuit:analyst",
                    to_session="a0-comms:conductor",
                    from_agent="analyst",
                    content="Acknowledged. Will adjust capacity analysis.",
                    mode="async",
                )
                await mailbox.store("a0-comms:conductor", reply_msg)

                # Step 5: verify reply in conductor's mailbox
                conductor_inbox = await mailbox.check("a0-comms:conductor", mark_read=False, limit=20)
                reply_found = False
                for m in conductor_inbox:
                    if "Acknowledged" in m["content"]:
                        reply_found = True
                        break
                assert reply_found, "Reply from a0-circuit not found in conductor inbox"
                print("✓ test_evol_conductor_forward_reply_chain passed")

    asyncio.run(run())


# ============================================================
# Test 4: forward with annotation
# ============================================================
def test_forward_with_annotation():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()
                src_msg = Message(
                    from_session="a0-evol:evol",
                    to_session="conductor:agent",
                    from_agent="evol",
                    content="Drift report: minimalism bias at 0.7",
                    mode="async",
                )
                src_msg.message_id = "msg-ann-phase6-001"
                await mailbox.store("conductor:agent", src_msg)

                mock_agent = Mock()
                mock_agent.context_id = "conductor:agent"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                response = await tool.execute(
                    action="forward",
                    message_id="msg-ann-phase6-001",
                    to_session="a0-circuit:reviewer",
                    message="FYI — review this drift finding",
                )

                assert response.additional.get("status") == "forwarded"

                target_inbox = await mailbox.check("a0-circuit:reviewer", mark_read=False, limit=20)
                assert len(target_inbox) == 1
                content = target_inbox[0]["content"]
                assert "FYI — review this drift finding" in content
                assert "Drift report: minimalism bias at 0.7" in content
                assert "--- Forwarded message ---" in content
                assert "Forwarded from evol" in content
                print("✓ test_forward_with_annotation passed")

    asyncio.run(run())


# ============================================================
# Test 5: cross-project blocking
# ============================================================
def test_cross_project_blocking():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                # Agent from a0-comms project
                mock_agent = Mock()
                mock_agent.context_id = "a0-comms:conductor"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)
                # Allow from_project a0-comms for cross-project sends
                tool._loaded_config = {"allowed_cross_project_messages": ["a0-comms"]}

                # Allowed: same project
                resp_same = await tool.execute(
                    action="send",
                    to_session="a0-comms:agent1",
                    message="Same project",
                )
                assert "blocked" not in resp_same.message.lower()

                # Allowed: a0-comms (from_project) IS in allowed list
                resp_allowed = await tool.execute(
                    action="send",
                    to_session="a0-circuit:coder",
                    message="Allowed cross-project",
                )
                assert "blocked" not in resp_allowed.message.lower()

                # Blocked: a0-evol agent (from_project a0-evol) is NOT in allowed list
                mock_agent2 = Mock()
                mock_agent2.context_id = "a0-evol:evol"
                mock_agent2.profile_name = "evol"
                tool2 = _create_messenger_tool(tmp_path, mock_agent2)
                tool2._loaded_config = {"allowed_cross_project_messages": ["a0-comms"]}

                resp_blocked = await tool2.execute(
                    action="send",
                    to_session="a0-circuit:coder",
                    message="Blocked cross-project attempt",
                )
                assert "blocked" in resp_blocked.message.lower()
                print("✓ test_cross_project_blocking passed")

    asyncio.run(run())


# ============================================================
# Test 6: broadcast to active sessions
# ============================================================
def test_broadcast_to_active_sessions():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()

                mock_agent = Mock()
                mock_agent.context_id = "conductor:agent"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                # Register active sessions in the registry
                tool._registry.list_active = Mock(return_value=[
                    "conductor:agent",
                    "a0-circuit:coder",
                    "a0-circuit:analyst",
                    "a0-evol:evol",
                ])

                response = await tool.execute(
                    action="broadcast",
                    message="⚠️ System maintenance in 5 minutes.",
                )

                assert response.additional.get("status") == "broadcast"
                assert response.additional.get("delivered_count") == 3
                assert response.additional.get("target_count") == 3

                for target in ["a0-circuit:coder", "a0-circuit:analyst", "a0-evol:evol"]:
                    inbox = await mailbox.check(target, mark_read=False, limit=20)
                    assert len(inbox) == 1, f"{target} inbox should have 1 message, got {len(inbox)}"
                    assert "System maintenance" in inbox[0]["content"]
                    assert inbox[0]["mode"] == "broadcast"

                # Conductor (self) should NOT receive the broadcast
                self_inbox = await mailbox.check("conductor:agent", mark_read=False, limit=20)
                assert len(self_inbox) == 0
                print("✓ test_broadcast_to_active_sessions passed")

    asyncio.run(run())


# ============================================================
# Test 7: auto-inbox check extension
# Fixed: verify communicate received UserMessage result with notification text
# ============================================================
def test_auto_inbox_check():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "ext_mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                # Store a message in target agent's mailbox
                mailbox = Mailbox()
                msg = Message(
                    from_session="a0-evol:evol",
                    to_session="conductor:agent",
                    from_agent="evol",
                    content="Session absorbed. Pattern shift detected.",
                    mode="async",
                )
                await mailbox.store("conductor:agent", msg)

                # Mock agent module for UserMessage import
                mock_agent_mod = MagicMock()
                mock_agent_mod.UserMessage = Mock(return_value="mock_user_msg")

                with patch.dict("sys.modules", {"agent": mock_agent_mod}):
                    import importlib
                    ext_module = importlib.import_module(
                        "extensions.python.agent_loop_end"
                    )

                    mock_context = Mock()
                    mock_context.id = "conductor:agent"
                    mock_context.communicate = Mock()

                    mock_agent = Mock()
                    mock_agent.context_id = "conductor:agent"

                    mock_response = Mock()

                    with patch.object(ext_module, "_load_config", return_value={"auto_check_inbox": True}):
                        await ext_module.on_agent_loop_end(mock_context, mock_agent, mock_response)

                        # Verify communicate was called with the UserMessage result
                        # containing the notification text
                        mock_agent_mod.UserMessage.assert_called_once()
                        notification_arg = mock_agent_mod.UserMessage.call_args[0][0]
                        assert "Pattern shift detected" in str(notification_arg)

                        # Verify the UserMessage return value was passed to communicate
                        expected_msg = mock_agent_mod.UserMessage.return_value
                        mock_context.communicate.assert_called_once_with(expected_msg)

                        print("✓ test_auto_inbox_check passed")

    asyncio.run(run())


# ============================================================
# Test 8: parallel sessions — explicit target without switching
# ============================================================
def test_parallel_sessions_explicit_target():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()

                # Conductor has current_session concept pointing to a0-circuit
                # But explicitly sends to a0-evol
                mock_agent = Mock()
                mock_agent.context_id = "a0-comms:conductor"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                # Send explicitly to a0-evol:default (not the "current" a0-circuit)
                response = await tool.execute(
                    action="send",
                    to_session="a0-evol:default",
                    message="Run self-evaluation on latest session.",
                )

                assert "blocked" not in response.message.lower()
                assert "queued" in response.additional.get("status", "").lower() or \
                       "delivered" in response.additional.get("status", "").lower()

                # Verify message went to a0-evol, NOT a0-circuit
                evol_inbox = await mailbox.check("a0-evol:default", mark_read=False, limit=20)
                circuit_inbox = await mailbox.check("a0-circuit:default", mark_read=False, limit=20)

                assert len(evol_inbox) == 1, "a0-evol should have received the message"
                assert "Run self-evaluation" in evol_inbox[0]["content"]
                assert len(circuit_inbox) == 0, "a0-circuit should NOT have received the message"
                print("✓ test_parallel_sessions_explicit_target passed")

    asyncio.run(run())


# ============================================================
# Test 9: conductor routing state persistence
# Fixed: removed inline resolve_session, kept JSON round-trip
# and real message sending via MessengerTool
# ============================================================
def test_routing_state_persistence():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            routing_file = Path(tmpdir) / "routing_state.json"

            # Simulate conductor saving routing state (as if via memory_save)
            routing_table = {
                "routing_table": {
                    "a0-circuit": {
                        "session_id": "a0-circuit:default",
                        "context_id": "a0-circuit:ctx-001",
                        "last_seen": "2026-05-23T18:00:00Z",
                    },
                    "a0-evol": {
                        "session_id": "a0-evol:evol",
                        "context_id": "a0-evol:ctx-002",
                        "last_seen": "2026-05-23T17:55:00Z",
                    },
                },
                "current_session": "a0-circuit:default",
            }
            routing_file.write_text(json.dumps(routing_table, indent=2))

            # Load and verify JSON round-trip persistence
            loaded = json.loads(routing_file.read_text())
            assert loaded["current_session"] == "a0-circuit:default"
            assert loaded["routing_table"]["a0-circuit"]["session_id"] == "a0-circuit:default"
            assert loaded["routing_table"]["a0-evol"]["session_id"] == "a0-evol:evol"

            # Use the routing table to send a real message via MessengerTool
            target_session = loaded["routing_table"]["a0-circuit"]["session_id"]

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()

                mock_agent = Mock()
                mock_agent.context_id = "a0-comms:conductor"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                # Send to resolved session from routing table
                response = await tool.execute(
                    action="send",
                    to_session=target_session,
                    message="Task assignment via routing table",
                )

                assert "blocked" not in response.message.lower()

                # Verify message landed at the resolved target
                inbox = await mailbox.check(target_session, mark_read=False, limit=20)
                assert len(inbox) == 1
                assert "Task assignment via routing table" in inbox[0]["content"]

                # Update current_session in routing state (conductor switches focus)
                loaded["current_session"] = "a0-evol:evol"
                routing_file.write_text(json.dumps(loaded, indent=2))

                # Verify the update persists correctly
                reloaded = json.loads(routing_file.read_text())
                assert reloaded["current_session"] == "a0-evol:evol"
                print("✓ test_routing_state_persistence passed")

    asyncio.run(run())


# ============================================================
# Test 10: Edge case — forward of already-read message
# ============================================================
def test_forward_already_read_message():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()

                # Store a message
                msg = Message(
                    from_session="a0-evol:evol",
                    to_session="conductor:agent",
                    from_agent="evol",
                    content="Important update",
                    mode="async",
                )
                await mailbox.store("conductor:agent", msg)

                # Check inbox with mark_read=True — marks the message as read
                read_msgs = await mailbox.check("conductor:agent", mark_read=True, limit=20)
                assert len(read_msgs) == 1
                msg_id = read_msgs[0]["message_id"]

                # Try to forward the already-read message
                mock_agent = Mock()
                mock_agent.context_id = "conductor:agent"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                response = await tool.execute(
                    action="forward",
                    message_id=msg_id,
                    to_session="a0-circuit:analyst",
                )

                # _forward reads with mark_read=False, which only returns unread —
                # so the already-read message should not be found
                assert "not found" in response.message.lower()
                print("✓ test_forward_already_read_message passed")

    asyncio.run(run())


# ============================================================
# Test 11: Edge case — reply to nonexistent thread
# ============================================================
def test_reply_nonexistent_thread():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "conductor:agent"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                response = await tool.execute(
                    action="reply",
                    thread_id="nonexistent-thread-123",
                    message="This reply should fail",
                )

                assert "not found" in response.message.lower()
                print("✓ test_reply_nonexistent_thread passed")

    asyncio.run(run())


# ============================================================
# Test 12: Edge case — broadcast when only self is active
# ============================================================
def test_broadcast_only_self_active():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "conductor:agent"
                mock_agent.profile_name = "conductor"
                tool = _create_messenger_tool(tmp_path, mock_agent)

                # Registry returns only the broadcaster's own session
                tool._registry = Mock()
                tool._registry.list_active = Mock(return_value=["conductor:agent"])

                response = await tool.execute(
                    action="broadcast",
                    message="System maintenance",
                )

                # After filtering self, targets list is empty
                assert "no active sessions" in response.message.lower()
                print("✓ test_broadcast_only_self_active passed")

    asyncio.run(run())


# ============================================================
# Test 13: Edge case — cross-project forward blocking
# ============================================================
def test_forward_cross_project_blocked():
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mailbox = Mailbox()

                # evol receives a message in its inbox
                msg = Message(
                    from_session="a0-comms:researcher",
                    to_session="a0-evol:evol",
                    from_agent="researcher",
                    content="Drift report: pattern detected",
                    mode="async",
                )
                await mailbox.store("a0-evol:evol", msg)

                # Read inbox without marking read
                inbox = await mailbox.check("a0-evol:evol", mark_read=False, limit=20)
                assert len(inbox) == 1
                msg_id = inbox[0]["message_id"]

                mock_agent = Mock()
                mock_agent.context_id = "a0-evol:evol"
                mock_agent.profile_name = "evol"
                tool = _create_messenger_tool(tmp_path, mock_agent)
                # Only a0-comms allowed; agent is from a0-evol → blocked
                tool._loaded_config = {"allowed_cross_project_messages": ["a0-comms"]}

                # Forward to a0-circuit project: should be blocked
                response = await tool.execute(
                    action="forward",
                    message_id=msg_id,
                    to_session="a0-circuit:coder",
                )

                assert "blocked" in response.message.lower()
                print("✓ test_forward_cross_project_blocked passed")

    asyncio.run(run())


# ============================================================
# Test runner
# ============================================================
if __name__ == "__main__":
    print("=== a0-comms Phase 6 Integration Tests ===\n")
    tests = [
        test_switch_session_success,
        test_switch_session_timeout,
        test_evol_conductor_forward_reply_chain,
        test_forward_with_annotation,
        test_cross_project_blocking,
        test_broadcast_to_active_sessions,
        test_auto_inbox_check,
        test_parallel_sessions_explicit_target,
        test_routing_state_persistence,
        test_forward_already_read_message,
        test_reply_nonexistent_thread,
        test_broadcast_only_self_active,
        test_forward_cross_project_blocked,
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
    total = len(tests)
    print(f"\n=== Phase 6: {passed}/{total} passed, {failed} failed {'✓' if failed == 0 else '✗'} ===")
