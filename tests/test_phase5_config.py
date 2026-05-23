#!/usr/bin/env python3
"""Phase 5 Tests — config resolution, permissions integration, enabled check, backward compat"""
import sys
import os
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, "/a0/usr/plugins/a0_comms")
sys.path.insert(0, "/a0")

from usr.plugins.a0_comms.helpers.config import MessengerConfig
from usr.plugins.a0_comms.helpers.mailbox import Mailbox
from usr.plugins.a0_comms.helpers.message_schema import Message


# Reusable helpers for MessengerTool tests (matching Phase 4 pattern)
class FakeResponse:
    def __init__(self, message="", break_loop=False, additional=None):
        self.message = message
        self.break_loop = break_loop
        self.additional = additional or {}

class FakeTool:
    pass


def _create_messenger_tool(mock_agent: Mock):
    """Helper to create MessengerTool with test fixtures (Phase 4 pattern)."""
    mock_tool_mod = MagicMock()
    mock_tool_mod.Tool = FakeTool
    mock_tool_mod.Response = FakeResponse

    p = patch.dict("sys.modules", {"helpers.tool": mock_tool_mod})
    p.start()
    from tools.messenger import MessengerTool
    p.stop()

    tool = MessengerTool()
    tool.agent = mock_agent
    return tool


# ============================================================
# Test: MessengerConfig loads defaults only when no project
# ============================================================
def test_config_load_defaults():
    """MessengerConfig with no project loads default_config.yaml only."""
    config = MessengerConfig()
    assert config.enabled is True
    assert config.allowed_cross_project_messages == ["*"]
    assert isinstance(config.agent_capabilities, list)  # No agent profile -> empty list
    assert config.get("default_routing_mode") == "auto"
    assert config.get("default_timeout_seconds") == 120
    print("✓ test_config_load_defaults passed")


# ============================================================
# Test: Project config overrides global defaults
# ============================================================
def test_config_project_override():
    """Create temp project config, verify it overrides global."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_name = Path(tmpdir).name
        project_dir = Path(f"/a0/usr/projects/{project_name}")
        project_dir.mkdir(parents=True, exist_ok=True)

        config_file = project_dir / "a0_comms_config.yaml"
        config_file.write_text("allowed_cross_project_messages: ['a0-circuit']\nenabled: true\n")

        try:
            config = MessengerConfig(project_name=project_name)
            assert config.allowed_cross_project_messages == ["a0-circuit"]
            assert config.enabled is True
            # Non-overridden keys still come from global defaults
            assert config.get("default_timeout_seconds") == 120
            print("✓ test_config_project_override passed")
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)


# ============================================================
# Test: Agent override within project config
# ============================================================
def test_config_agent_override():
    """Project config with agents section — conductor gets its own override."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_name = Path(tmpdir).name
        project_dir = Path(f"/a0/usr/projects/{project_name}")
        project_dir.mkdir(parents=True, exist_ok=True)

        config_file = project_dir / "a0_comms_config.yaml"
        config_file.write_text(
            "allowed_cross_project_messages: ['a0-circuit']\n"
            "agents:\n"
            "  conductor:\n"
            "    allowed_cross_project_messages: ['a0-evol']\n"
        )

        try:
            # Without agent profile — gets project-level override
            config_default = MessengerConfig(project_name=project_name)
            assert config_default.allowed_cross_project_messages == ["a0-circuit"]

            # With conductor agent profile — gets agent-level override
            config_conductor = MessengerConfig(project_name=project_name, agent_profile="conductor")
            assert config_conductor.allowed_cross_project_messages == ["a0-evol"]

            print("✓ test_config_agent_override passed")
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)


