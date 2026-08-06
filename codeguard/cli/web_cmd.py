"""CLI web command — start WebUI demo."""


def web_command(args: list[str]) -> None:
    """Start the WebUI demo server.

    Args:
        args: CLI arguments after 'web'. Supports --port, --host.
    """
    host = "127.0.0.1"
    port = 8080
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                pass
        elif arg == "--host" and i + 1 < len(args):
            host = args[i + 1]

    import uvicorn
    uvicorn.run("codeguard.web.app:app", host=host, port=port, reload=False)