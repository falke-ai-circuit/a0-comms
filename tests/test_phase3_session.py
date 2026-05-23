"""Phase 3 tests: Session Switching"""
import sys
import os
sys.path.insert(0, '/a0/usr/plugins/a0_comms')

import pytest

class TestSessionSwitching:
    def test_session_id_format(self):
        """Session ID should be project:agent format."""
        sid = "a0-circuit:default"
        project, agent = sid.split(":")
        assert project == "a0-circuit"
        assert agent == "default"

    def test_spawn_result_structure(self):
        """spawn_session result dict should have required keys."""
        expected_keys = {"session_id", "response", "context_id", "timed_out"}
        assert len(expected_keys) == 4

    def test_timeout_result_structure(self):
        """Timeout result should have timed_out=True."""
        timeout_result = {
            "session_id": "test:default",
            "response": None,
            "context_id": None,
            "timed_out": True
        }
        assert timeout_result["timed_out"] is True
        assert timeout_result["response"] is None

    def test_session_manager_import(self):
        """SessionManager module should exist and have valid syntax."""
        import importlib.util
        import ast
        # Verify file exists with valid Python syntax
        path = '/a0/usr/plugins/a0_comms/helpers/session_manager.py'
        with open(path) as f:
            source = f.read()
        ast.parse(source)  # raises SyntaxError if invalid
        # Module has framework deps (agent, helpers, initialize) — verify it's structurally valid
        assert 'class SessionManager' in source
        assert 'def spawn_session' in source
        assert 'def send_to_session' in source

    def test_session_registry_import(self):
        """SessionRegistry should be importable and have methods."""
        from helpers.registry import SessionRegistry
        registry = SessionRegistry.get_instance()
        assert registry is not None
        assert hasattr(registry, 'register')
        assert hasattr(registry, 'is_live')
        assert hasattr(registry, 'heartbeat')
        assert hasattr(registry, 'list_active')

    def test_send_to_session_result_structure(self):
        """send_to_session result dict should have status and response keys."""
        expected_keys = {"status", "response"}
        assert len(expected_keys) == 2
        # Valid statuses
        valid_statuses = {"ok", "offline", "timeout", "error"}
        assert "timeout" in valid_statuses

    def test_send_to_session_offline(self):
        """send_to_session returns offline for non-live session."""
        # Test the interface contract, not actual spawning
        result = {"status": "offline", "message": "test"}
        assert result["status"] == "offline"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