# ============================================================
# Test: Full resolution chain — global → project → agent
# ============================================================
def test_config_resolution_chain():
    """Full chain: global defaults → project override → agent override = final value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_name = Path(tmpdir).name
        project_dir = Path(f"/a0/usr/projects/{project_name}")
        project_dir.mkdir(parents=True, exist_ok=True)

        config_file = project_dir / "a0_comms_config.yaml"
        config_file.write_text(
            "allowed_cross_project_messages: ['a0-circuit']\n"
            "default_timeout_seconds: 60\n"
            "agents:\n"
            "  conductor:\n"
            "    default_timeout_seconds: 30\n"
            "    enabled: false\n"
        )

        try:
            # Global-level
            global_cfg = MessengerConfig()
            assert global_cfg.allowed_cross_project_messages == ["*"]
            assert global_cfg.get("default_timeout_seconds") == 120
            assert global_cfg.enabled is True

            # Project-level
            proj_cfg = MessengerConfig(project_name=project_name)
            assert proj_cfg.allowed_cross_project_messages == ["a0-circuit"]
            assert proj_cfg.get("default_timeout_seconds") == 60
            assert proj_cfg.enabled is True  # Not overridden at project level

            # Agent-level (conductor)
            agent_cfg = MessengerConfig(project_name=project_name, agent_profile="conductor")
            assert agent_cfg.allowed_cross_project_messages == ["a0-circuit"]  # Agent didn't override this
            assert agent_cfg.get("default_timeout_seconds") == 30
            assert agent_cfg.enabled is False  # Overridden by agent

            print("✓ test_config_resolution_chain passed")
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)


# ============================================================
# Test: Permission check uses resolved config (MessengerTool integration)
# ============================================================
def test_permission_with_resolved_config():
    """Create MessengerTool, set project context, verify _check_cross_project_permission uses resolved config."""
    async def run():
        # Set up MessengerConfig with restricted cross-project
        resolved = MessengerConfig()
        resolved._resolved["allowed_cross_project_messages"] = ["a0-circuit"]

        mock_agent = Mock()
        mock_agent.context_id = "a0-circuit:conductor"
        mock_agent.profile_name = "conductor"

        tool = _create_messenger_tool(mock_agent)
        tool._loaded_config = resolved

        # Same project — allowed
        allowed, reason = tool._check_cross_project_permission("a0-circuit:agent1", "a0-circuit:agent2")
        assert allowed is True
        assert reason == ""

        # Cross-project FROM blocked project (a0-evol not in allowed list)
        allowed, reason = tool._check_cross_project_permission("a0-evol:agent1", "a0-circuit:agent2")
        assert allowed is False
        assert "blocked" in reason

        print("✓ test_permission_with_resolved_config passed")

    asyncio.run(run())


# ============================================================
# Test: No project config exists → falls back to default_config.yaml
# ============================================================
def test_permission_fallback_no_project():
    """No project config file → _config falls back to raw default_config.yaml."""
    async def run():
        mock_agent = Mock()
        mock_agent.context_id = "nonexistent-project:agent1"
        mock_agent.profile_name = "agent1"

        tool = _create_messenger_tool(mock_agent)

        # Should resolve config without _loaded_config being set
        # Since no project config exists, it falls back to default_config.yaml
        # With wildcard "*", all cross-project is allowed
        allowed, reason = tool._check_cross_project_permission("any:agent1", "other:agent2")
        assert allowed is True  # Wildcard in defaults allows all

        print("✓ test_permission_fallback_no_project passed")

    asyncio.run(run())


# ============================================================
# Test: Messenger disabled in config → all actions return error
# ============================================================
def test_messenger_disabled():
    """Config with enabled: false → all actions return error."""
    async def run():
        mock_agent = Mock()
        mock_agent.context_id = "test:agent1"
        mock_agent.profile_name = "agent1"

        tool = _create_messenger_tool(mock_agent)
        # Set config with enabled: false as dict (backward compat path)
        tool._loaded_config = {
            "enabled": False,
            "allowed_cross_project_messages": ["*"]
        }

        # Test multiple actions — all should return disabled error
        for action in ["send", "check", "reply", "forward", "broadcast", "list_sessions", "switch_session"]:
            kwargs = {"action": action}
            if action in ("send", "reply", "forward", "switch_session"):
                kwargs["to_session"] = "target:agent"
                kwargs["message"] = "test"
                if action == "switch_session":
                    kwargs["project"] = "test-project"
            if action == "broadcast":
                kwargs["message"] = "test"

            response = await tool.execute(**kwargs)
            assert "disabled" in response.message.lower(), f"{action} should return disabled error, got: {response.message}"

        print("✓ test_messenger_disabled passed")

    asyncio.run(run())


# ============================================================
# Test: Backward compat — setting _loaded_config directly still works
# ============================================================
def test_backward_compat_direct_config():
    """Setting _loaded_config directly still works (as Phase 4 tests do)."""
    async def run():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "mailboxes"
            tmp_path.mkdir(parents=True)

            with patch.object(Mailbox, "BASE_DIR", tmp_path):
                mock_agent = Mock()
                mock_agent.context_id = "legacy:agent1"
                mock_agent.profile_name = "agent1"

                tool = _create_messenger_tool(mock_agent)
                # Set raw dict (Phase 4 pattern)
                tool._loaded_config = {
                    "allowed_cross_project_messages": ["a0-circuit"],
                    "enabled": True
                }

                # Same project — should work
                response = await tool.execute(
                    action="send",
                    to_session="legacy:agent2",
                    message="Hello same project"
                )
                assert "blocked" not in response.message.lower()

                # Cross-project to blocked (a0-evol not in allowed list)
                response = await tool.execute(
                    action="send",
                    to_session="a0-evol:agent1",
                    message="Blocked cross-project"
                )
                assert "blocked" in response.message.lower()

                print("✓ test_backward_compat_direct_config passed")

    asyncio.run(run())


# ============================================================
# Test: from_dict creates config from pre-resolved dict
# ============================================================
def test_config_from_dict():
    """from_dict() creates a MessengerConfig from a pre-resolved dict."""
    data = {
        "enabled": True,
        "allowed_cross_project_messages": ["a0-circuit", "a0-comms"],
        "default_timeout_seconds": 90
    }
    config = MessengerConfig.from_dict(data)
    assert config.enabled is True
    assert config.allowed_cross_project_messages == ["a0-circuit", "a0-comms"]
    assert config.get("default_timeout_seconds") == 90
    print("✓ test_config_from_dict passed")


# ============================================================
# Test: MessengerConfig handles missing default_config.yaml gracefully
# ============================================================
def test_config_missing_default():
    """MessengerConfig handles missing default_config.yaml gracefully."""
    # Path to default_config.yaml relative to config.py (parent.parent)
    config_dir = Path("/a0/usr/plugins/a0_comms")
    original_path = config_dir / "default_config.yaml"
    temp_backup = config_dir / "default_config.yaml.backup-test"

    # Move config temporarily to simulate missing file
    if original_path.exists():
        shutil.move(str(original_path), str(temp_backup))

    try:
        config = MessengerConfig()
        assert config._resolved == {}
        assert config.enabled is True  # Default True
        assert config.allowed_cross_project_messages == []  # Empty list
        print("✓ test_config_missing_default passed")
    finally:
        if temp_backup.exists():
            shutil.move(str(temp_backup), str(original_path))


# ============================================================
# Test runner
# ============================================================
if __name__ == "__main__":
    print("=== a0-comms Phase 5 Tests ===\n")
    tests = [
        test_config_load_defaults,
        test_config_project_override,
        test_config_agent_override,
        test_config_resolution_chain,
        test_permission_with_resolved_config,
        test_permission_fallback_no_project,
        test_messenger_disabled,
        test_backward_compat_direct_config,
        test_config_from_dict,
        test_config_missing_default,
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
    print(f"\n=== Phase 5: {passed}/{len(tests)} passed, {failed} failed {'✓' if failed == 0 else '✗'} ===")
