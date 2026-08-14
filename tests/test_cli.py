"""CLI dispatch tests — Task 15.1."""

from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# chat command
# ---------------------------------------------------------------------------

class TestChatCommand:
    def test_imports_and_is_callable(self):
        from codeguard.cli.chat import chat_command
        assert callable(chat_command)

    def test_chat_test_mode_creates_session_and_runs(self):
        from codeguard.cli.chat import chat_command
        with patch("codeguard.cli.chat.CompositionRoot") as mock_root_cls, \
             patch("codeguard.cli.chat.ChatSession") as mock_session_cls:
            mock_root = MagicMock()
            mock_session = MagicMock()
            mock_session.run.return_value = 0
            mock_root_cls.return_value = mock_root
            mock_session_cls.return_value = mock_session

            with pytest.raises(SystemExit) as exc:
                chat_command(args=["--mode", "test"])

            assert exc.value.code == 0
            mock_root_cls.assert_called_once_with(
                mode="test", workspace_root=Path.cwd()
            )
            mock_root.create_loop.assert_called_once_with(session_id="cli-session")
            mock_session_cls.assert_called_once()
            call_kwargs = mock_session_cls.call_args.kwargs
            # The eager loop is handed to the session via the factory.
            assert call_kwargs["loop_factory"]("any") is mock_root.create_loop.return_value
            mock_session.run.assert_called_once()

    def test_chat_demo_mode_selects_demo_root(self):
        from codeguard.cli.chat import chat_command
        with patch("codeguard.cli.chat.CompositionRoot") as mock_root_cls, \
             patch("codeguard.cli.chat.ChatSession") as mock_session_cls:
            mock_root = MagicMock()
            mock_session = MagicMock()
            mock_session.run.return_value = 0
            mock_root_cls.return_value = mock_root
            mock_session_cls.return_value = mock_session

            with pytest.raises(SystemExit) as exc:
                chat_command(args=["--mode", "demo"])

            assert exc.value.code == 0
            mock_root_cls.assert_called_once_with(
                mode="demo", workspace_root=Path.cwd()
            )

    def test_chat_local_mode_without_key_exits_gracefully(self, capsys):
        from codeguard.cli.chat import chat_command
        with patch("codeguard.credentials.store.KeyringCredentialStore.get",
                   return_value=None):
            with pytest.raises(SystemExit) as exc:
                chat_command(args=["--mode", "local"])
            assert exc.value.code == 1
            captured = capsys.readouterr()
            assert "Error:" in captured.out or "Error:" in captured.err


# ---------------------------------------------------------------------------
# demo command
# ---------------------------------------------------------------------------

class TestDemoCommand:
    def test_imports_and_is_callable(self):
        from codeguard.cli.demo_cmd import demo_command
        assert callable(demo_command)

    def test_demo_runs_scenario_a_by_default(self):
        from codeguard.cli.demo_cmd import demo_command
        with patch("codeguard.cli.demo_cmd.CompositionRoot") as mock_root_cls:
            mock_root = MagicMock()
            mock_loop = MagicMock()
            mock_loop.run.return_value = MagicMock(terminal_state=MagicMock(value="completed"))
            mock_root.create_loop.return_value = mock_loop
            mock_root_cls.return_value = mock_root

            with pytest.raises(SystemExit) as exc:
                demo_command(args=[])

            assert exc.value.code == 0
            mock_root_cls.assert_called_once_with(mode="demo")
            mock_root.create_loop.assert_called_once()
            mock_loop.run.assert_called_once()

    def test_demo_runs_specified_scenario(self):
        from codeguard.cli.demo_cmd import demo_command
        with patch("codeguard.cli.demo_cmd.CompositionRoot") as mock_root_cls:
            mock_root = MagicMock()
            mock_loop = MagicMock()
            mock_loop.run.return_value = MagicMock(terminal_state=MagicMock(value="completed"))
            mock_root.create_loop.return_value = mock_loop
            mock_root_cls.return_value = mock_root

            with pytest.raises(SystemExit) as exc:
                demo_command(args=["--scenario", "b"])

            assert exc.value.code == 0

    def test_demo_rejects_unknown_scenario(self):
        from codeguard.cli.demo_cmd import demo_command
        with pytest.raises(SystemExit) as exc:
            demo_command(args=["--scenario", "x"])
        assert exc.value.code != 0


# ---------------------------------------------------------------------------
# web command
# ---------------------------------------------------------------------------

class TestWebCommand:
    def test_imports_and_is_callable(self):
        from codeguard.cli.web_cmd import web_command
        assert callable(web_command)

    def test_web_starts_uvicorn(self):
        from codeguard.cli.web_cmd import web_command
        fake_uvicorn = MagicMock()
        with patch.dict("sys.modules", {"uvicorn": fake_uvicorn}):
            web_command(args=[])
            fake_uvicorn.run.assert_called_once()
            call_kwargs = fake_uvicorn.run.call_args.kwargs
            assert call_kwargs["host"] == "127.0.0.1"
            assert call_kwargs["port"] == 8080


# ---------------------------------------------------------------------------
# config command
# ---------------------------------------------------------------------------

class TestConfigCommand:
    def test_imports_and_is_callable(self):
        from codeguard.cli.config_cmd import config_command
        assert callable(config_command)

    def test_config_returns_string_with_mode(self):
        from codeguard.cli.config_cmd import config_command
        result = config_command(args=[])
        assert isinstance(result, str)
        assert "mode" in result.lower()

    def test_config_shows_workspace_info(self):
        from codeguard.cli.config_cmd import config_command
        result = config_command(args=[])
        assert "workspace" in result.lower()


# ---------------------------------------------------------------------------
# __main__ dispatch
# ---------------------------------------------------------------------------

class TestMainDispatch:
    def test_main_no_args_prints_help(self):
        from codeguard.__main__ import main
        with pytest.raises(SystemExit):
            main([])

    def test_main_version(self):
        from codeguard.__main__ import main
        with pytest.raises(SystemExit):
            main(["--version"])

    def test_main_chat_dispatches(self):
        from codeguard.__main__ import main
        with patch("codeguard.cli.chat.chat_command") as mock_chat:
            mock_chat.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                main(["chat", "--mode", "test"])
            mock_chat.assert_called_once()

    def test_main_demo_dispatches(self):
        from codeguard.__main__ import main
        with patch("codeguard.cli.demo_cmd.demo_command") as mock_demo:
            mock_demo.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                main(["demo"])
            mock_demo.assert_called_once()

    def test_main_web_dispatches(self):
        from codeguard.__main__ import main
        with patch("codeguard.cli.web_cmd.web_command") as mock_web:
            mock_web.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                main(["web"])
            mock_web.assert_called_once()

    def test_main_config_dispatches(self):
        from codeguard.__main__ import main
        with patch("codeguard.cli.config_cmd.config_command") as mock_config:
            mock_config.return_value = "config output"
            main(["config"])

    def test_main_key_dispatches(self):
        from codeguard.__main__ import main
        with patch("codeguard.cli.key_cmd.key_set_command") as mock_key:
            mock_key.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                main(["key", "set", "--provider", "deepseek"])
            mock_key.assert_called_once()

    def test_main_unknown_command(self):
        from codeguard.__main__ import main
        with pytest.raises(SystemExit):
            main(["nonexistent_command_xyz"])