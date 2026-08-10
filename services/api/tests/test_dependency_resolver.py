"""Dependency resolver unit tests."""
from forge_api.application.indexing.dependency_resolver import DependencyResolver

resolver = DependencyResolver()

REPO_FILES = {
    "src/app.py",
    "src/auth/service.py",
    "src/util/__init__.py",
    "lib/helpers.ts",
    "pkg/config/mod.rs",
}


def test_python_absolute_module_resolution() -> None:
    path, external = resolver.resolve(
        source_path="src/app.py",
        target_path="src.auth.service",
        repo_files=REPO_FILES,
        language="python",
    )
    assert path == "src/auth/service.py"
    assert external is False


def test_python_relative_import_resolution() -> None:
    path, external = resolver.resolve(
        source_path="src/auth/service.py",
        target_path="..util",
        repo_files=REPO_FILES,
        language="python",
    )
    assert path == "src/util/__init__.py"
    assert external is False


def test_python_external_module() -> None:
    path, external = resolver.resolve(
        source_path="src/app.py",
        target_path="os",
        repo_files=REPO_FILES,
        language="python",
    )
    assert path is None
    assert external is True


def test_js_relative_resolution() -> None:
    path, external = resolver.resolve(
        source_path="src/ui/index.ts",
        target_path="./helpers",
        repo_files=REPO_FILES,
        language="typescript",
    )
    assert path is None  # helpers.ts is under lib/, not src/ui
    assert external is True


def test_js_bare_specifier_external() -> None:
    path, external = resolver.resolve(
        source_path="src/app.py",
        target_path="react",
        repo_files=REPO_FILES,
        language="typescript",
    )
    assert external is True


def test_rust_crate_internal() -> None:
    path, external = resolver.resolve(
        source_path="pkg/main.rs",
        target_path="crate::config",
        repo_files=REPO_FILES,
        language="rust",
    )
    assert path == "pkg/config/mod.rs"
    assert external is False


def test_rust_external_crate() -> None:
    path, external = resolver.resolve(
        source_path="pkg/main.rs",
        target_path="serde",
        repo_files=REPO_FILES,
        language="rust",
    )
    assert external is True


def test_unknown_language_external() -> None:
    path, external = resolver.resolve(
        source_path="a.b", target_path="x", repo_files=REPO_FILES, language=None
    )
    assert path is None
    assert external is True