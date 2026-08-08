from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
import sys
import uuid

if getattr(sys, "frozen", False):
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


# ---------------------------------------------------------------------------
# Scenario replay data — generated once from codeguard.demo runs
# ---------------------------------------------------------------------------

def _build_scenario_a_replay():
    """Run scenario A and capture deterministic trace/guardrail data."""
    from codeguard.demo.scenario_a import run_scenario_a
    result = run_scenario_a()
    frames = []
    for t in result.trace:
        frames.append({
            "state": t["to"].value if hasattr(t["to"], "value") else str(t["to"]),
            "description": "",
            "tool_call": None,
            "failed": False,
        })
    if result.guardrail_decisions:
        for i, d in enumerate(result.guardrail_decisions):
            dv = d.decision.value if hasattr(d.decision, "value") else str(d.decision)
            if i < len(frames):
                frames[i]["description"] = d.human_readable_message
                frames[i]["tool_call"] = {
                    "command": d.normalized_action.tool_name if d.normalized_action else "",
                    "args": d.normalized_action.normalized_parameters if d.normalized_action else {},
                    "result_ok": dv != "BLOCK",
                }
    return {
        "frames": frames,
        "guardrail_decisions": [
            {
                "decision": d.decision.value if hasattr(d.decision, "value") else str(d.decision),
                "tool_call": {
                    "command": d.normalized_action.tool_name if d.normalized_action else "",
                    "args": d.normalized_action.normalized_parameters if d.normalized_action else {},
                    "result_ok": (d.decision.value if hasattr(d.decision, "value") else str(d.decision)) != "BLOCK",
                },
                "reasons": [d.human_readable_message],
                "impact": "",
            }
            for d in result.guardrail_decisions
        ],
        "feedback_results": [],
        "steps_total": result.steps_total,
        "llm_calls_total": result.llm_calls_total,
    }


def _build_scenario_b_replay():
    """Run scenario B (approve) and capture deterministic replay data.
    B includes approve/reject/timeout branches: replay uses approve path."""
    from codeguard.demo.scenario_b import run_scenario_b_approve
    result = run_scenario_b_approve()
    frames = []
    for t in result.trace:
        frames.append({
            "state": t["to"].value if hasattr(t["to"], "value") else str(t["to"]),
            "description": "",
            "tool_call": None,
            "failed": False,
        })
    if result.guardrail_decisions:
        for i, d in enumerate(result.guardrail_decisions):
            dv = d.decision.value if hasattr(d.decision, "value") else str(d.decision)
            if i < len(frames):
                frames[i]["description"] = d.human_readable_message
                frames[i]["tool_call"] = {
                    "command": d.normalized_action.tool_name if d.normalized_action else "",
                    "args": d.normalized_action.normalized_parameters if d.normalized_action else {},
                    "result_ok": dv != "BLOCK",
                }
    return {
        "frames": frames,
        "guardrail_decisions": [
            {
                "decision": d.decision.value if hasattr(d.decision, "value") else str(d.decision),
                "tool_call": {
                    "command": d.normalized_action.tool_name if d.normalized_action else "",
                    "args": d.normalized_action.normalized_parameters if d.normalized_action else {},
                    "result_ok": (d.decision.value if hasattr(d.decision, "value") else str(d.decision)) != "BLOCK",
                },
                "reasons": [d.human_readable_message],
                "impact": "",
            }
            for d in result.guardrail_decisions
        ],
        "feedback_results": [],
        "steps_total": result.steps_total,
        "llm_calls_total": result.llm_calls_total,
    }


