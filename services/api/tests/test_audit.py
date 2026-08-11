"""Audit system tests.

Verifies that AuditLogger produces correct AuditEventModel records and
that the domain AuditEvent dataclass carries the full context.
"""
from uuid import uuid4

from forge_api.domain.audit import AuditEvent, AuditEventType


class TestAuditEvent:
    def test_event_carries_full_context(self) -> None:
        user_id = uuid4()
        session_id = uuid4()
        event = AuditEvent(
            event=AuditEventType.LOGIN,
            user_id=user_id,
            session_id=session_id,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            reason="credential login",
            payload={"browser": "chrome"},
        )
        assert event.event == AuditEventType.LOGIN
        assert event.user_id == user_id
        assert event.session_id == session_id
        assert event.ip_address == "192.168.1.1"
        assert event.user_agent == "Mozilla/5.0"
        assert event.reason == "credential login"
        assert event.payload == {"browser": "chrome"}

    def test_event_defaults_to_none(self) -> None:
        event = AuditEvent(event=AuditEventType.SESSION_CLEANED)
        assert event.user_id is None
        assert event.session_id is None
        assert event.ip_address is None
        assert event.user_agent is None
        assert event.reason is None
        assert event.payload is None

    def test_event_is_frozen(self) -> None:
        event = AuditEvent(event=AuditEventType.LOGIN)
        import dataclasses

        assert dataclasses.is_dataclass(event)
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            event.event = AuditEventType.LOGOUT  # type: ignore[misc]


class TestAuditEventTypes:
    def test_all_event_types_are_namespaced(self) -> None:
        for member in AuditEventType:
            assert "." in member.value, f"{member.name} should be namespaced"

    def test_expected_events_exist(self) -> None:
        expected = {
            "auth.login",
            "auth.register",
            "auth.logout",
            "auth.logout_all",
            "auth.refresh_rotated",
            "auth.refresh_reuse_detected",
            "auth.session_revoked",
            "auth.session_expired",
            "auth.session_cleaned",
            "oauth.authorize",
            "oauth.callback",
            "oauth.state_mismatch",
            "oauth.nonce_mismatch",
            "oauth.profile_invalid",
            "workspace.created",
            "workspace.renamed",
            "workspace.deleted",
            "workspace.updated",
            "workspace.member_added",
            "workspace.member_removed",
            "workspace.member_role_changed",
            "repository.created",
            "repository.imported",
            "repository.cloned",
            "repository.updated",
            "repository.archived",
            "repository.restored",
            "repository.deleted",
            "repository.indexed",
            "repository.reindexed",
            "memory.created",
            "memory.updated",
            "memory.deleted",
            "memory.archived",
            "memory.stale_marked",
            "memory.searched",
            "context.assembled",
        }
        actual = {member.value for member in AuditEventType}
        assert expected == actual


class TestFakeAuditLogger:
    def test_log_collects_events(self, fake_audit) -> None:
        fake_audit.log(
            AuditEventType.LOGIN,
            user_id=uuid4(),
            ip_address="1.2.3.4",
        )
        assert len(fake_audit.events) == 1
        assert fake_audit.events[0]["event"] == AuditEventType.LOGIN
        assert fake_audit.events[0]["ip_address"] == "1.2.3.4"
