"""CLI demo command — run demo scenarios."""

import sys
from codeguard.composition import CompositionRoot


def demo_command(args: list[str]) -> None:
    """Run a demo scenario.

    Args:
        args: CLI arguments after 'demo'. Supports --scenario {a,b,c}.
    """
    scenario = "a"
    for i, arg in enumerate(args):
        if arg == "--scenario" and i + 1 < len(args):
            scenario = args[i + 1]
            break
    # Also accept positional scenario argument
    for arg in args:
        if arg in ("a", "b", "c") and not arg.startswith("-"):
            scenario = arg
            break

    if scenario not in ("a", "b", "c"):
        print(f"Error: unknown scenario '{scenario}'. Expected a, b, or c.", file=sys.stderr)
        sys.exit(2)

    root = CompositionRoot(mode="demo")
    loop = root.create_loop(session_id=f"demo-{scenario}")
    result = loop.run()
    print(f"Demo {scenario} completed: {result.terminal_state.value}")
    sys.exit(0)