"""Conversation management service.

Orchestrates conversation lifecycle, message persistence, and LLM interaction
with full authorization enforcement.
"""
import logging
from typing import Any
from uuid import UUID

from forge_api.domain.audit import AuditEventType
from forge_api.domain.conversation import (
    ConversationRecord,
    MessageRecord,
)
from forge_api.domain.errors import AuthorizationError, NotFoundError, ValidationError
from forge_api.domain.llm import ChatMessage, FinishReason, MessageRole
from forge_api.domain.memory import ContextWindow
from forge_api.domain.repositories import (
    ConversationRepository,
    MessageRepository,
    UsageEventRepository,
)
from forge_api.infrastructure.audit import AuditLogger
from forge_api.infrastructure.llm.model_registry import ModelRegistry

from .gateway import GatewayStreamIterator, LLMGateway
from .prompt_builder import PromptBuilder
from .usage_tracker import UsageTracker

logger = logging.getLogger(__name__)


class ConversationService:
    """Manages conversation lifecycle with LLM integration.

    Responsibilities:
    - Conversation CRUD with authorization
    - Message persistence
    - Context assembly → PromptBuilder → LLMGateway flow
    - Usage tracking
    - Streaming lifecycle management
    """

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        messages: MessageRepository,
        usage_events: UsageEventRepository,
        gateway: LLMGateway,
        prompt_builder: PromptBuilder,
        usage_tracker: UsageTracker,
        registry: ModelRegistry,
        audit: AuditLogger,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._usage_events = usage_events
        self._gateway = gateway
        self._prompt_builder = prompt_builder
        self._usage_tracker = usage_tracker
        self._registry = registry
        self._audit = audit

    # ─── Conversation CRUD ─────────────────────────────────────────────

    async def create_conversation(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        title: str | None = None,
        repository_id: UUID | None = None,
    ) -> ConversationRecord:
        """Create a new conversation."""
        conversation = await self._conversations.create(
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            repository_id=repository_id,
        )
        self._audit.log(
            AuditEventType.CONVERSATION_CREATED,
            user_id=user_id,
            payload={
                "conversation_id": str(conversation.id),
                "workspace_id": str(workspace_id),
                "repository_id": str(repository_id) if repository_id else None,
            },
        )
        return conversation

    async def get_conversation(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        require_owner: bool = False,
    ) -> ConversationRecord:
        """Get a conversation with authorization check."""
        conversation = await self._conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found")

        # Verify workspace membership and conversation ownership
        if conversation.workspace_id != workspace_id:
            raise AuthorizationError("Conversation does not belong to workspace")
        if conversation.user_id != user_id:
            # Allow workspace admins to view, but only owner can modify
            if require_owner:
                raise AuthorizationError("You do not have access to this conversation")

        return conversation

    async def list_conversations(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ConversationRecord]:
        """List conversations for a user in a workspace."""
        return await self._conversations.list_by_workspace(
            workspace_id,
            user_id,
            limit=limit,
            offset=offset,
        )

    async def count_conversations(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> int:
        """Count conversations for a user in a workspace."""
        return await self._conversations.count_by_workspace(workspace_id, user_id)

    async def delete_conversation(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Soft delete a conversation. Only owner can delete."""
        # Verify ownership
        conversation = await self.get_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            require_owner=True,
        )

        if conversation.deleted_at is not None:
            return False  # Already deleted

        result = await self._conversations.soft_delete(conversation_id)
        if result:
            self._audit.log(
                AuditEventType.CONVERSATION_DELETED,
                user_id=user_id,
                payload={
                    "conversation_id": str(conversation_id),
                    "workspace_id": str(workspace_id),
                },
            )
        return result

    # ─── Message operations ─────────────────────────────────────────────

    async def list_messages(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MessageRecord]:
        """List messages in a conversation with authorization."""
        # Verify access
        await self.get_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return await self._messages.list_by_conversation(
            conversation_id,
            limit=limit,
            offset=offset,
        )

    async def count_messages(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
    ) -> int:
        """Count messages in a conversation with authorization."""
        await self.get_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return await self._messages.count_by_conversation(conversation_id)

    # ─── LLM completion ─────────────────────────────────────────────────

    async def complete(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        user_message: str,
        context_window: ContextWindow | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[MessageRecord, MessageRecord]:
        """Run a non-streaming completion.

        Returns (user_message_record, assistant_message_record).
        """
        # Verify conversation exists and user has access
        conversation = await self.get_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            require_owner=True,
        )

        if conversation.deleted_at is not None:
            raise ValidationError("Cannot complete a deleted conversation")

        # Resolve model
        model_id = model or "fake/echo"
        spec = self._registry.resolve_model(model_id)
        if spec is None:
            raise ValidationError(f"Model '{model_id}' is not available")

        # Get conversation history
        history_messages = await self._get_conversation_history(conversation_id)

        # Build prompt
        prompt_messages = self._prompt_builder.build(
            user_query=user_message,
            context_window=context_window,
            conversation_history=history_messages,
        )

        # Persist user message
        user_record = await self._messages.create(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )
        await self._conversations.increment_message_count(conversation_id)

        # Call LLM
        response = await self._gateway.complete(
            messages=prompt_messages,
            model=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
        )

        # Persist assistant message
        assistant_record = await self._messages.create(
            conversation_id=conversation_id,
            role="assistant",
            content=response.content,
            provider=response.provider,
            model=response.model,
            prompt_version=self._prompt_builder.version,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
            duration_ms=response.duration_ms,
            finish_reason=response.finish_reason.value,
            status="complete" if response.finish_reason == FinishReason.STOP else "partial",
            metadata=response.metadata,
        )
        await self._conversations.increment_message_count(conversation_id)

        # Record usage
        await self._usage_tracker.record(
            workspace_id=workspace_id,
            user_id=user_id,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
            duration_ms=response.duration_ms,
            conversation_id=conversation_id,
            message_id=assistant_record.id,
        )

        return user_record, assistant_record

    async def stream(
        self,
        *,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        user_message: str,
        context_window: ContextWindow | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> "ConversationStream":
        """Start a streaming completion.

        Returns a ConversationStream that yields SSE-compatible events.
        """
        # Verify conversation exists and user has access
        conversation = await self.get_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            require_owner=True,
        )

        if conversation.deleted_at is not None:
            raise ValidationError("Cannot complete a deleted conversation")

        # Resolve model
        model_id = model or "fake/echo"
        spec = self._registry.resolve_model(model_id)
        if spec is None:
            raise ValidationError(f"Model '{model_id}' is not available")

        # Get conversation history
        history_messages = await self._get_conversation_history(conversation_id)

        # Build prompt
        prompt_messages = self._prompt_builder.build(
            user_query=user_message,
            context_window=context_window,
            conversation_history=history_messages,
        )

        # Persist user message
        user_record = await self._messages.create(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )
        await self._conversations.increment_message_count(conversation_id)

        # Start LLM stream
        stream = await self._gateway.stream(
            messages=prompt_messages,
            model=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
        )

        # Create assistant message placeholder
        assistant_record = await self._messages.create(
            conversation_id=conversation_id,
            role="assistant",
            content="",  # Will be updated as we stream
            provider=spec.provider.value,
            model=model_id,
            prompt_version=self._prompt_builder.version,
            status="partial",
        )
        await self._conversations.increment_message_count(conversation_id)

        return ConversationStream(
            stream=stream,
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            user_record=user_record,
            assistant_record=assistant_record,
            messages=self._messages,
            conversations=self._conversations,
            usage_tracker=self._usage_tracker,
            prompt_version=self._prompt_builder.version,
        )

    async def _get_conversation_history(
        self, conversation_id: UUID
    ) -> list[ChatMessage]:
        """Get prior messages for context."""
        records = await self._messages.list_by_conversation(
            conversation_id,
            limit=100,  # Reasonable history limit
        )
        messages = []
        for record in records:
            role = MessageRole.USER if record.role == "user" else MessageRole.ASSISTANT
            if record.role == "system":
                role = MessageRole.SYSTEM
            messages.append(ChatMessage(role=role, content=record.content))
        return messages


class ConversationStream:
    """Manages streaming completion lifecycle with persistence.

    Yields SSE-compatible events and handles:
    - Accumulating content
    - Persisting final message
    - Recording usage
    - Handling cancellation
    """

    def __init__(
        self,
        *,
        stream: GatewayStreamIterator,
        conversation_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        user_record: MessageRecord,
        assistant_record: MessageRecord,
        messages: MessageRepository,
        conversations: ConversationRepository,
        usage_tracker: UsageTracker,
        prompt_version: str,
    ) -> None:
        self._stream = stream
        self._conversation_id = conversation_id
        self._workspace_id = workspace_id
        self._user_id = user_id
        self._user_record = user_record
        self._assistant_record = assistant_record
        self._messages = messages
        self._conversations = conversations
        self._usage_tracker = usage_tracker
        self._prompt_version = prompt_version
        self._finalized = False

    @property
    def conversation_id(self) -> UUID:
        return self._conversation_id

    @property
    def message_id(self) -> UUID:
        return self._assistant_record.id

    @property
    def model(self) -> str:
        return self._assistant_record.model or "unknown"

    def __aiter__(self) -> "ConversationStream":
        return self

    async def __anext__(self) -> dict[str, Any]:
        """Yield SSE-compatible event data."""
        if self._finalized:
            raise StopAsyncIteration

        try:
            delta = await self._stream.__anext__()

            # Check if stream is complete
            if delta.finish_reason is not None:
                await self._finalize(
                    content=self._stream.accumulated_content,
                    usage=delta.usage,
                    finish_reason=delta.finish_reason.value,
                )
                return {
                    "event": "done",
                    "data": {
                        "finish_reason": delta.finish_reason.value,
                        "usage": {
                            "input_tokens": delta.usage.input_tokens if delta.usage else 0,
                            "output_tokens": delta.usage.output_tokens if delta.usage else 0,
                            "total_tokens": delta.usage.total_tokens if delta.usage else 0,
                        },
                    },
                }

            return {
                "event": "delta",
                "data": {"content": delta.content},
            }

        except StopAsyncIteration:
            # Stream ended naturally without finish_reason
            await self._finalize(
                content=self._stream.accumulated_content,
                usage=self._stream.usage,
                finish_reason="stop",
            )
            raise

        except Exception as exc:
            # Error during streaming
            await self._finalize(
                content=self._stream.accumulated_content,
                usage=self._stream.usage,
                finish_reason="error",
                error=str(exc),
            )
            return {
                "event": "error",
                "data": {
                    "code": "stream_error",
                    "message": str(exc)[:200],
                },
            }

    async def cancel(self) -> None:
        """Cancel the stream and persist partial output."""
        if self._finalized:
            return

        await self._finalize(
            content=self._stream.accumulated_content,
            usage=self._stream.usage,
            finish_reason="cancelled",
        )

    async def _finalize(
        self,
        *,
        content: str,
        usage: Any | None,
        finish_reason: str,
        error: str | None = None,
    ) -> None:
        """Persist final assistant message and usage."""
        if self._finalized:
            return
        self._finalized = True

        # Update assistant message
        status = "complete" if finish_reason == "stop" else "partial"
        if error:
            status = "error"

        await self._messages.update(
            self._assistant_record.id,
            content=content,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            duration_ms=self._stream.duration_ms,
            finish_reason=finish_reason,
            status=status,
            metadata={"error": error} if error else None,
        )

        # Record usage if available
        if usage and usage.total_tokens > 0:
            await self._usage_tracker.record(
                workspace_id=self._workspace_id,
                user_id=self._user_id,
                provider=self._assistant_record.provider or "unknown",
                model=self._assistant_record.model or "unknown",
                usage=usage,
                duration_ms=self._stream.duration_ms,
                conversation_id=self._conversation_id,
                message_id=self._assistant_record.id,
            )
