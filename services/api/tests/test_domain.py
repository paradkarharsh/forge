"""Domain model tests."""
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DatabaseError,
    DomainError,
    ForgeError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from forge_api.domain.sessions import SessionRecord
from forge_api.domain.users import UserRecord
from forge_api.domain.workspaces import WorkspaceRecord


class TestWorkspaceRole:
    def test_all_roles_exist(self) -> None:
        expected = {"owner", "admin", "member", "maintainer", "developer", "viewer"}
        actual = {r.value for r in WorkspaceRole}
        assert expected == actual


class TestDomainRecords:
    def test_session_record_is_frozen(self) -> None:
        now = datetime.now(UTC)
        record = SessionRecord(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            refresh_hash="abc",
            created_at=now,
            expires_at=now,
            revoked_at=None,
            replaced_at=None,
            last_active_at=now,
            device_name=None,
            ip_address=None,
            user_agent=None,
        )
        with pytest.raises(AttributeError):
            record.id = uuid4()  # type: ignore[misc]

    def test_user_record_is_frozen(self) -> None:
        record = UserRecord(
            id=uuid4(),
            email="a@b.com",
            password_hash=None,
            created_at=datetime.now(UTC),
        )
        with pytest.raises(AttributeError):
            record.email = "x"  # type: ignore[misc]

    def test_workspace_record_is_frozen(self) -> None:
        record = WorkspaceRecord(
            id=uuid4(),
            name="test",
            created_at=datetime.now(UTC),
            deleted_at=None,
        )
        with pytest.raises(AttributeError):
            record.name = "y"  # type: ignore[misc]


class TestErrorHierarchy:
    def test_all_errors_extend_forge_error(self) -> None:
        errors = [
            DomainError,
            ValidationError,
            AuthenticationError,
            AuthorizationError,
            NotFoundError,
            ConflictError,
            DatabaseError,
            ServiceUnavailableError,
        ]
        for cls in errors:
            assert issubclass(cls, ForgeError)

    def test_status_codes(self) -> None:
        assert AuthenticationError.status_code == 401
        assert AuthorizationError.status_code == 403
        assert NotFoundError.status_code == 404
        assert ConflictError.status_code == 409
        assert DomainError.status_code == 422
        assert ValidationError.status_code == 422
        assert DatabaseError.status_code == 500
        assert ServiceUnavailableError.status_code == 503

    def test_custom_code_override(self) -> None:
        err = ForgeError("msg", code="custom_code")
        assert err.code == "custom_code"
        assert str(err) == "msg"

    def test_details_field(self) -> None:
        err = ValidationError("bad", details={"field": "email"})
        assert err.details == {"field": "email"}
