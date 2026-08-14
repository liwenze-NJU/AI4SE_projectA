"""CLI chat command — interactive agent harness session."""

import sys
from pathlib import Path

from codeguard.chat import ChatHistory, ChatSession
from codeguard.composition import CompositionRoot


def chat_command(args: list[str]) -> None:
    """Run one interactive agent harness session.

    Args:
        args: CLI arguments after 'chat'. Supports --mode {test,local,demo}.

    The loop is created eagerly so wiring errors (e.g. a missing local API
    key) fail fast with the existing safe error message before the
    interactive prompt starts.
    """
    mode = "local"
    for i, arg in enumerate(args):
        if arg == "--mode" and i + 1 < len(args):
            mode = args[i + 1]
            break

    try:
        root = CompositionRoot(mode=mode, workspace_root=Path.cwd())
        loop = root.create_loop(session_id="cli-session")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    history = ChatHistory(max_messages=50, max_summaries=10)
    session = ChatSession(
        loop_factory=lambda session_id: loop,
        history=history,
        status_provider=lambda: {"mode": mode},
    )
    sys.exit(session.run())
