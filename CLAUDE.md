# CodeGuard Harness — Claude Code Instructions

## Project overview

CodeGuard Harness is a Python 3.12 CLI Coding Agent Harness for Windows. It implements agent loop, tool dispatch, governance guardrails, feedback loop, memory, and configuration from scratch. Key focus: governance guardrails + test feedback loop.

## Design references

- WebUI design follows Open Design Vercel Design System (DESIGN.md)
- Open Design is a design-time tool only; WebUI is implemented with FastAPI + Jinja2 + HTML/CSS + vanilla JS
- No React, Node.js, or Open Design runtime dependencies in the deliverable

## Project logging protocol

- Each new session: read CLAUDE.md, SPEC.md, PLAN.md (if exists), SPEC_PROCESS.md, AGENT_LOG.md (last 100 lines), then check `git status`, current branch, and last 5 commits.
- AGENT_LOG.md: append only. Never delete or rewrite history. If old records are wrong, append a CORRECTED entry.
- Before each PLAN task: append STARTED log with task_id, branch/worktree, skill, goal, and verification command.
- TDD RED phase: log command, exit code, and failure summary. TDD GREEN phase: log command, exit code, and pass count.
- After subagent completes: log agent type, task, key output, two-phase review result, and manual edits.
- After commit/PR: append real commit hash, PR URL, and CI status. Never predict or fabricate.
- Before claiming task completion: verify AGENT_LOG and PLAN are updated, tests re-run, `git diff`/`git status` checked.
- If log update fails or contradicts Git/test state, do NOT claim completion.
- Do NOT commit `.claude/projects/` local machine memory files.

## Push policy

Every commit must be pushed to BOTH remotes:
- `origin` (NJU GitLab): `https://git.nju.edu.cn/241880437/ai4sepa.git`
- `github` (GitHub mirror): `https://github.com/liwenze-NJU/AI4SE_projectA.git`

## Specification references

- `SPEC.md` — Design specification (v1.1, pending final user confirmation)
- `SPEC_PROCESS.md` — Design process record (brainstorming rounds 1-12)
- `AGENT_LOG.md` — Development process log
- `PLAN.md` — Implementation plan (to be created after spec confirmation)

## Design guardrails

- All core mechanisms must be implemented as code, not prompts
- Guardrail uses default-deny policy; unregistered tools and unknown actions are BLOCK'd
- Shell execution uses structured program+args, never shell=True
- All credentials stored via Windows Credential Manager + keyring
- WebUI demo mode runs real harness core with Mock external boundaries only
- Tests use ScriptedMockLLM (no real LLM, no network, no API keys)