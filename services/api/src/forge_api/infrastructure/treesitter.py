"""Tree-sitter based source parser for repository intelligence.

Implements ``TreeSitterParser`` for the Phase 1 languages (Python,
TypeScript, JavaScript, Rust, Go) on the tree-sitter 0.26 API:

- ``Language(capsule)`` wraps a grammar module's ``language()`` capsule.
- ``Parser(lang).parse(bytes)`` builds a syntax tree.
- ``QueryCursor(Query(lang, src)).captures(root)`` returns
  ``{capture_name: [Node, ...]}``.

Symbols are extracted by walking the concrete syntax tree so nesting
(class -> method) is preserved; dependencies are extracted per language
with small matchers over import/require/use nodes. Failures are
non-fatal and reported on ``ParseResult.errors``.
"""
import logging
from importlib import import_module

from tree_sitter import Language, Parser

from forge_api.domain.indexing import (
    DependencyKind,
    ParsedDependency,
    ParsedSymbol,
    ParseResult,
    SymbolKind,
)

logger = logging.getLogger(__name__)

# ─── Language loading ─────────────────────────────────────────────────


def _build_language(module_name: str, factory: str) -> Language | None:
    try:
        module = import_module(module_name)
        capsule = getattr(module, factory)()
        return Language(capsule)
    except Exception as exc:  # pragma: no cover - guarded at runtime
        logger.warning("Failed to load tree-sitter grammar %s: %s", module_name, exc)
        return None


class _GrammarRegistry:
    """Lazily loads grammars once and shares them across parses."""

    def __init__(self) -> None:
        self._languages: dict[str, Language | None] = {}

    def get(self, name: str) -> Language | None:
        if name not in self._languages:
            source = _GRAMMAR_SOURCES.get(name)
            if source is None:
                self._languages[name] = None
            else:
                self._languages[name] = _build_language(*source)
        return self._languages[name]


