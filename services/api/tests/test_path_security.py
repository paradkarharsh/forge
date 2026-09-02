"""Unit and security tests for path containment and secret redaction."""
import os
import tempfile
from pathlib import Path

import pytest

from forge_api.domain.errors import ValidationError
from forge_api.domain.tool import (
    redact_secrets,
    safe_resolve_repo_path,
)


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir).resolve()
        # Create standard structure
        (repo_path / "src").mkdir()
        (repo_path / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
        (repo_path / ".git").mkdir()
        (repo_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        yield repo_path


class TestPathContainment:
    def test_valid_relative_paths(self, temp_repo: Path) -> None:
        p1 = safe_resolve_repo_path(temp_repo, "src/main.py")
        assert p1 == temp_repo / "src" / "main.py"

        p2 = safe_resolve_repo_path(temp_repo, "new_file.txt")
        assert p2 == temp_repo / "new_file.txt"

        p3 = safe_resolve_repo_path(temp_repo, "src/deep/nested/path.py")
        assert p3 == temp_repo / "src" / "deep" / "nested" / "path.py"

    def test_reject_empty_and_null_bytes(self, temp_repo: Path) -> None:
        with pytest.raises(ValidationError):
            safe_resolve_repo_path(temp_repo, "")

        with pytest.raises(ValidationError):
            safe_resolve_repo_path(temp_repo, "   ")

        with pytest.raises(ValidationError):
            safe_resolve_repo_path(temp_repo, "file\0.txt")

    @pytest.mark.parametrize(
        "bad_path",
        [
            "/etc/passwd",
            "/var/log",
            "C:\\Windows\\System32",
            "C:/boot.ini",
            "D:\\secret.txt",
            "\\server\\share\\file.txt",
        ],
    )
    def test_reject_absolute_paths(self, temp_repo: Path, bad_path: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            safe_resolve_repo_path(temp_repo, bad_path)
        assert exc_info.value.code == "path_traversal"

    @pytest.mark.parametrize(
        "bad_path",
        [
            "../outside.txt",
            "src/../../outside.txt",
            "a/b/c/../../../../etc/passwd",
            "..\\outside.txt",
            "src\\..\\..\\outside.txt",
        ],
    )
    def test_reject_path_traversal(self, temp_repo: Path, bad_path: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            safe_resolve_repo_path(temp_repo, bad_path)
        assert exc_info.value.code == "path_traversal"

    @pytest.mark.parametrize(
        "git_path",
        [
            ".git",
            ".git/config",
            ".git/HEAD",
            "src/.git",
            "submodule/.git/config",
            ".GIT",
            ".Git/HEAD",
        ],
    )
    def test_reject_git_directory_access(
        self, temp_repo: Path, git_path: str
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            safe_resolve_repo_path(temp_repo, git_path)
        assert exc_info.value.code == "forbidden_path"

    def test_reject_symlink_escaping_repository(self, temp_repo: Path) -> None:
        with tempfile.TemporaryDirectory() as external_dir:
            secret_file = Path(external_dir) / "secret.txt"
            secret_file.write_text("confidential", encoding="utf-8")

            symlink_path = temp_repo / "symlink_to_external"
            try:
                os.symlink(external_dir, symlink_path, target_is_directory=True)
            except (OSError, NotImplementedError):
                pytest.skip("Symlink creation not permitted in this environment.")

            with pytest.raises(ValidationError) as exc_info:
                safe_resolve_repo_path(temp_repo, "symlink_to_external/secret.txt")
            assert exc_info.value.code == "symlink_escape"


class TestSecretRedaction:
    def test_redact_bearer_token(self) -> None:
        token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        raw = f"Authorization: Bearer {token} in headers"
        redacted = redact_secrets(raw)

        assert "eyJhbGci" not in redacted
        assert "[REDACTED_TOKEN]" in redacted

    def test_redact_api_keys(self) -> None:
        raw = "Using key sk-1234567890abcdef1234567890abcdef for OpenAI"
        redacted = redact_secrets(raw)
        assert "sk-1234567890abcdef" not in redacted
        assert "[REDACTED_API_KEY]" in redacted

    def test_redact_github_tokens(self) -> None:
        raw = "Token is ghp_123456789012345678901234567890123456"
        redacted = redact_secrets(raw)
        assert "ghp_12345678" not in redacted
        assert "[REDACTED_GITHUB_TOKEN]" in redacted

    def test_redact_database_url_passwords(self) -> None:
        raw = "postgres://postgres:SuperSecretPassword123@db.internal:5432/forgedb"
        redacted = redact_secrets(raw)
        assert "SuperSecretPassword123" not in redacted
        assert "postgres://postgres:[REDACTED]@db.internal:5432/forgedb" in redacted

    def test_redact_private_keys(self) -> None:
        raw = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        redacted = redact_secrets(raw)
        assert "MIIEowIBAAKCAQEA0" not in redacted
        assert "[REDACTED_PRIVATE_KEY]" in redacted
