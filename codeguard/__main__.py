"""CodeGuard Harness — CLI entry point."""

import sys
import argparse


def main(args: list[str] | None = None) -> None:
    """Dispatch CLI commands to their implementations.

    Args:
        args: CLI argument list (defaults to sys.argv[1:] for production use).
    """
    parser = argparse.ArgumentParser(
        prog="codeguard",
        description=(
            "CodeGuard Harness — Governance-driven test feedback loop "
            "for coding agents"
        ),
    )
    parser.add_argument("--version", action="version", version="0.1.0")
    sub = parser.add_subparsers(dest="command")

    # chat
    chat_parser = sub.add_parser("chat", help="Start interactive agent session")
    chat_parser.add_argument("--mode", default="local",
                             choices=["test", "local", "demo"],
                             help="Operating mode (default: local)")

    # demo
    demo_parser = sub.add_parser("demo", help="Run demo mode")
    demo_parser.add_argument("--scenario", default="a", choices=["a", "b", "c"],
                             help="Demo scenario (default: a)")
    demo_parser.add_argument("scenario_pos", nargs="?",
                             choices=["a", "b", "c"], default=None,
                             help="Demo scenario positional")

    # web
    web_parser = sub.add_parser("web", help="Start WebUI demo")
    web_parser.add_argument("--port", type=int, default=8080, help="Listen port")
    web_parser.add_argument("--host", default="127.0.0.1", help="Bind address")

    # key
    key_parser = sub.add_parser("key", help="Manage API keys")
    key_sub = key_parser.add_subparsers(dest="key_command")
    for kc in ["set", "status", "update", "clear"]:
        p = key_sub.add_parser(kc)
        p.add_argument("--provider", default="deepseek", help="API provider name")

    # config
    sub.add_parser("config", help="Show effective configuration")

    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        sys.exit(0)

    # Dispatch to real command implementations
    if parsed.command == "chat":
        from codeguard.cli.chat import chat_command
        cli_args = ["--mode", parsed.mode]
        chat_command(cli_args)

    elif parsed.command == "demo":
        from codeguard.cli.demo_cmd import demo_command
        scenario = parsed.scenario_pos or parsed.scenario
        cli_args = ["--scenario", scenario]
        demo_command(cli_args)

    elif parsed.command == "web":
        from codeguard.cli.web_cmd import web_command
        # Only forward explicitly-passed flags so web_cmd defaults
        # (PORT/HOST env vars, Render) are not overridden.
        cli_args = []
        if parsed.port != 8080:
            cli_args += ["--port", str(parsed.port)]
        if parsed.host != "127.0.0.1":
            cli_args += ["--host", parsed.host]
        web_command(cli_args)

    elif parsed.command == "config":
        from codeguard.cli.config_cmd import config_command
        output = config_command(args=[])
        print(output)

    elif parsed.command == "key":
        from codeguard.cli.key_cmd import (
            key_set_command, key_status_command,
            key_update_command, key_clear_command,
        )
        key_cmd = parsed.key_command
        provider = getattr(parsed, "provider", "deepseek")
        cli_args = ["--provider", provider]
        if key_cmd == "set":
            key_set_command(cli_args)
        elif key_cmd == "status":
            key_status_command(cli_args)
        elif key_cmd == "update":
            key_update_command(cli_args)
        elif key_cmd == "clear":
            key_clear_command(cli_args)
        else:
            key_parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()