_GRAMMAR_SOURCES: dict[str, tuple[str, str]] = {
    "python": ("tree_sitter_python", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
    "javascript": ("tree_sitter_javascript", "language"),
    "rust": ("tree_sitter_rust", "language"),
    "go": ("tree_sitter_go", "language"),
}

_registry = _GrammarRegistry()


# ─── Language configuration ──────────────────────────────────────────

# Each config maps tree-sitter node types to symbol handling.
#   container_types: produce a container symbol (class/interface/enum/type)
#                    and treat function-like children as methods.
#   symbol_types:    produce a leaf symbol whose kind depends on context.
#   kind_map:        node type -> SymbolKind for container types.
#   pass_through:    node types that open a container scope but emit no symbol
#                    (e.g. Rust impl_item).
_CONFIGS: dict[str, dict] = {
    "python": {
        "container_types": {"class_definition"},
        "kind_map": {"class_definition": SymbolKind.CLASS},
        "symbol_types": {"function_definition"},
        "method_kinds": {"function_definition"},
        "pass_through": set(),
    },
    "typescript": {
        "container_types": {
            "class_declaration",
            "abstract_class_declaration",
            "interface_declaration",
            "enum_declaration",
            "type_alias_declaration",
        },
        "kind_map": {
            "class_declaration": SymbolKind.CLASS,
            "abstract_class_declaration": SymbolKind.CLASS,
            "interface_declaration": SymbolKind.INTERFACE,
            "enum_declaration": SymbolKind.ENUM,
            "type_alias_declaration": SymbolKind.TYPE,
        },
        "symbol_types": {"function_declaration", "method_definition"},
        "method_kinds": {"function_declaration", "method_definition"},
        "pass_through": set(),
    },
    "javascript": {
        "container_types": {"class_declaration"},
        "kind_map": {"class_declaration": SymbolKind.CLASS},
        "symbol_types": {"function_declaration", "method_definition"},
        "method_kinds": {"function_declaration", "method_definition"},
        "pass_through": set(),
    },
    "rust": {
        "container_types": {
            "struct_item",
            "enum_item",
            "trait_item",
            "union_item",
        },
        "kind_map": {
            "struct_item": SymbolKind.TYPE,
            "enum_item": SymbolKind.ENUM,
            "trait_item": SymbolKind.INTERFACE,
            "union_item": SymbolKind.TYPE,
        },
        "symbol_types": {"function_item", "const_item"},
        "method_kinds": {"function_item"},
        "pass_through": {"impl_item"},
    },
    "go": {
        "container_types": {"type_declaration"},
        "kind_map": {"type_declaration": SymbolKind.TYPE},
        "symbol_types": {"function_declaration", "method_declaration"},
        "method_kinds": {"function_declaration", "method_declaration"},
        "pass_through": set(),
    },
    "tsx": {},
}


def _decode(text: bytes) -> str:
    return text.decode("utf-8", errors="replace")


def _node_name(config: dict, node: object) -> str | None:
    """Return the symbol name for a node via its ``name`` field."""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _decode(name_node.text).strip()
    return name or None


def _node_signature(config: dict, node: object) -> str | None:
    """Return the first line of the node as a human-readable signature."""
    text = _decode(node.text).strip()
    if not text:
        return None
    first = text.splitlines()[0]
    return first[:2048] or None


def _node_range(node: object) -> tuple[int, int | None]:
    start = node.start_point.row + 1
    end = node.end_point.row + 1
    return start, end


def _collect_symbols(config: dict, node: object, in_container: bool = False) -> list:
    """Walk ``node`` and return nested ``ParsedSymbol`` trees."""
    symbols: list = []
    for child in node.named_children:
        ctype = child.type
        if ctype in config["pass_through"]:
            symbols.extend(_collect_symbols(config, child, in_container=True))
            continue
        if ctype in config["container_types"]:
            name = _node_name(config, child)
            if name is None:
                continue
            kind = config["kind_map"][ctype]
            start, end = _node_range(child)
            children = _collect_symbols(config, child, in_container=True)
            symbols.append(
                ParsedSymbol(
                    name=name,
                    kind=kind,
                    signature=_node_signature(config, child),
                    line_start=start,
                    line_end=end,
                    children=tuple(children),
                )
            )
            continue
        if ctype in config["symbol_types"]:
            name = _node_name(config, child)
            if name is None:
                continue
            if in_container and ctype in config["method_kinds"]:
                kind = SymbolKind.METHOD
            elif ctype in config["method_kinds"] and ctype in (
                "method_definition",
                "method_declaration",
            ):
                kind = SymbolKind.METHOD
            else:
                kind = SymbolKind.FUNCTION
            start, end = _node_range(child)
            symbols.append(
                ParsedSymbol(
                    name=name,
                    kind=kind,
                    signature=_node_signature(config, child),
                    line_start=start,
                    line_end=end,
                )
            )
            continue
        symbols.extend(_collect_symbols(config, child, in_container=in_container))
    return symbols


# ─── Dependency extraction ───────────────────────────────────────────


def _iter_descendants(node: object):
    stack = list(node.named_children)
    while stack:
        current = stack.pop()
        yield current
        stack.extend(current.named_children)


def _extract_python_deps(root: object) -> list[ParsedDependency]:
    deps: list[ParsedDependency] = []
    for n in _iter_descendants(root):
        if n.type == "import_statement":
            target = None
            for c in n.named_children:
                if c.type in ("dotted_name", "relative_import"):
                    target = _decode(c.text).strip()
                    break
            if target:
                deps.append(ParsedDependency(target, DependencyKind.IMPORT))
        elif n.type == "import_from_statement":
            mod = n.child_by_field_name("module_name")
            base = _decode(mod.text).strip() if mod else ""
            for c in n.children:
                if c.type == "relative_import":
                    dots = len(_decode(c.text).strip())
                    base = f"{'.' * dots}{base}" if base else "." * dots
                    break
            if base:
                deps.append(ParsedDependency(base, DependencyKind.FROM))
    return deps


def _quoted_argument(node: object) -> str | None:
    for c in _iter_descendants(node):
        if c.type == "string":
            text = _decode(c.text).strip().strip("\"'")
            if text:
                return text
    return None


def _extract_js_deps(root: object) -> list[ParsedDependency]:
    deps: list[ParsedDependency] = []
    for n in _iter_descendants(root):
        if n.type == "import_statement":
            source = n.child_by_field_name("source")
            if source is not None:
                text = _decode(source.text).strip().strip("\"'")
                if text:
                    deps.append(ParsedDependency(text, DependencyKind.IMPORT))
        elif n.type == "export_statement":
            source = n.child_by_field_name("source")
            if source is not None:
                text = _decode(source.text).strip().strip("\"'")
                if text:
                    deps.append(ParsedDependency(text, DependencyKind.IMPORT))
        elif n.type == "call_expression":
            func = n.child_by_field_name("function")
            if func is not None and _decode(func.text) == "require":
                target = _quoted_argument(n)
                if target:
                    deps.append(ParsedDependency(target, DependencyKind.REQUIRE))
        elif n.type == "import_require_clause":
            source = _decode(n.text).strip()
            target = source.replace("require", "").strip().strip("()\"'")
            if target:
                deps.append(ParsedDependency(target, DependencyKind.REQUIRE))
    return deps


def _extract_rust_deps(root: object) -> list[ParsedDependency]:
    deps: list[ParsedDependency] = []
    for n in _iter_descendants(root):
        if n.type != "use_declaration":
            continue
        # Take the first scoped/identifier path inside the use list.
        target = None
        for c in n.named_children:
            if c.type in ("scoped_identifier", "identifier"):
                target = _decode(c.text).strip()
                break
        if not target:
            continue
        # Keep only the leading crate path (drop `::{...}` segments).
        parts = target.split("::")
        cleaned = []
        for part in parts:
            if not part.isupper() and "{" not in part and "}" not in part:
                cleaned.append(part)
            else:
                break
        if cleaned and not all(p == "self" for p in cleaned):
            deps.append(ParsedDependency("::".join(cleaned), DependencyKind.USE))
    return deps


def _extract_go_deps(root: object) -> list[ParsedDependency]:
    deps: list[ParsedDependency] = []
    for n in _iter_descendants(root):
        if n.type != "import_spec":
            continue
        path = n.child_by_field_name("path")
        if path is not None:
            text = _decode(path.text).strip().strip("\"")
            if text:
                deps.append(ParsedDependency(text, DependencyKind.IMPORT))
            continue
        # Fall back to the first string literal child (grouped imports nest
        # import_spec inside an import_spec_list).
        for c in n.named_children:
            if c.type in ("interpreted_string_literal", "raw_string_literal"):
                text = _decode(c.text).strip().strip("\"")
                if text:
                    deps.append(ParsedDependency(text, DependencyKind.IMPORT))
                break
    return deps


_DEP_FACTORIES = {
    "python": _extract_python_deps,
    "typescript": _extract_js_deps,
    "tsx": _extract_js_deps,
    "javascript": _extract_js_deps,
    "rust": _extract_rust_deps,
    "go": _extract_go_deps,
}


# ─── Parser ──────────────────────────────────────────────────────────


class ForgeTreeSitterParser:
    """Concrete ``TreeSitterParser`` built on tree-sitter grammars."""

    def __init__(self) -> None:
        self._registry = _registry

    def parse(self, content: str, language: str) -> ParseResult:
        lang = self._registry.get(language)
        if lang is None:
            return ParseResult((), (), (f"language not available: {language}",))
        config = _config_for(language)
        try:
            tree = Parser(lang).parse(content.encode("utf-8"))
        except Exception as exc:
            logger.warning("tree-sitter parse failed for %s: %s", language, exc)
            return ParseResult((), (), (f"parse failed: {exc}",))
        root = tree.root_node
        symbols = _collect_symbols(config, root)
        dep_factory = _DEP_FACTORIES.get(language)
        deps = dep_factory(root) if dep_factory else []
        errors: tuple[str, ...] = ()
        if root.has_error:
            errors = ("syntax tree contains error nodes",)
        return ParseResult(
            symbols=tuple(symbols),
            dependencies=tuple(deps),
            errors=errors,
        )

    def supported_languages(self) -> set[str]:
        found = set()
        for name, (module_name, factory) in _GRAMMAR_SOURCES.items():
            try:
                module = import_module(module_name)
                getattr(module, factory)
                found.add(name)
            except Exception:
                continue
        return found


def _config_for(language: str) -> dict:
    if language == "tsx":
        return _CONFIGS["typescript"]
    return _CONFIGS.get(language, _CONFIGS["javascript"])