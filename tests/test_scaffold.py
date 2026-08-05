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