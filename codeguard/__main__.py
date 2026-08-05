import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="codeguard",
        description=(
            "CodeGuard Harness — Governance-driven test feedback loop "
            "for coding agents"
        ),
    )
    parser.add_argument("--version", action="version", version="0.1.0")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("chat", help="Start interactive agent session")
    sub.add_parser("demo", help="Run demo mode")
    sub.add_parser("web", help="Start WebUI demo")
    key_parser = sub.add_parser("key", help="Manage API keys")
    key_sub = key_parser.add_subparsers(dest="key_command")
    for kc in ["set", "status", "update", "clear"]:
        p = key_sub.add_parser(kc)
        p.add_argument("--provider", default="deepseek", help="API provider name")
    sub.add_parser("config", help="Show effective configuration")
    args = parser.parse_args()
    print(f"CodeGuard Harness v0.1.0 — command: {args.command or 'none'}")


if __name__ == "__main__":
    main()