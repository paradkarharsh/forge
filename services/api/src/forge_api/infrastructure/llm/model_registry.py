"""Configuration-driven model registry.

Provides model lookup, capability checks, and cost metadata without
exposing API secrets.  Provider secrets live in Settings only, never
in the registry or PostgreSQL.
"""
import logging
from typing import Any

from forge_api.domain.llm import (
    LLMProviderType,
    ModelCapabilities,
    ModelSpec,
)

logger = logging.getLogger(__name__)

# ─── Built-in model definitions ──────────────────────────────────────

_BUILTIN_MODELS: list[ModelSpec] = [
    # Fake provider (always available — used by tests)
    ModelSpec(
        provider=LLMProviderType.FAKE,
        model_id="fake/echo",
        display_name="Fake Echo (Test)",
        capabilities=ModelCapabilities(chat=True, streaming=True, system_prompt=True),
        context_window=8192,
        max_output_tokens=4096,
        default_temperature=0.7,
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        enabled=True,
        availability="available",
    ),
    # OpenAI
    ModelSpec(
        provider=LLMProviderType.OPENAI,
        model_id="gpt-4o",
        display_name="GPT-4o",
        capabilities=ModelCapabilities(
            chat=True, streaming=True, system_prompt=True,
            tool_calling=True, structured_output=True,
        ),
        context_window=128_000,
        max_output_tokens=16_384,
        default_temperature=0.7,
        input_cost_per_million=2.50,
        output_cost_per_million=10.00,
        enabled=True,
        availability="requires_api_key",
    ),
    ModelSpec(
        provider=LLMProviderType.OPENAI,
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        capabilities=ModelCapabilities(
            chat=True, streaming=True, system_prompt=True,
            tool_calling=True, structured_output=True,
        ),
        context_window=128_000,
        max_output_tokens=16_384,
        default_temperature=0.7,
        input_cost_per_million=0.15,
        output_cost_per_million=0.60,
        enabled=True,
        availability="requires_api_key",
    ),
    # Ollama (local)
    ModelSpec(
        provider=LLMProviderType.OLLAMA,
        model_id="llama3.1",
        display_name="Llama 3.1 (Local)",
        capabilities=ModelCapabilities(
            chat=True, streaming=True, system_prompt=True,
        ),
        context_window=128_000,
        max_output_tokens=8192,
        default_temperature=0.7,
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        enabled=True,
        availability="requires_ollama",
    ),
    ModelSpec(
        provider=LLMProviderType.OLLAMA,
        model_id="codellama",
        display_name="Code Llama (Local)",
        capabilities=ModelCapabilities(
            chat=True, streaming=True, system_prompt=True,
        ),
        context_window=16_384,
        max_output_tokens=4096,
        default_temperature=0.7,
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        enabled=True,
        availability="requires_ollama",
    ),
]


class ModelRegistry:
    """Configuration-driven model registry.

    Never exposes API secrets.
    """

    def __init__(
        self, extra_models: list[ModelSpec] | None = None,
    ) -> None:
        self._models: dict[str, ModelSpec] = {}
        for spec in _BUILTIN_MODELS:
            self._models[spec.model_id] = spec
        for spec in extra_models or []:
            self._models[spec.model_id] = spec

    def get(self, model_id: str) -> ModelSpec | None:
        return self._models.get(model_id)

    def list_models(
        self, *, enabled_only: bool = True,
    ) -> list[ModelSpec]:
        models = list(self._models.values())
        if enabled_only:
            models = [m for m in models if m.enabled]
        return models

    def list_by_provider(
        self, provider: LLMProviderType,
    ) -> list[ModelSpec]:
        return [
            m for m in self._models.values()
            if m.provider == provider and m.enabled
        ]

    def resolve_model(self, model_id: str) -> ModelSpec | None:
        """Resolve a model, returning None if not found or disabled."""
        spec = self._models.get(model_id)
        if spec is None or not spec.enabled:
            return None
        return spec

    def estimate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost in USD for a given token count."""
        spec = self._models.get(model_id)
        if spec is None:
            return 0.0
        return (
            spec.input_cost_per_million * input_tokens / 1_000_000
            + spec.output_cost_per_million * output_tokens / 1_000_000
        )

    def model_view(self, spec: ModelSpec) -> dict[str, Any]:
        """API-safe view of a model (no secrets)."""
        return {
            "model_id": spec.model_id,
            "provider": spec.provider.value,
            "display_name": spec.display_name,
            "capabilities": {
                "chat": spec.capabilities.chat,
                "streaming": spec.capabilities.streaming,
                "system_prompt": spec.capabilities.system_prompt,
                "tool_calling": spec.capabilities.tool_calling,
                "structured_output": spec.capabilities.structured_output,
            },
            "context_window": spec.context_window,
            "max_output_tokens": spec.max_output_tokens,
            "default_temperature": spec.default_temperature,
            "input_cost_per_million": spec.input_cost_per_million,
            "output_cost_per_million": spec.output_cost_per_million,
            "enabled": spec.enabled,
            "availability": spec.availability,
        }
