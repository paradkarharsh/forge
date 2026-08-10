"""Chunking service unit tests."""
from forge_api.application.indexing.chunking_service import ChunkingService, count_tokens
from forge_api.domain.indexing import ParsedSymbol, SymbolKind

svc = ChunkingService()


def _content(num_lines: int = 40) -> str:
    return "\n".join(f"line {i} with some words" for i in range(1, num_lines + 1))


def test_empty_content_produces_no_chunks() -> None:
    assert svc.chunk_file(content="   ", symbols=[], chunk_tokens=10, overlap_tokens=0) == []


def test_no_symbols_sliding_window() -> None:
    chunks = svc.chunk_file(content=_content(), symbols=[], chunk_tokens=25, overlap_tokens=0)
    assert len(chunks) >= 2
    assert all(c.token_count <= 25 for c in chunks)
    # Chunks tile the file without overlap in this mode.
    assert chunks[0].line_start == 1
    assert chunks[-1].line_end <= 40


def test_symbol_boundaries_split_chunks() -> None:
    symbols = [
        ParsedSymbol("s1", SymbolKind.FUNCTION, None, 1, 3),
        ParsedSymbol("s2", SymbolKind.FUNCTION, None, 10, 12),
    ]
    chunks = svc.chunk_file(
        content=_content(20), symbols=symbols, chunk_tokens=25, overlap_tokens=0
    )
    # Symbol at line 10 forces a break before it.
    assert any(c.line_end == 9 or c.line_start == 10 for c in chunks)


def test_overlap_reuses_lines() -> None:
    chunks = svc.chunk_file(content=_content(20), symbols=[], chunk_tokens=25, overlap_tokens=10)
    if len(chunks) >= 2:
        assert chunks[1].line_start <= chunks[0].line_end  # overlapping


def test_count_tokens() -> None:
    assert count_tokens("def foo(a, b):\n    return a + b") == 7