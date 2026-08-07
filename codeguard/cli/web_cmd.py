"""CLI web command — start WebUI demo."""

import os

from codeguard.web.app import app as fastapi_app


def web_command(args: list[str]) -> None:
    """Start the WebUI demo server.

    Uses a direct FastAPI app object (not a "module:app" string) so the
    frozen exe bundle can import it. Render provides the port via the
    ``PORT`` environment variable; local CLI flags take precedence.

    Args:
        args: CLI arguments after 'web'. Supports --port, --host.
    """
    host = "127.0.0.1"
    port = int(os.environ.get("PORT", "8080"))
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                pass
        elif arg == "--host" and i + 1 < len(args):
            host = args[i + 1]

    import uvicorn
    uvicorn.run(fastapi_app, host=host, port=port, reload=False)
