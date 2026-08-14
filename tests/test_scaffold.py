import subprocess
import sys


def test_codeguard_help_shows_subcommands():
    """python -m codeguard --help exits 0 and lists the five planned subcommands."""
    result = subprocess.run(
        [sys.executable, "-m", "codeguard", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "chat" in result.stdout
    assert "demo" in result.stdout
    assert "web" in result.stdout
    assert "key" in result.stdout
    assert "config" in result.stdout


def test_codeguard_chat_help_describes_interactive_session():
    """chat subcommand help announces the interactive governed session."""
    result = subprocess.run(
        [sys.executable, "-m", "codeguard", "chat", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Start an interactive governed coding-agent session" in result.stdout


def test_codeguard_version_is_011_during_development():
    """--version reports 0.1.1; the 0.2.0-interactive bump belongs to Task 8."""
    result = subprocess.run(
        [sys.executable, "-m", "codeguard", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.1" in result.stdout
    assert "0.2.0-interactive" not in result.stdout