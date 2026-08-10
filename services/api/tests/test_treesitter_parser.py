"""Tree-sitter parser unit tests across the Phase 1 languages."""
from forge_api.domain.indexing import SymbolKind
from forge_api.infrastructure.treesitter import ForgeTreeSitterParser


def test_python_symbols_and_dependencies() -> None:
    parser = ForgeTreeSitterParser()
    result = parser.parse(
        """import os
from pathlib import Path

def add(a, b):
    return a + b

class Foo:
    def bar(self):
        return 1
""",
        "python",
    )
    names = [(s.kind, s.name) for s in result.symbols]
    assert (SymbolKind.FUNCTION, "add") in names
    foo = next(s for s in result.symbols if s.name == "Foo")
    assert foo.kind == SymbolKind.CLASS
    assert [(c.kind, c.name) for c in foo.children] == [(SymbolKind.METHOD, "bar")]
    targets = {d.target_path for d in result.dependencies}
    assert "os" in targets
    assert "pathlib" in targets


def test_python_relative_import_depth() -> None:
    parser = ForgeTreeSitterParser()
    result = parser.parse(
        "from ..util import helper\n",
        "python",
    )
    assert any(d.target_path.startswith("..") for d in result.dependencies)


def test_typescript_symbols_and_dependencies() -> None:
    parser = ForgeTreeSitterParser()
    result = parser.parse(
        '''import { readFile } from "fs";
import path from "node:path";

export interface User { id: number }
export class Service {
  run(): void {}
}
function helper(): void {}
''',
        "typescript",
    )
    kinds = {s.name: s.kind for s in result.symbols}
    assert kinds.get("Service") == SymbolKind.CLASS
    assert kinds.get("User") == SymbolKind.INTERFACE
    service = next(s for s in result.symbols if s.name == "Service")
    assert [(c.name, c.kind) for c in service.children] == [("run", SymbolKind.METHOD)]
    targets = {d.target_path for d in result.dependencies}
    assert "fs" in targets
    assert "node:path" in targets


def test_typescript_jsx_req() -> None:
    parser = ForgeTreeSitterParser()
    result = parser.parse('const x = require("lodash");\n', "javascript")
    assert any(
        d.target_path == "lodash" and d.kind.value == "require"
        for d in result.dependencies
    )


def test_rust_symbols_and_dependencies() -> None:
    parser = ForgeTreeSitterParser()
    result = parser.parse(
        """use std::collections::HashMap;

pub fn run() -> i32 { 1 }
pub struct Point { x: i32, y: i32 }
impl Point {
    fn dist(&self) -> i32 { 0 }
}
pub enum Color { Red, Green }
""",
        "rust",
    )
    kinds = {s.name: s.kind for s in result.symbols}
    assert kinds.get("run") == SymbolKind.FUNCTION
    assert kinds.get("Point") == SymbolKind.TYPE
    assert kinds.get("Color") == SymbolKind.ENUM
    assert any(d.target_path == "std::collections::HashMap" for d in result.dependencies)


def test_go_symbols_and_dependencies() -> None:
    parser = ForgeTreeSitterParser()
    result = parser.parse(
        """package main

import (
\t"fmt"
)

func main() {}
type Server struct { port int }
func (s *Server) Start() {}
""",
        "go",
    )
    kinds = {s.name: s.kind for s in result.symbols}
    assert kinds.get("main") == SymbolKind.FUNCTION
    assert kinds.get("Start") == SymbolKind.METHOD
    assert any(d.target_path == "fmt" for d in result.dependencies)


def test_unsupported_language_returns_error_not_exception() -> None:
    parser = ForgeTreeSitterParser()
    result = parser.parse("some text", "klingon")
    assert result.errors
    assert result.symbols == ()


def test_malformed_content_is_non_fatal() -> None:
    parser = ForgeTreeSitterParser()
    result = parser.parse("def (\n))))))", "python")
    # Errors may be reported, but parsing never raises.
    assert isinstance(result.symbols, tuple)


def test_supported_languages_include_phase1() -> None:
    parser = ForgeTreeSitterParser()
    supported = parser.supported_languages()
    assert {"python", "typescript", "javascript", "rust", "go"} <= supported