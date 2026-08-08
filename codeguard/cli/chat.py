"""CLI chat command — one-shot agent harness session."""

import sys
from codeguard.composition import CompositionRoot


def chat_command(args: list[str]) -> None:
    """Run one agent harness session.

    Args:
        args: CLI arguments after 'chat'. Supports --mode {test,local,demo}.
    """
    mode = "local"
    for i, arg in enumerate(args):
        if arg == "--mode" and i + 1 < len(args):
            mode = args[i + 1]
            break

    if mode == "test":
        root = CompositionRoot(mode="test")
    elif mode == "demo":
        root = CompositionRoot(mode="demo")
    else:
        root = CompositionRoot(mode="local")

    try:
        loop = root.create_loop(session_id="cli-session")
        result = loop.run()
        print(f"Session completed: {result.terminal_state.value}")
        sys.exit(0)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)