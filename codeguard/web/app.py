from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
import sys
import uuid

if getattr(sys, "frozen", False):
    # PyInstaller spec bundles assets under _MEIPASS/codeguard/web/...
    _BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "codeguard" / "web"
else:
    _BASE_DIR = Path(__file__).parent
_templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
_static_dir = _BASE_DIR / "static"

_MOCK_PENDING_REQUEST = {
    "request_id": "mock-req-1",
    "action": "write_file(mock://workspace/src/auth.py)",
    "reasons": ["副作用：修改源文件", "可能合法：与测试修复相关"],
    "impact": "mock://workspace/src/auth.py · 依赖模块：auth, session",
    "timeout_seconds": 15,
}


class ApprovalRequest(BaseModel):
    """JSON body for the approval decision endpoint (mock)."""
    decision: str
    request_id: str = "mock-req-1"


_MOCK_RESULTS = {
    "scenario": "C · 测试失败反馈闭环",
    "final_state": "COMPLETED",
    "duration_seconds": 42,
    "step_count": 7,
    "guardrail_counts": {"ALLOW": 1, "BLOCK": 0, "REQUEST_APPROVAL": 0},
    "feedback_loop": {
        "triggered": True,
        "steps": [
            {"title": "第一次失败", "category": "测试失败", "detail": "VALIDATING · 断言失败", "time": "00:09", "color": "danger"},
            {"title": "反馈分类", "category": "断言失败", "detail": "FEEDING_BACK · 分类回灌", "time": "00:11", "color": "warn"},
            {"title": "Agent 改动作", "category": "改用 validate", "detail": "EXECUTING · 修正动作", "time": "00:14", "color": "accent"},
            {"title": "第二次通过", "category": "测试通过", "detail": "VALIDATING · 通过", "time": "00:18", "color": "success"},
        ],
    },
    "memory_entries": [
        {"type": "已批准决策", "summary": "write_file(mock://…/auth.py) 已批准", "source": "00:06"},
        {"type": "任务摘要", "summary": "测试会话：3 步完成，1 次失败恢复", "source": "00:42"},
        {"type": "失败解决方案", "summary": "断言失败 → 改用 validate input 后通过", "source": "00:11"},
        {"type": "项目约定", "summary": "validate 优先于直接写入（本场景示例）", "source": "00:18"},
    ],
}


def _new_demo_session(scenario: str = "demo") -> dict:
    """Create an in-memory demo session (browser-isolated, mock only)."""
    return {
        "scenario": scenario,
        "state": "INITIALIZING",
        "current_step": 0,
        "trace": [],
        "guardrail_decisions": [],
        "pending_request": None,
    }


def create_app(mode: str = "demo") -> FastAPI:
    app = FastAPI(title="CodeGuard Harness WebUI")

    sessions = {}

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": mode, "mock": mode == "demo"}

    @app.post("/session")
    async def create_session(scenario: str = "a"):
        session_id = str(uuid.uuid4())
        sessions[session_id] = _new_demo_session(scenario=scenario)
        return {"session_id": session_id, "scenario": scenario}

    @app.get("/session")
    async def session_entry(scenario: str = "a"):
        """Entry from scenario cards: create a session and go to dashboard."""
        session_id = str(uuid.uuid4())
        sessions[session_id] = _new_demo_session(scenario=scenario)
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
        sessions.setdefault(demo_session_id, _new_demo_session(scenario="demo"))
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

    @app.get("/approval")
    async def approval(request: Request, session: str = ""):
        """P3 approval modal (mock): pending action with risk summary + countdown."""
        demo_session_id = session or str(uuid.uuid4())
        sessions.setdefault(demo_session_id, _new_demo_session(scenario="demo"))
        return _templates.TemplateResponse(
            request=request,
            name="approval.html",
            context={
                "mock_mode": mode == "demo",
                "session_id": demo_session_id,
                "request": _MOCK_PENDING_REQUEST,
            },
        )

    @app.post("/session/{session_id}/approval")
    async def submit_approval(session_id: str, payload: ApprovalRequest):
        """Record an approval decision on the session (approve/reject)."""
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")
        if payload.decision not in ("approve", "reject"):
            raise HTTPException(status_code=400, detail="decision must be approve or reject")
        if session.get("pending_request") is None:
            session["pending_request"] = dict(_MOCK_PENDING_REQUEST)
        if session["pending_request"].get("request_id") != payload.request_id:
            raise HTTPException(status_code=409, detail="request mismatch")
        session["pending_request"]["decision"] = payload.decision
        if payload.decision == "approve":
            session["state"] = "EXECUTING"
        else:
            session["state"] = "CANCELLED"
        session["guardrail_decisions"].append(
            {
                "decision": "ALLOW" if payload.decision == "approve" else "BLOCK",
                "tool_call": {"command": "write_file", "args": {"path": "mock://workspace/src/auth.py"}, "result_ok": payload.decision == "approve"},
                "reasons": session["pending_request"]["reasons"],
                "impact": session["pending_request"]["impact"],
            }
        )
        return {"session_id": session_id, "request_id": payload.request_id, "decision": payload.decision}

    @app.get("/results")
    async def results(request: Request):
        """P4 session results + memory summary (mock)."""
        return _templates.TemplateResponse(
            request=request,
            name="results.html",
            context={
                "mock_mode": mode == "demo",
                "results": _MOCK_RESULTS,
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
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    return app


# Module-level app for `uvicorn.run("codeguard.web.app:app")` (web CLI / exe / Render)
app = create_app(mode="demo")
