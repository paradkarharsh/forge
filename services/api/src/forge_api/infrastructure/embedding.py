"""Embedding providers for repository intelligence.

Implements ``EmbeddingProvider``. ``NullEmbedder`` disables embeddings so
the system works fully without any ML dependency; ``SentenceTransformerEmbedder``
provides local 384-dimension embeddings via sentence-transformers
(``all-MiniLM-L6-v2``). The provider interface stays open for future
providers (e.g. hosted APIs) without changing the application layer.
"""
import asyncio
import logging

from forge_api.domain.indexing import EmbeddingProvider

logger = logging.getLogger(__name__)


class NullEmbedder:
    """Disabled embedding provider: returns None vectors for every text."""

    async def embed(self, texts: list[str]) -> list[list[float] | None]:
        return [None for _ in texts]

    def dimension(self) -> int | None:
        return None


class SentenceTransformerEmbedder:
    """Local embeddings via sentence-transformers (384 dimensions).

    The model is loaded lazily so an app that never enables embeddings does
    not pay the import cost. Requires the ``sentence-transformers`` package
    (optional ``embeddings`` extra); construction raises ``RuntimeError``
    when the package is unavailable.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model = None
        self._dimension = 384

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - optional dep
                raise RuntimeError(
                    "sentence-transformers is not installed; "
                    "install the 'embeddings' extra to enable local embeddings"
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []
        model = self._load()

        def encode(batch: list[str]) -> list[list[float]]:
            return model.encode(batch, normalize_embeddings=True).tolist()

        # encode is CPU-bound; run it off the event loop.
        return await asyncio.get_running_loop().run_in_executor(None, encode, texts)

    def dimension(self) -> int | None:
        return self._dimension


def build_embedding_provider(provider: str, model: str) -> EmbeddingProvider:
    """Construct the provider configured by ``Settings``.

    ``provider == "local"`` returns a sentence-transformers embedder when
    the optional dependency is installed; otherwise it degrades to
    ``NullEmbedder`` so the system always works with embeddings disabled.
    """
    if provider == "local":
        try:
            return SentenceTransformerEmbedder(model)
        except Exception:
            logger.warning(
                "Embedding provider 'local' unavailable; falling back to no embeddings"
            )
    return NullEmbedder()