def _build_scenario_c_replay():
    """Run scenario C and capture deterministic trace/feedback data."""
    from codeguard.demo.scenario_c import run_scenario_c
    result = run_scenario_c()
    frames = []
    for t in result.trace:
        frames.append({
            "state": t["to"].value if hasattr(t["to"], "value") else str(t["to"]),
            "description": "",
            "tool_call": None,
            "failed": False,
        })
    if result.guardrail_decisions:
        for i, d in enumerate(result.guardrail_decisions):
            dv = d.decision.value if hasattr(d.decision, "value") else str(d.decision)
            if i < len(frames):
                frames[i]["description"] = d.human_readable_message
                frames[i]["tool_call"] = {
                    "command": d.normalized_action.tool_name if d.normalized_action else "",
                    "args": d.normalized_action.normalized_parameters if d.normalized_action else {},
                    "result_ok": dv != "BLOCK",
                }
    # Mark failed state frames
    for fb in result.feedback_results:
        fb_status = getattr(fb, "status", "")
        if hasattr(fb_status, "value"):
            fb_status = fb_status.value
        if "FAILED" in str(fb_status).upper():
            # mark first EXECUTING/INTERMEDIATE_VALIDATION frame as failed
            for f in frames:
                if f["state"] == "intermediate_validation":
                    f["failed"] = True
                    f["failure_category"] = "TEST_ASSERTION_FAILURE"
                    break
    return {
        "frames": frames,
        "guardrail_decisions": [
            {
                "decision": d.decision.value if hasattr(d.decision, "value") else str(d.decision),
                "tool_call": {
                    "command": d.normalized_action.tool_name if d.normalized_action else "",
                    "args": d.normalized_action.normalized_parameters if d.normalized_action else {},
                    "result_ok": (d.decision.value if hasattr(d.decision, "value") else str(d.decision)) != "BLOCK",
                },
                "reasons": [d.human_readable_message],
                "impact": "",
            }
            for d in result.guardrail_decisions
        ],
        "feedback_results": [
            {"status": getattr(f, "status", "").value if hasattr(getattr(f, "status", ""), "value")
             else str(getattr(f, "status", "")),
             "summary": getattr(f, "summary", "")}
            for f in result.feedback_results
        ],
        "steps_total": result.steps_total,
        "llm_calls_total": result.llm_calls_total,
    }


_SCENARIO_BUILDERS = {
    "a": _build_scenario_a_replay,
    "b": _build_scenario_b_replay,
    "c": _build_scenario_c_replay,
}

_SCENARIO_LABELS = {
    "a": "场景 A · 路径逃逸被 BLOCK",
    "b": "场景 B · 副作用动作待审批",
    "c": "场景 C · 测试失败反馈闭环",
}
_BACKWARD_LABEL_MAP = {
    # Map SPEC scenario letters to their full Chinese label for the nav bar.
    # Used when the session hasn't been created yet (no scenario data).
    "a": "场景 A · 路径逃逸被 BLOCK",
    "b": "场景 B · 副作用动作待审批",
    "c": "场景 C · 测试失败反馈闭环",
}


def _new_demo_session(scenario: str = "demo") -> dict:
    """Create an in-memory demo session with pre-built replay data."""
    builder = _SCENARIO_BUILDERS.get(scenario)
    replay = builder() if builder else {"frames": [], "guardrail_decisions": [],
                                         "feedback_results": [], "steps_total": 0,
                                         "llm_calls_total": 0}
    return {
        "scenario": scenario,
        "state": "INITIALIZING",
        "current_step": 0,
        "trace": [],
        "guardrail_decisions": [],
        "feedback_results": replay["feedback_results"],  # surface for tests
        "pending_request": None,
        "_replay_feedback": replay["feedback_results"],
        "replay_frames": replay["frames"],
        "replay_guardrail_decisions": replay["guardrail_decisions"],
        "replay_feedback_results": replay["feedback_results"],
        "steps_total": replay["steps_total"],
        "llm_calls_total": replay["llm_calls_total"],
    }


