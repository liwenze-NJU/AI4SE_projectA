"""Tests for key command security: getpass usage, key not leaked in output."""

import sys
import pytest
from unittest.mock import patch, MagicMock
import codeguard.cli.key_cmd as key_cmd


class TestKeySetUsesGetpass:
    """Verify that key_set_command uses getpass.getpass, not input()."""

    def test_key_set_calls_getpass_not_input(self):
        with patch("codeguard.cli.key_cmd.getpass") as mock_gp, \
             patch("codeguard.cli.key_cmd.KeyringCredentialStore") as mock_store, \
             patch("sys.exit"):
            mock_gp.getpass.return_value = "sk-test-123"
            key_cmd.key_set_command(["--provider", "deepseek"])
            mock_gp.getpass.assert_called_once()
            # Confirm store.set received the key
            mock_store.return_value.set.assert_called_once_with(
                "deepseek", "sk-test-123"
            )

    def test_key_set_output_does_not_contain_key(self, capsys):
        with patch("codeguard.cli.key_cmd.getpass") as mock_gp, \
             patch("codeguard.cli.key_cmd.KeyringCredentialStore"), \
             patch("sys.exit"):
            mock_gp.getpass.return_value = "sk-secret-abc"
            key_cmd.key_set_command(["--provider", "deepseek"])
            captured = capsys.readouterr()
            assert "sk-secret-abc" not in captured.out
            assert "sk-secret-abc" not in captured.err
            assert "hidden" not in captured.out.lower()  # no fake promise

    def test_key_set_empty_key_errors(self):
        with patch("codeguard.cli.key_cmd.getpass") as mock_gp, \
             patch("codeguard.cli.key_cmd.KeyringCredentialStore"):
            mock_gp.getpass.return_value = "   "
            with pytest.raises(SystemExit) as exc_info:
                key_cmd.key_set_command(["--provider", "deepseek"])
            assert exc_info.value.code == 1

    def test_key_update_also_calls_getpass(self):
        with patch("codeguard.cli.key_cmd.getpass") as mock_gp, \
             patch("codeguard.cli.key_cmd.KeyringCredentialStore"), \
             patch("sys.exit"):
            mock_gp.getpass.return_value = "sk-new-key"
            key_cmd.key_update_command(["--provider", "deepseek"])
            mock_gp.getpass.assert_called_once()
