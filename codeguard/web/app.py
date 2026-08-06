from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
import uuid

_templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def create_app(mode: str = "demo") -> FastAPI:
    app = FastAPI(title="CodeGuard Harness WebUI")

    sessions = {}

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": mode, "mock": mode == "demo"}

    @app.post("/session")
    async def create_session(scenario: str = "a"):
        session_id = str(uuid.uuid4())
        sessions[session_id] = {"scenario": scenario, "state": "created"}
        return {"session_id": session_id, "scenario": scenario}

    @app.get("/")
    async def index(request: Request):
        return _templates.TemplateResponse(
            request=request,
            name="scenarios.html",
            context={"mock_mode": mode == "demo"},
        )

    return app
