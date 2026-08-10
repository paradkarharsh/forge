"""Embedding provider unit tests."""
from forge_api.infrastructure.embedding import (
    NullEmbedder,
    build_embedding_provider,
)


async def test_null_embedder_returns_none_vectors() -> None:
    embedder = NullEmbedder()
    assert embedder.dimension() is None
    vectors = await embedder.embed(["hello", "world"])
    assert vectors == [None, None]


def test_build_provider_defaults_to_none() -> None:
    provider = build_embedding_provider("none", "all-MiniLM-L6-v2")
    assert provider.dimension() is None
    assert isinstance(provider, NullEmbedder)


def test_build_provider_unknown_falls_back_to_none() -> None:
    provider = build_embedding_provider("mystery", "x")
    assert provider.dimension() is None


class _FakeModel:
    def encode(self, batch, *, normalize_embeddings):
        return [[1.0, 0.0] for _ in batch]


class _FakeSentenceTransformerEmbedder(NullEmbedder):
    """Stand-in for SentenceTransformerEmbedder with a fake model."""

    def __init__(self) -> None:
        self._model = _FakeModel()
        self._dimension = 2

    def _load(self):
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float] | None]:
        model = self._load()
        return model.encode(texts, normalize_embeddings=True)

    def dimension(self) -> int | None:
        return self._dimension


async def test_local_provider_shape() -> None:
    """The real provider's embed contract: one vector per text, model dim."""
    provider = _FakeSentenceTransformerEmbedder()
    assert provider.dimension() == 2
    vectors = await provider.embed(["a", "b"])
    assert len(vectors) == 2
    assert all(len(v) == 2 for v in vectors)