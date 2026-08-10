"""File discovery service unit tests using the in-memory git client."""
from forge_api.application.indexing.file_discovery_service import FileDiscoveryService


async def test_discover_files_filters_vendored(fake_git) -> None:
    fake_git.set_files(
        {
            "src/app.py": b"print(1)",
            "node_modules/lib/index.js": b"module.exports = 1",
            "src/logo.png": b"\x89PNG",
            ".git/config": b"",
            "README.md": b"hi",
        }
    )
    svc = FileDiscoveryService(git=fake_git, max_files=100)
    files = await svc.discover_files("/repo")
    paths = {f.path for f in files}
    assert "src/app.py" in paths
    assert "README.md" in paths
    assert "node_modules/lib/index.js" not in paths
    assert "src/logo.png" not in paths
    assert ".git/config" not in paths
    # language detected
    app = next(f for f in files if f.path == "src/app.py")
    assert app.language == "python"


async def test_discover_files_max_limit(fake_git) -> None:
    fake_git.set_files({f"f{i}.py": b"x" for i in range(50)})
    svc = FileDiscoveryService(git=fake_git, max_files=10)
    files = await svc.discover_files("/repo")
    assert len(files) == 10


async def test_diff_returns_entries(fake_git) -> None:
    from forge_api.domain.indexing import DiffEntry

    fake_git.set_diff([DiffEntry(status="M", path="a.py")])
    svc = FileDiscoveryService(git=fake_git, max_files=100)
    entries = await svc.diff("/repo", "b" * 40, "c" * 40)
    assert entries[0].path == "a.py"
    assert entries[0].status == "M"