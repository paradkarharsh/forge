"""Usage tracking service.

Records per-request LLM usage (tokens, cost, duration) using the model
registry for cost metadata.  Local/Ollama cost is zero.
"""
import logging
from uuid import UUID

from forge_api.domain.conversation import UsageEventRecord
from forge_api.domain.llm import TokenUsage
from forge_api.domain.repositories import UsageEventRepository
from forge_api.infrastructure.llm.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class UsageTracker:
    """Records and queries LLM usage events."""

    def __init__(
        self,
        *,
        usage_repo: UsageEventRepository,
        registry: ModelRegistry,
    ) -> None:
        self._usage = usage_repo
        self._registry = registry

    async def record(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        provider: str,
        model: str,
        usage: TokenUsage,
        duration_ms: float,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> UsageEventRecord:
        """Record a usage event with cost estimation."""
        estimated_cost = self._registry.estimate_cost(
            model, usage.input_tokens, usage.output_tokens,
        )
        return await self._usage.create(
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            provider=provider,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            duration_ms=duration_ms,
            estimated_cost=estimated_cost,
            metadata=metadata,
        )

    async def get_workspace_usage(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        start=None,
        end=None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[UsageEventRecord]:
        return await self._usage.list_by_workspace(
            workspace_id,
            user_id=user_id,
            start=start,
            end=end,
            limit=limit,
            offset=offset,
        )

    async def get_workspace_aggregate(
        self,
        workspace_id: UUID,
        *,
        user_id: UUID | None = None,
        start=None,
        end=None,
    ) -> dict:
        return await self._usage.aggregate_by_workspace(
            workspace_id,
            user_id=user_id,
            start=start,
            end=end,
        )