def create_app(mode: str = "demo") -> FastAPI:
    app = FastAPI(title="CodeGuard Harness WebUI")

    sessions = {}

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": mode, "mock": mode == "demo"}

    @app.post("/session")
    async def create_session(request: Request):
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        scenario = body.get("scenario", "a")
        session_id = str(uuid.uuid4())
        sessions[session_id] = _new_demo_session(scenario=scenario)
        return {"session_id": session_id, "scenario": scenario}

    @app.get("/session")
    async def session_entry(request: Request, scenario: str = "a"):
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
        demo_session_id = session or str(uuid.uuid4())
        sessions.setdefault(demo_session_id, _new_demo_session(scenario="demo"))
        sesh = sessions.get(demo_session_id, {})
        sc = sesh.get("scenario", "demo")
        # If scenario letter was passed as query param, use it
        if not session:
            sc = "demo"
        label = _SCENARIO_LABELS.get(sc, _SCENARIO_LABELS.get(sc, "演示回放"))
        return _templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "mock_mode": mode == "demo",
                "session_id": demo_session_id,
                "scenario": sc,
                "scenario_label": label,
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
        demo_session_id = session or str(uuid.uuid4())
        sessions.setdefault(demo_session_id, _new_demo_session(scenario="demo"))
        sesh = sessions.get(demo_session_id, {})
        sc = sesh.get("scenario", "b")
        return _templates.TemplateResponse(
            request=request,
            name="approval.html",
            context={
                "mock_mode": mode == "demo",
                "session_id": demo_session_id,
                "scenario": sc,
                "scenario_label": _SCENARIO_LABELS.get(sc, "场景 B · 副作用动作待审批"),
                "request": _MOCK_PENDING_REQUEST,
            },
        )

    @app.post("/session/{session_id}/approval")
    async def submit_approval(session_id: str, payload: ApprovalRequest):
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
        session["guardrail_decisions"].append({
            "decision": "ALLOW" if payload.decision == "approve" else "BLOCK",
            "tool_call": {"command": "write_file", "args": {"path": "mock://workspace/src/auth.py"},
                          "result_ok": payload.decision == "approve"},
            "reasons": session["pending_request"]["reasons"],
            "impact": session["pending_request"]["impact"],
        })
        return {"session_id": session_id, "request_id": payload.request_id, "decision": payload.decision}

    @app.get("/results")
    async def results(request: Request):
        return _templates.TemplateResponse(
            request=request,
            name="results.html",
            context={
                "mock_mode": mode == "demo",
                "results": _MOCK_RESULTS,
                "scenario": "c",
                "scenario_label": _SCENARIO_LABELS.get("c", "场景 C · 测试失败反馈闭环"),
            },
        )

    # ------------------------------------------------------------------
    # Session state (for polling)
    # ------------------------------------------------------------------

    @app.get("/session/{session_id}/state")
    async def get_session_state(session_id: str):
        session = sessions.get(session_id)
        if not session:
            return {"error": "session not found"}
        return _session_state_response(session_id, session)

    # ------------------------------------------------------------------
    # Step / Replay — backend is the sole source of truth
    # ------------------------------------------------------------------

    @app.post("/session/{session_id}/step")
    async def step_session(session_id: str):
        """Advance the session by one replay frame. Returns updated state."""
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")

        frames = session.get("replay_frames", [])
        idx = session.get("current_step", 0)

        # Check if already terminal
        TERMINAL = {"completed", "failed", "cancelled", "limit_reached"}
        if session.get("state", "").lower() in TERMINAL:
            return _session_state_response(session_id, session)

        if idx >= len(frames):
            return _session_state_response(session_id, session)

        # If AWAITING_APPROVAL and no decision yet, don't auto-advance
        if session.get("state", "") == "AWAITING_APPROVAL":
            return _session_state_response(session_id, session)

        frame = frames[idx]
        new_state = frame["state"].upper()

        # Skip INITIALIZING and BUILDING_CONTEXT (first frame from replay)
        if new_state == "INITIALIZING" or new_state == "BUILDING_CONTEXT":
            session["current_step"] = idx + 1
            # If first step, set state to BUILDING_CONTEXT and continue
            if new_state == "BUILDING_CONTEXT":
                session["state"] = "BUILDING_CONTEXT"
            return _session_state_response(session_id, session)

        prev_state = session.get("state", "INITIALIZING")
        session["current_step"] = idx + 1
        session["state"] = new_state
        entry = {
            "from": prev_state,
            "to": new_state,
            "at": "",
        }

        # Carry forward frame metadata: failed flag, failure_category,
        # description, tool_call so they appear in the trace visible
        # to the frontend.
        for field in ("failed", "failure_category"):
            if frame.get(field):
                entry[field] = frame[field]
        if frame.get("description"):
            entry["description"] = frame["description"]
        if frame.get("tool_call"):
            entry["tool_call"] = frame["tool_call"]

        # Annotate INTERMEDIATE_VALIDATION frames with feedback summaries
        if new_state == "INTERMEDIATE_VALIDATION":
            fb_results = session.get("_replay_feedback",
                                     session.get("replay_feedback_results", []))
            visited = session.get("_fb_visited", 0)
            if visited < len(fb_results):
                fb_data = fb_results[visited]
                entry["description"] = fb_data.get("summary", "")
                entry["failed"] = "FAILED" in str(fb_data.get("status", "")).upper()
                entry["failure_category"] = (
                    "TEST_FAILURE" if entry["failed"] else ""
                )
                session["_fb_visited"] = visited + 1

        session["trace"].append(entry)

        # Bring in the NEXT guardrail decision when hitting a GOVERNING frame.
        # GRs accumulate: first GOVERNING → GR[0], second GOVERNING → GR[0]+GR[1].
        # Also annotate the trace entry with the GR info.
        if new_state == "GOVERNING":
            all_gr = session.get("replay_guardrail_decisions", [])
            gr_idx = session.get("_gr_cursor", 0)
            if gr_idx < len(all_gr):
                gr_data = all_gr[gr_idx]
                session["guardrail_decisions"].append(gr_data)
                session["_gr_cursor"] = gr_idx + 1
                # Annotate the trace entry we just appended
                if session["trace"]:
                    last_trace = session["trace"][-1]
                    last_trace["guardrail_decision"] = gr_data.get("decision", "")
                    last_trace["guardrail_reasons"] = gr_data.get("reasons", [])
                    last_trace["tool_call"] = gr_data.get("tool_call")
                    last_trace["description"] = (
                        gr_data.get("reasons", ["Allocated"])[0]
                        if gr_data.get("reasons") else "Allocated"
                    )

        # Set pending_request for scenario B AWAITING_APPROVAL
        if new_state == "AWAITING_APPROVAL":
            session["pending_request"] = dict(_MOCK_PENDING_REQUEST)

        return _session_state_response(session_id, session)

    @app.post("/session/{session_id}/replay")
    async def replay_session(session_id: str):
        """Reset session to INITIALIZING and clear all accumulated state."""
        session = sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session not found")

        scenario = session.get("scenario", "demo")
        sessions[session_id] = _new_demo_session(scenario=scenario)
        return _session_state_response(session_id, sessions[session_id])

    # Mount static files AFTER all routes
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    return app


def _session_state_response(session_id: str, session: dict) -> dict:
    """Build the standard state response dict."""
    fb = session.get("feedback_results", [])
    if not fb:
        fb = session.get("_replay_feedback",
                         session.get("replay_feedback_results", []))
    return {
        "session_id": session_id,
        "scenario": session.get("scenario", ""),
        "state": session.get("state", "INITIALIZING"),
        "current_step": session.get("current_step", 0),
        "trace": session.get("trace", []),
        "guardrail_decisions": session.get("guardrail_decisions", []),
        "feedback_results": fb,
        "steps_total": session.get("steps_total", 0),
        "llm_calls_total": session.get("llm_calls_total", 0),
        "pending_approval": session.get("state", "") == "AWAITING_APPROVAL",
        "approval_request": session.get("pending_request") if session.get("state", "") == "AWAITING_APPROVAL" else None,
    }


# Module-level app for `uvicorn.run("codeguard.web.app:app")` (web CLI / exe / Render)
app = create_app(mode="demo")
