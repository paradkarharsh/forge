"""Symbol-aware file chunking for embedding.

Splits file content into chunks that respect symbol boundaries where
possible, falling back to a sliding window for code without symbols.
Chunking is pure logic: no I/O, no dependencies on persistence.
"""
from forge_api.domain.indexing import Chunk, ParsedSymbol


def count_tokens(text: str) -> int:
    """Approximate token count using whitespace tokenization."""
    return len(text.split())


class ChunkingService:
    """Splits file content into embeddable chunks."""

    def chunk_file(
        self,
        *,
        content: str,
        symbols: list[ParsedSymbol],
        chunk_tokens: int,
        overlap_tokens: int,
    ) -> list[Chunk]:
        """Chunk ``content`` targeting ``chunk_tokens`` with ``overlap_tokens`` overlap.

        Symbol start lines act as preferred break points so a chunk never
        begins mid-symbol when a symbol boundary is available.
        """
        if not content.strip():
            return []

        lines = content.split("\n")
        line_tokens = [count_tokens(line) for line in lines]
        symbol_starts = {s.line_start for s in symbols}
        overlap_lines = _overlap_lines(overlap_tokens, line_tokens)

        chunks: list[Chunk] = []
        i = 0
        n = len(lines)
        min_tokens = max(1, chunk_tokens // 2)
        while i < n:
            start = i
            buffer: list[str] = []
            tokens = 0
            while i < n:
                line_no = i + 1  # 1-based line number
                if buffer and line_no in symbol_starts and tokens >= min_tokens:
                    break
                next_tokens = line_tokens[i]
                if buffer and tokens + next_tokens > chunk_tokens:
                    break
                buffer.append(lines[i])
                tokens += next_tokens
                i += 1
            if not buffer:
                i += 1  # avoid infinite loop on empty line
                continue
            end = i  # exclusive line index
            chunks.append(
                Chunk(
                    content="\n".join(buffer),
                    line_start=start + 1,
                    line_end=end,
                    token_count=tokens,
                )
            )
            # Back up by the overlap, but never re-include the first line.
            if overlap_lines and end - start > overlap_lines:
                i = max(start + 1, end - overlap_lines)
        return chunks


def _overlap_lines(overlap_tokens: int, line_tokens: list[int]) -> int:
    """Convert an overlap token budget into a line count."""
    if overlap_tokens <= 0:
        return 0
    total = 0
    count = 0
    for tokens in reversed(line_tokens):
        total += tokens
        count += 1
        if total >= overlap_tokens:
            break
    return max(1, count)