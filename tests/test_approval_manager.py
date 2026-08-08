import pytest
from datetime import datetime, timedelta
from codeguard.action import ActionKind, NormalizedAction
from codeguard.guardrail.approval import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    FakeClock,
)


def _make_na(fingerprint="fp123"):
    return NormalizedAction(
        kind=ActionKind.TOOL_CALL,
        tool_name="write_file",
        normalized_parameters={"path": "output.txt"},
        action_fingerprint=fingerprint,
        original_raw="",
        normalized_at=datetime(2026, 1, 1, 12, 0, 0),
    )


class TestCreateRequest:
    def test_creates_with_correct_fields(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        na = _make_na()
        req = mgr.create_request(
            session_id="s1", normalized_action=na,
            matched_rules=["risk_rule"], risk_summary="写入项目目录",
        )
        assert req.request_id is not None
        assert len(req.request_id) > 0
        assert req.session_id == "s1"
        assert req.status == ApprovalStatus.PENDING
        assert req.action_fingerprint == "fp123"
        assert req.matched_rules == ["risk_rule"]
        assert req.risk_summary == "写入项目目录"
        assert req.created_at == datetime(2026, 1, 1, 12, 0, 0)
        assert req.expires_at == datetime(2026, 1, 1, 12, 1, 0)

    def test_each_request_has_unique_id(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        na = _make_na()
        r1 = mgr.create_request("s1", na, [], "")
        r2 = mgr.create_request("s1", na, [], "")
        assert r1.request_id != r2.request_id


class TestApprove:
    def test_approve_success(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        na = _make_na()
        req = mgr.create_request("s1", na, [], "")
        result = mgr.approve(req.request_id, session_id="s1", action_fingerprint="fp123")
        assert result.decision == ApprovalStatus.APPROVED
        assert result.request_id == req.request_id
        assert req.status == ApprovalStatus.APPROVED

    def test_approve_wrong_session_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        with pytest.raises(ValueError, match="Session"):
            mgr.approve(req.request_id, session_id="other", action_fingerprint="fp123")

    def test_approve_wrong_fingerprint_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        with pytest.raises(ValueError, match="fingerprint"):
            mgr.approve(req.request_id, session_id="s1", action_fingerprint="wrong_fp")

    def test_approve_expired_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=5)
        req = mgr.create_request("s1", _make_na(), [], "")
        clock.advance(10)
        with pytest.raises(ValueError, match="expired"):
            mgr.approve(req.request_id, session_id="s1", action_fingerprint="fp123")

    def test_approve_unknown_request_raises(self):
        mgr = ApprovalManager(approval_timeout=60)
        with pytest.raises(ValueError, match="Unknown"):
            mgr.approve("nonexistent", session_id="s1", action_fingerprint="fp")

    def test_approve_already_approved_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        mgr.approve(req.request_id, "s1", "fp123")
        with pytest.raises(ValueError, match="already"):
            mgr.approve(req.request_id, session_id="s1", action_fingerprint="fp123")

    def test_approve_already_rejected_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        mgr.reject(req.request_id, "s1")
        with pytest.raises(ValueError, match="already"):
            mgr.approve(req.request_id, session_id="s1", action_fingerprint="fp123")

    def test_approve_timed_out_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=5)
        req = mgr.create_request("s1", _make_na(), [], "")
        clock.advance(10)
        mgr.check_timeout(req)
        with pytest.raises(ValueError, match="already"):
            mgr.approve(req.request_id, session_id="s1", action_fingerprint="fp123")


class TestReject:
    def test_reject_success(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        result = mgr.reject(req.request_id, session_id="s1")
        assert result.decision == ApprovalStatus.REJECTED
        assert req.status == ApprovalStatus.REJECTED

    def test_reject_wrong_session_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        with pytest.raises(ValueError, match="Session"):
            mgr.reject(req.request_id, session_id="other")

    def test_reject_expired_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=5)
        req = mgr.create_request("s1", _make_na(), [], "")
        clock.advance(10)
        with pytest.raises(ValueError, match="expired"):
            mgr.reject(req.request_id, session_id="s1")

    def test_reject_unknown_request_raises(self):
        mgr = ApprovalManager(approval_timeout=60)
        with pytest.raises(ValueError, match="Unknown"):
            mgr.reject("nonexistent", session_id="s1")

    def test_reject_already_rejected_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        mgr.reject(req.request_id, "s1")
        with pytest.raises(ValueError, match="already"):
            mgr.reject(req.request_id, session_id="s1")

    def test_reject_already_approved_raises(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        mgr.approve(req.request_id, "s1", "fp123")
        with pytest.raises(ValueError, match="already"):
            mgr.reject(req.request_id, session_id="s1")


class TestTimeout:
    def test_check_timeout_when_expired(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        clock.advance(61)
        result = mgr.check_timeout(req)
        assert result.decision == ApprovalStatus.TIMEOUT
        assert req.status == ApprovalStatus.TIMEOUT

    def test_check_timeout_at_exact_expiry(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        clock.advance(60)  # exactly at expires_at
        result = mgr.check_timeout(req)
        assert result.decision == ApprovalStatus.TIMEOUT

    def test_check_timeout_before_expiry_returns_none(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        clock.advance(30)
        result = mgr.check_timeout(req)
        assert result is None
        assert req.status == ApprovalStatus.PENDING

    def test_check_timeout_non_pending_ignored(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        req = mgr.create_request("s1", _make_na(), [], "")
        mgr.approve(req.request_id, "s1", "fp123")
        clock.advance(120)
        result = mgr.check_timeout(req)
        assert result is None
        assert req.status == ApprovalStatus.APPROVED


class TestMultipleRequests:
    def test_independent_requests(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        mgr = ApprovalManager(clock=clock, approval_timeout=60)
        r1 = mgr.create_request("s1", _make_na("fp1"), [], "")
        r2 = mgr.create_request("s2", _make_na("fp2"), [], "")
        mgr.approve(r1.request_id, "s1", "fp1")
        mgr.reject(r2.request_id, "s2")
        assert r1.status == ApprovalStatus.APPROVED
        assert r2.status == ApprovalStatus.REJECTED


class TestFakeClock:
    def test_advance_is_deterministic(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        clock.advance(30)
        assert clock.now == datetime(2026, 1, 1, 12, 0, 30)
        clock.advance(30)
        assert clock.now == datetime(2026, 1, 1, 12, 1, 0)

    def test_is_expired_exact_boundary(self):
        clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0))
        deadline = datetime(2026, 1, 1, 12, 1, 0)
        assert clock.is_expired(deadline) is False
        clock.advance(60)
        assert clock.is_expired(deadline) is True

    def test_default_now(self):
        clock = FakeClock()
        assert isinstance(clock.now, datetime)