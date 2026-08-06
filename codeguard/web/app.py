from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
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

    @app.get("/session")
    async def session_entry(scenario: str = "a"):
        """Entry from scenario cards: create a session and go to dashboard."""
        session_id = str(uuid.uuid4())
        sessions[session_id] = {"scenario": scenario, "state": "created"}
        return RedirectResponse(url=f"/dashboard?session={session_id}", status_code=303)

    @app.get("/")
    async def index(request: Request):
        return _templates.TemplateResponse(
            request=request,
            name="scenarios.html",
            context={"mock_mode": mode == "demo"},
        )

    @app.get("/dashboard")
    async def dashboard(request: Request, session: str = ""):
        """Agent running dashboard (P2)."""
        demo_session_id = session or str(uuid.uuid4())
        sessions.setdefault(demo_session_id, {
            "scenario": "demo",
            "state": "INITIALIZING",
            "current_step": 0,
            "trace": [],
            "guardrail_decisions": [],
        })
        return _templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "mock_mode": mode == "demo",
                "session_id": demo_session_id,
                "states": [
                    {"name": "INITIALIZING", "label": "初始化中", "icon": "◷", "color": "muted"},
                    {"name": "BUILDING_CONTEXT", "label": "构建上下文", "icon": "▤", "color": "muted"},
                    {"name": "DECIDING", "label": "决策中", "icon": "◇", "color": "accent"},
                    {"name": "GOVERNING", "label": "治理评估", "icon": "🛡", "color": "accent"},
                    {"name": "AWAITING_APPROVAL", "label": "等待审批", "icon": "⏸", "color": "warn"},
                    {"name": "EXECUTING", "label": "执行工具", "icon": "▶", "color": "accent"},
                    {"name": "VALIDATING", "label": "校验测试", "icon": "✓", "color": "accent"},
                    {"name": "FEEDING_BACK", "label": "反馈回灌", "icon": "↺", "color": "warn"},
                ],
                "terminal_states": [
                    {"name": "COMPLETED", "label": "已完成", "icon": "✓", "color": "success"},
                    {"name": "FAILED", "label": "已失败", "icon": "✕", "color": "danger"},
                    {"name": "CANCELLED", "label": "已取消", "icon": "◌", "color": "meta"},
                    {"name": "LIMIT_REACHED", "label": "达到上限", "icon": "⇪", "color": "warn"},
                ],
            },
        )

    @app.get("/session/{session_id}/state")
    async def get_session_state(session_id: str):
        """Get session state for polling."""
        session = sessions.get(session_id)
        if not session:
            return {"error": "session not found"}
        return {
            "session_id": session_id,
            "scenario": session.get("scenario", ""),
            "state": session.get("state", "INITIALIZING"),
            "current_step": session.get("current_step", 0),
            "trace": session.get("trace", []),
            "guardrail_decisions": session.get("guardrail_decisions", []),
        }

    # Mount static files AFTER all routes
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    return app
