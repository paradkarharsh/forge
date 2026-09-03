"""Bounded Agent Orchestrator owning the agent execution loop and lifecycle.

Integrates:
- FP6 Context & Memory
- FP7 LLM Gateway & PromptBuilder
- FP8 ToolRegistry & PolicyEngine
- Bounded observations & secret redaction
- Deterministic approval suspension and cryptographic argument hash resumption
- Cancellation and cumulative execution limits
"""

import hmac
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from forge_api.application.agent.context_adapter import AgentContextAdapter
from forge_api.application.agent.decision_parser import ModelDecisionParser
from forge_api.application.llm.gateway import LLMGateway
from forge_api.application.llm.prompt_builder import PromptBuilder
from forge_api.application.tools.policy_engine import PolicyEngine
from forge_api.application.tools.tool_registry import ToolRegistry
from forge_api.domain.agent import (
    AgentEvent,
    AgentEventPublisher,
    AgentEventType,
    AgentLimits,
    AgentSessionRecord,
    AgentStatus,
    ExecutionMetrics,
    ModelDecisionType,
    ToolCallStatus,
    is_terminal_agent_status,
    validate_agent_transition,
)
from forge_api.domain.approval import (
    ApprovalStatus,
    compute_arguments_hash,
)
from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import (
    DomainError,
    NotFoundError,
    ValidationError,
)
from forge_api.domain.llm import ChatMessage, MessageRole
from forge_api.domain.repositories import (
    AgentApprovalRepository,
    AgentSessionRepository,
    AgentStepRepository,
    AgentToolCallRepository,
    RepositoryRepository,
    WorkspaceRepository,
)
from forge_api.domain.tool import (
    ToolExecutionContext,
    redact_secrets,
)

logger = logging.getLogger(__name__)

_DEFAULT_APPROVAL_TTL_HOURS = 24


@runtime_checkable
class CancellationChecker(Protocol):
    """Protocol for dynamic cancellation detection (e.g. via Redis)."""

    async def is_cancelled(self, session_id: UUID) -> bool: ...


class AgentOrchestrator:
    """The authoritative engine running bounded agent execution loops."""

    def __init__(
        self,
        *,
        sessions: AgentSessionRepository,
        steps: AgentStepRepository,
        tool_calls: AgentToolCallRepository,
        approvals: AgentApprovalRepository,
        tool_registry: ToolRegistry,
        policy_engine: PolicyEngine,
        context_assembly: Any,  # ContextAssemblyService
        prompt_builder: PromptBuilder,
        gateway: LLMGateway,
        events: AgentEventPublisher,
        workspaces: WorkspaceRepository,
        repositories: RepositoryRepository | None = None,
        cancellation_checker: CancellationChecker | None = None,
        context_adapter: AgentContextAdapter | None = None,
        decision_parser: ModelDecisionParser | None = None,
        audit: Any | None = None,
        usage_tracker: Any | None = None,
    ) -> None:
        self._sessions = sessions
        self._steps = steps
        self._tool_calls = tool_calls
        self._approvals = approvals
        self._tool_registry = tool_registry
        self._policy_engine = policy_engine
        self._context_assembly = context_assembly
        self._prompt_builder = prompt_builder
        self._gateway = gateway
        self._events = events
        self._workspaces = workspaces
        self._repositories = repositories
        self._cancellation_checker = cancellation_checker
        self._context_adapter = context_adapter or AgentContextAdapter()
        self._decision_parser = decision_parser or ModelDecisionParser()
        self._audit = audit
        self._usage_tracker = usage_tracker

    def _audit_log(
        self,
        event_type: AuditEventType,
        session: AgentSessionRecord,
        *,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Safely record an audit event without secrets or raw reasoning."""
        if not self._audit:
            return
        safe_payload = {
            "workspace_id": str(session.workspace_id),
            "repository_id": str(session.repository_id) if session.repository_id else None,
            "session_id": str(session.id),
        }
        if payload:
            for k, v in payload.items():
                if k in (
                    "chain_of_thought",
                    "thought",
                    "reasoning",
                    "secret",
                    "password",
                    "token",
                    "api_key",
                ):
                    continue
                if isinstance(v, str):
                    safe_payload[k] = redact_secrets(v)[:500]
                elif isinstance(v, (int, float, bool)):
                    safe_payload[k] = v
                elif isinstance(v, dict):
                    safe_payload[k] = {
                        sk: redact_secrets(str(sv))[:200] if isinstance(sv, str) else sv
                        for sk, sv in v.items()
                        if sk
                        not in (
                            "chain_of_thought",
                            "thought",
                            "reasoning",
                            "secret",
                            "password",
                            "token",
                            "api_key",
                        )
                    }

        try:
            self._audit.log(
                event_type,
                user_id=session.user_id,
                session_id=session.id,
                reason=reason,
                payload=safe_payload,
            )
        except Exception as exc:
            logger.warning(
                "Failed to record audit event %s for session %s: %s", event_type, session.id, exc
            )

    async def run_session(self, session_id: UUID) -> AgentSessionRecord:
        """Run an agent session loop to completion or until suspended for approval."""
        session = await self._sessions.get(session_id)
        if not session:
            raise NotFoundError(
                f"Agent session '{session_id}' not found.",
                code="agent_session_not_found",
            )

        if is_terminal_agent_status(session.status):
            raise DomainError(
                f"Agent session is in terminal state '{session.status.value}'.",
                code="terminal_agent_session",
            )

        if session.status == AgentStatus.WAITING_FOR_APPROVAL:
            raise DomainError(
                "Agent session is waiting for approval. Use resume_session() after approval.",
                code="session_waiting_for_approval",
            )

        # Transition to RUNNING if needed (CREATED -> PLANNING -> RUNNING)
        if session.status == AgentStatus.CREATED:
            validate_agent_transition(session.status, AgentStatus.PLANNING)
            session = await self._sessions.update_status(
                session_id,
                AgentStatus.PLANNING,
                started_at=session.started_at or datetime.now(UTC),
            )
            await self._emit(AgentEventType.PLANNING_STARTED, session_id)
            self._audit_log(AuditEventType.AGENT_PLANNING_STARTED, session)
        if session.status == AgentStatus.PLANNING:
            validate_agent_transition(session.status, AgentStatus.RUNNING)
            session = await self._sessions.update_status(
                session_id,
                AgentStatus.RUNNING,
                started_at=session.started_at or datetime.now(UTC),
            )
            await self._emit(AgentEventType.STARTED, session_id)
            await self._emit(AgentEventType.RUNNING, session_id)
            self._audit_log(AuditEventType.AGENT_RUNNING, session)

        # Resolve authoritative repo root
        repo_root = await self._resolve_repo_root(session.repository_id)

        # Resolve workspace role
        user_role = await self._resolve_user_role(session.workspace_id, session.user_id)

        return await self._orchestration_loop(session, repo_root, user_role)

    async def resume_session(self, session_id: UUID) -> AgentSessionRecord:
        """Resume an agent session suspended in WAITING_FOR_APPROVAL."""
        session = await self._sessions.get(session_id)
        if not session:
            raise NotFoundError(
                f"Agent session '{session_id}' not found.",
                code="agent_session_not_found",
            )

        if session.status != AgentStatus.WAITING_FOR_APPROVAL:
            raise DomainError(
                f"Session status is '{session.status.value}', expected 'waiting_for_approval'.",
                code="invalid_agent_state",
            )

        # Load latest approval for session
        approvals = await self._approvals.list_by_session(session_id)
        if not approvals:
            raise NotFoundError(
                "No approval found for session.",
                code="no_approval_found",
            )
        approval = max(approvals, key=lambda a: a.requested_at)

        # 1. Check expiration
        now = datetime.now(UTC)
        if approval.expires_at and now > approval.expires_at:
            await self._approvals.decide(
                approval.id,
                status=ApprovalStatus.EXPIRED,
                decided_by=approval.requested_by or session.user_id,
                reason="Approval request expired.",
                decided_at=now,
            )
            session = await self._sessions.update_status(
                session_id,
                AgentStatus.EXPIRED,
                completed_at=now,
            )
            await self._emit(AgentEventType.TIMED_OUT, session_id, {"reason": "expired"})
            return session

        # 2. Check decision status
        if approval.status == ApprovalStatus.DENIED:
            await self._emit(AgentEventType.APPROVAL_DENIED, session_id)
            # Record denial as observation and resume to let agent handle it or fail
            denial_obs = self._context_adapter.format_observation(
                tool_name=approval.tool_name,
                output=(
                    f"Approval was DENIED for tool '{approval.tool_name}'. "
                    f"Reason: {approval.reason or 'User denied'}"
                ),
                is_error=True,
            )

            validate_agent_transition(session.status, AgentStatus.RUNNING)
            session = await self._sessions.update_status(session_id, AgentStatus.RUNNING)
            repo_root = await self._resolve_repo_root(session.repository_id)
            user_role = await self._resolve_user_role(session.workspace_id, session.user_id)
            return await self._orchestration_loop(
                session, repo_root, user_role, initial_observation=denial_obs
            )

        if approval.status != ApprovalStatus.GRANTED:
            raise DomainError(
                f"Approval status is '{approval.status.value}', not 'granted'.",
                code="approval_not_granted",
            )

        # 3. Load tool call and verify cryptographic arguments hash
        tool_call = await self._tool_calls.get(approval.tool_call_id)
        if not tool_call:
            raise NotFoundError(
                "Tool call associated with approval not found.",
                code="tool_call_not_found",
            )

        if tool_call.status != ToolCallStatus.PENDING_APPROVAL:
            raise DomainError(
                f"Tool call '{tool_call.id}' status is '{tool_call.status.value}', "
                "expected 'pending_approval'.",
                code="tool_call_already_executed",
            )

        recomputed_hash = compute_arguments_hash(tool_call.arguments)
        if not hmac.compare_digest(recomputed_hash, approval.arguments_hash):
            logger.error(
                "Cryptographic argument hash mismatch for session %s, tool call %s",
                session_id,
                tool_call.id,
            )
            await self._tool_calls.complete(
                tool_call.id,
                status=ToolCallStatus.FAILED,
                error_message="Tampered tool arguments: cryptographic hash mismatch.",
            )
            session = await self._sessions.update_status(
                session_id, AgentStatus.FAILED, completed_at=now
            )
            await self._emit(AgentEventType.FAILED, session_id, {"error": "hash_mismatch"})
            raise DomainError(
                "Tool call arguments do not match approved hash.",
                code="approval_hash_mismatch",
            )

        # 4. Transition back to RUNNING
        validate_agent_transition(session.status, AgentStatus.RUNNING)
        session = await self._sessions.update_status(session_id, AgentStatus.RUNNING)
        await self._emit(AgentEventType.APPROVAL_GRANTED, session_id)
        await self._emit(AgentEventType.RESUMED, session_id)
        self._audit_log(AuditEventType.AGENT_RESUMED, session, reason="approval_granted")

        repo_root = await self._resolve_repo_root(session.repository_id)
        user_role = await self._resolve_user_role(session.workspace_id, session.user_id)

        # Enforce cumulative tool call limit before executing tool
        if session.metrics.total_tool_calls >= session.limits.max_tool_calls:
            return await self._handle_timeout(
                session,
                session.metrics,
                session.metrics.wall_time_seconds,
                "Max tool calls exceeded.",
            )

        # 5. Execute the approved tool
        tool = self._tool_registry.get(tool_call.tool_name)
        if not tool:
            await self._tool_calls.complete(
                tool_call.id,
                status=ToolCallStatus.FAILED,
                error_message=f"Tool '{tool_call.tool_name}' missing from registry.",
            )
            return await self._orchestration_loop(session, repo_root, user_role)

        ctx = ToolExecutionContext(
            workspace_id=session.workspace_id,
            repository_id=session.repository_id,
            user_id=session.user_id,
            session_id=session.id,
            repo_root=repo_root,
            timeout_seconds=30.0,
        )

        await self._tool_calls.complete(tool_call.id, status=ToolCallStatus.RUNNING)
        await self._emit(AgentEventType.TOOL_STARTED, session_id, {"tool": tool.name})
        self._audit_log(
            AuditEventType.AGENT_TOOL_CALL_STARTED, session, payload={"tool": tool.name}
        )

        t_start = time.monotonic()
        try:
            res = await tool.execute(ctx, tool_call.arguments)
            duration_ms = (time.monotonic() - t_start) * 1000.0
            tool_status = ToolCallStatus.COMPLETED if res.success else ToolCallStatus.FAILED

            # Enforce max_output_bytes
            output_to_store = res.output
            if (
                output_to_store
                and len(output_to_store.encode("utf-8")) > session.limits.max_output_bytes
            ):
                max_bytes = session.limits.max_output_bytes
                truncated = output_to_store.encode("utf-8")[:max_bytes].decode(
                    "utf-8", errors="ignore"
                )
                output_to_store = (
                    f"{truncated}\n[... Tool output truncated: exceeded {max_bytes} byte limit ...]"
                )

            await self._tool_calls.complete(
                tool_call.id,
                status=tool_status,
                output=output_to_store,
                error_message=res.error,
                duration_ms=duration_ms,
                completed_at=datetime.now(UTC),
            )
            evt_type = AgentEventType.TOOL_COMPLETED if res.success else AgentEventType.TOOL_FAILED
            await self._emit(evt_type, session_id, {"tool": tool.name})
            self._audit_log(
                AuditEventType.AGENT_TOOL_CALL_COMPLETED
                if res.success
                else AuditEventType.AGENT_TOOL_CALL_FAILED,
                session,
                payload={"tool": tool.name, "success": res.success},
            )

            obs = self._context_adapter.format_observation(
                tool_name=tool.name,
                output=output_to_store if res.success else (res.error or output_to_store),
                is_error=not res.success,
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - t_start) * 1000.0
            await self._tool_calls.complete(
                tool_call.id,
                status=ToolCallStatus.FAILED,
                error_message=str(exc),
                duration_ms=duration_ms,
                completed_at=datetime.now(UTC),
            )
            await self._emit(AgentEventType.TOOL_FAILED, session_id, {"tool": tool.name})
            self._audit_log(
                AuditEventType.AGENT_TOOL_CALL_FAILED,
                session,
                payload={"tool": tool.name, "error": str(exc)},
            )
            obs = self._context_adapter.format_observation(
                tool_name=tool.name,
                output=f"Execution error: {exc}",
                is_error=True,
            )

        # Update cumulative tool count
        updated_metrics = ExecutionMetrics(
            total_llm_calls=session.metrics.total_llm_calls,
            total_tool_calls=session.metrics.total_tool_calls + 1,
            total_input_tokens=session.metrics.total_input_tokens,
            total_output_tokens=session.metrics.total_output_tokens,
            wall_time_seconds=session.metrics.wall_time_seconds,
            estimated_cost_usd=session.metrics.estimated_cost_usd,
            total_llm_retries=getattr(session.metrics, "total_llm_retries", 0),
        )
        session = await self._sessions.update_metrics(session_id, updated_metrics)

        # Continue orchestration loop
        return await self._orchestration_loop(
            session, repo_root, user_role, initial_observation=obs
        )

    # ─── Private Orchestration Loop ───────────────────────────────────

    async def _orchestration_loop(
        self,
        session: AgentSessionRecord,
        repo_root: str | None,
        user_role: WorkspaceRole,
        initial_observation: str | None = None,
    ) -> AgentSessionRecord:
        """The bounded, non-blocking execution loop."""
        session_id = session.id
        limits = session.limits or AgentLimits()
        metrics = session.metrics or ExecutionMetrics()
        loop_start_time = time.monotonic()

        observations: list[str] = []
        if initial_observation:
            observations.append(initial_observation)

        while True:
            # Heartbeat update in DB to signal active healthy worker
            if hasattr(self._sessions, "update_heartbeat"):
                try:
                    await self._sessions.update_heartbeat(
                        session_id, heartbeat_at=datetime.now(UTC)
                    )
                except Exception:
                    pass

            # 1. Check Cancellation before iteration
            if await self._is_cancelled(session_id):
                return await self._handle_cancellation(session, metrics, loop_start_time)

            # 2. Check Cumulative Execution Limits
            wall_time_elapsed = time.monotonic() - loop_start_time
            cumulative_wall_time = metrics.wall_time_seconds + wall_time_elapsed

            if cumulative_wall_time >= limits.max_wall_time_seconds:
                return await self._handle_timeout(
                    session, metrics, cumulative_wall_time, "Max wall time exceeded."
                )

            if metrics.total_llm_calls >= limits.max_llm_calls:
                return await self._handle_timeout(
                    session, metrics, cumulative_wall_time, "Max LLM calls exceeded."
                )

            if metrics.total_tool_calls >= limits.max_tool_calls:
                return await self._handle_timeout(
                    session, metrics, cumulative_wall_time, "Max tool calls exceeded."
                )

            # 3. Assemble Context via FP6 ContextAssemblyService
            context_window = None
            try:
                context_window = await self._context_assembly.assemble(
                    workspace_id=session.workspace_id,
                    user_id=session.user_id,
                    query=session.objective,
                    repository_id=session.repository_id,
                    session_id=session.id,
                )
            except Exception as exc:
                logger.warning("Context assembly failed for session %s: %s", session_id, exc)

            # 4. Build Structured Prompt with FP7 PromptBuilder & FP8 Tool Specs
            tool_specs = self._tool_registry.get_tool_specs()
            prompt_messages = self._build_prompt_messages(
                session.objective, context_window, observations, tool_specs
            )

            # 5. Check Cancellation before LLM invocation
            if await self._is_cancelled(session_id):
                return await self._handle_cancellation(session, metrics, loop_start_time)

            # 6. Call LLM Gateway
            model_to_use = session.model or "default"
            t_llm_start = time.monotonic()
            try:
                chat_response = await self._gateway.complete(
                    messages=prompt_messages,
                    model=model_to_use,
                    user_id=session.user_id,
                )
            except Exception as exc:
                logger.error("LLM call failed for session %s: %s", session_id, exc)
                # LLMGateway already retries transient errors. If it fails here, record failure.
                now = datetime.now(UTC)
                session = await self._sessions.update_status(
                    session_id, AgentStatus.FAILED, completed_at=now
                )
                await self._emit(AgentEventType.FAILED, session_id, {"error": str(exc)})
                self._audit_log(AuditEventType.AGENT_FAILED, session, reason=str(exc))
                return session

            llm_duration_ms = (time.monotonic() - t_llm_start) * 1000.0

            # Record authoritative usage event if usage tracker available
            estimated_cost = getattr(chat_response, "estimated_cost", 0.0)
            if self._usage_tracker:
                try:
                    usage_rec = await self._usage_tracker.record(
                        workspace_id=session.workspace_id,
                        user_id=session.user_id,
                        agent_session_id=session.id,
                        provider=getattr(chat_response, "provider", "default"),
                        model=chat_response.model or model_to_use,
                        usage=chat_response.usage,
                        duration_ms=llm_duration_ms,
                        metadata={"session_id": str(session.id), "step": session.current_step},
                    )
                    estimated_cost = getattr(usage_rec, "estimated_cost", estimated_cost)
                except Exception as exc:
                    logger.warning(
                        "Failed to record usage event for session %s: %s", session_id, exc
                    )

            # Update LLM metrics
            metrics = ExecutionMetrics(
                total_llm_calls=metrics.total_llm_calls + 1,
                total_tool_calls=metrics.total_tool_calls,
                total_input_tokens=metrics.total_input_tokens + chat_response.usage.input_tokens,
                total_output_tokens=metrics.total_output_tokens + chat_response.usage.output_tokens,
                wall_time_seconds=metrics.wall_time_seconds + (time.monotonic() - loop_start_time),
                estimated_cost_usd=metrics.estimated_cost_usd + estimated_cost,
                total_llm_retries=metrics.total_llm_retries + getattr(chat_response, "retries", 0),
            )
            session = await self._sessions.update_metrics(session_id, metrics)

            # 7. Parse Structured Model Decision
            try:
                decision = self._decision_parser.parse(chat_response)
            except ValidationError as exc:
                # Malformed decision is treated as bounded observation, not retried blindly
                obs = self._context_adapter.format_observation(
                    tool_name="model_decision_parser",
                    output=f"Malformed decision: {exc.message}. Please respond with valid JSON.",
                    is_error=True,
                )
                observations.append(obs)
                continue

            # 8. Handle 'complete' Decision
            if decision.type == ModelDecisionType.COMPLETE:
                now = datetime.now(UTC)
                validate_agent_transition(session.status, AgentStatus.COMPLETED)
                session = await self._sessions.update_status(
                    session_id, AgentStatus.COMPLETED, completed_at=now
                )
                await self._emit(
                    AgentEventType.COMPLETED,
                    session_id,
                    {"reason": decision.reason},
                )
                self._audit_log(
                    AuditEventType.AGENT_COMPLETED, session, payload={"reason": decision.reason}
                )
                return session

            # 9. Handle 'tool_call' Decision
            tool_name = decision.tool_name or ""
            tool = self._tool_registry.get(tool_name)

            if not tool:
                obs = self._context_adapter.format_observation(
                    tool_name=tool_name,
                    output=f"Error: Tool '{tool_name}' does not exist in registry.",
                    is_error=True,
                )
                observations.append(obs)
                await self._emit(
                    AgentEventType.TOOL_FAILED,
                    session_id,
                    {"tool": tool_name, "error": "not_found"},
                )
                continue

            # Validate input arguments against tool schema
            try:
                validated_args = tool.validate(decision.arguments)
            except ValidationError as exc:
                obs = self._context_adapter.format_observation(
                    tool_name=tool.name,
                    output=f"Validation error for '{tool.name}': {exc.message}",
                    is_error=True,
                )
                observations.append(obs)
                await self._emit(
                    AgentEventType.TOOL_FAILED,
                    session_id,
                    {"tool": tool.name, "error": "validation"},
                )
                continue

            # 10. Authorize with Deterministic PolicyEngine
            policy_decision = self._policy_engine.authorize(user_role, tool, validated_args)

            if not policy_decision.allowed:
                obs = self._context_adapter.format_observation(
                    tool_name=tool.name,
                    output=(
                        f"Policy Denial: "
                        f"{policy_decision.reason or 'Unauthorized tool invocation.'}"
                    ),
                    is_error=True,
                )
                observations.append(obs)
                await self._tool_calls.create(
                    session_id=session_id,
                    tool_name=tool.name,
                    arguments=validated_args,
                    risk_level=tool.risk_level,
                    status=ToolCallStatus.REJECTED,
                )
                await self._emit(
                    AgentEventType.TOOL_FAILED,
                    session_id,
                    {"tool": tool.name, "error": "policy_denied"},
                )
                continue

            # 11. Approval Suspension Boundary
            if policy_decision.requires_approval:
                # 1. Create tool call with PENDING_APPROVAL
                tc = await self._tool_calls.create(
                    session_id=session_id,
                    tool_name=tool.name,
                    arguments=validated_args,
                    risk_level=tool.risk_level,
                    status=ToolCallStatus.PENDING_APPROVAL,
                )
                self._audit_log(
                    AuditEventType.AGENT_TOOL_CALL_CREATED,
                    session,
                    payload={
                        "tool": tool.name,
                        "tool_call_id": str(tc.id),
                        "risk_level": tool.risk_level.value,
                    },
                )
                # 2. Compute exact canonical SHA-256 arguments hash
                args_hash = compute_arguments_hash(validated_args)

                # 3. Create durable AgentApproval
                now = datetime.now(UTC)
                expires_at = now + timedelta(hours=_DEFAULT_APPROVAL_TTL_HOURS)
                appr = await self._approvals.create(
                    session_id=session_id,
                    tool_call_id=tc.id,
                    tool_name=tool.name,
                    arguments_hash=args_hash,
                    requested_by=session.user_id,
                    expires_at=expires_at,
                )

                # 4. Transition session RUNNING -> WAITING_FOR_APPROVAL
                validate_agent_transition(session.status, AgentStatus.WAITING_FOR_APPROVAL)
                session = await self._sessions.update_status(
                    session_id, AgentStatus.WAITING_FOR_APPROVAL
                )

                # 5. Emit event
                await self._emit(
                    AgentEventType.APPROVAL_REQUIRED,
                    session_id,
                    {
                        "tool": tool.name,
                        "tool_call_id": str(tc.id),
                        "approval_id": str(appr.id),
                        "arguments_hash": args_hash,
                    },
                )
                self._audit_log(
                    AuditEventType.AGENT_APPROVAL_REQUIRED,
                    session,
                    payload={
                        "tool": tool.name,
                        "approval_id": str(appr.id),
                        "tool_call_id": str(tc.id),
                    },
                )

                # 6. EXIT WORKER IMMEDIATELY (no blocking, no polling)
                logger.info(
                    "Session %s suspended waiting for approval on tool '%s'",
                    session_id,
                    tool.name,
                )
                return session

            # 12. Pre-Approved Execution: Check Cancellation before tool execution
            if await self._is_cancelled(session_id):
                return await self._handle_cancellation(session, metrics, loop_start_time)

            # Enforce cumulative tool call limit before executing tool
            if metrics.total_tool_calls >= limits.max_tool_calls:
                return await self._handle_timeout(
                    session, metrics, cumulative_wall_time, "Max tool calls exceeded."
                )

            # Persist ToolCall with RUNNING
            tc = await self._tool_calls.create(
                session_id=session_id,
                tool_name=tool.name,
                arguments=validated_args,
                risk_level=tool.risk_level,
                status=ToolCallStatus.RUNNING,
            )
            self._audit_log(
                AuditEventType.AGENT_TOOL_CALL_CREATED,
                session,
                payload={"tool": tool.name, "tool_call_id": str(tc.id)},
            )
            await self._emit(AgentEventType.TOOL_STARTED, session_id, {"tool": tool.name})
            self._audit_log(
                AuditEventType.AGENT_TOOL_CALL_STARTED, session, payload={"tool": tool.name}
            )

            # Authoritative execution context
            ctx = ToolExecutionContext(
                workspace_id=session.workspace_id,
                repository_id=session.repository_id,
                user_id=session.user_id,
                session_id=session_id,
                repo_root=repo_root,
                timeout_seconds=30.0,
            )

            t_start = time.monotonic()
            try:
                res = await tool.execute(ctx, validated_args)
                duration_ms = (time.monotonic() - t_start) * 1000.0
                tool_status = ToolCallStatus.COMPLETED if res.success else ToolCallStatus.FAILED

                # Enforce max_output_bytes
                output_to_store = res.output
                if (
                    output_to_store
                    and len(output_to_store.encode("utf-8")) > limits.max_output_bytes
                ):
                    max_bytes = limits.max_output_bytes
                    truncated = output_to_store.encode("utf-8")[:max_bytes].decode(
                        "utf-8", errors="ignore"
                    )
                    output_to_store = (
                        f"{truncated}\n"
                        f"[... Tool output truncated: exceeded {max_bytes} byte limit ...]"
                    )

                await self._tool_calls.complete(
                    tc.id,
                    status=tool_status,
                    output=output_to_store,
                    error_message=res.error,
                    duration_ms=duration_ms,
                    completed_at=datetime.now(UTC),
                )
                evt_type = (
                    AgentEventType.TOOL_COMPLETED if res.success else AgentEventType.TOOL_FAILED
                )
                await self._emit(evt_type, session_id, {"tool": tool.name})
                self._audit_log(
                    AuditEventType.AGENT_TOOL_CALL_COMPLETED
                    if res.success
                    else AuditEventType.AGENT_TOOL_CALL_FAILED,
                    session,
                    payload={"tool": tool.name, "success": res.success},
                )

                obs = self._context_adapter.format_observation(
                    tool_name=tool.name,
                    output=output_to_store if res.success else (res.error or output_to_store),
                    is_error=not res.success,
                )
            except Exception as exc:
                duration_ms = (time.monotonic() - t_start) * 1000.0
                await self._tool_calls.complete(
                    tc.id,
                    status=ToolCallStatus.FAILED,
                    error_message=str(exc),
                    duration_ms=duration_ms,
                    completed_at=datetime.now(UTC),
                )
                await self._emit(AgentEventType.TOOL_FAILED, session_id, {"tool": tool.name})
                self._audit_log(
                    AuditEventType.AGENT_TOOL_CALL_FAILED,
                    session,
                    payload={"tool": tool.name, "error": str(exc)},
                )
                obs = self._context_adapter.format_observation(
                    tool_name=tool.name,
                    output=f"Execution error: {exc}",
                    is_error=True,
                )

            observations.append(obs)

            # Update metrics
            metrics = ExecutionMetrics(
                total_llm_calls=metrics.total_llm_calls,
                total_tool_calls=metrics.total_tool_calls + 1,
                total_input_tokens=metrics.total_input_tokens,
                total_output_tokens=metrics.total_output_tokens,
                wall_time_seconds=metrics.wall_time_seconds + (time.monotonic() - loop_start_time),
                estimated_cost_usd=metrics.estimated_cost_usd,
                total_llm_retries=metrics.total_llm_retries,
            )
            session = await self._sessions.update_metrics(session_id, metrics)

    # ─── Helpers ──────────────────────────────────────────────────────

    def _build_prompt_messages(
        self,
        objective: str,
        context_window: Any,
        observations: list[str],
        tool_specs: list[dict[str, Any]],
    ) -> list[ChatMessage]:
        """Construct the prompt combining immutable system instructions and untrusted data."""
        # 1. Base prompt built through FP7 PromptBuilder
        base_messages = self._prompt_builder.build(
            user_query=objective,
            context_window=context_window,
        )

        # 2. Add tool instructions and decision schema to system message
        tool_descriptions = "\n".join(
            f"- {s['name']}: {s['description']}\n  Schema: {s['parameters_schema']}"
            for s in tool_specs
        )
        tool_instruction = (
            "\n\n### AVAILABLE TOOLS\n"
            f"{tool_descriptions}\n\n"
            "### STRUCTURED DECISION FORMAT\n"
            "You MUST respond ONLY with a JSON object adhering to one of these formats:\n\n"
            "To execute a tool:\n"
            "```json\n"
            '{\n  "type": "tool_call",\n  "tool_name": "<name>",\n  "arguments": {...}\n}\n'
            "```\n\n"
            "When the objective is accomplished:\n"
            '```json\n{\n  "type": "complete",\n  "reason": "<summary>"\n}\n```\n'
        )

        sys_msg = base_messages[0]
        enriched_sys = ChatMessage(
            role=MessageRole.SYSTEM,
            content=sys_msg.content + tool_instruction,
        )
        messages: list[ChatMessage] = [enriched_sys]

        # Add user query message from base_messages (usually last)
        user_msg = (
            base_messages[-1]
            if len(base_messages) > 1
            else ChatMessage(role=MessageRole.USER, content=objective)
        )
        messages.append(user_msg)

        # 3. Add sliding-window compacted observations
        compacted_obs = self._context_adapter.compact_history(observations)
        if compacted_obs:
            obs_block = "\n\n### STEP OBSERVATIONS\n" + "\n\n".join(compacted_obs)
            messages.append(ChatMessage(role=MessageRole.USER, content=obs_block))

        return messages

    async def _resolve_repo_root(self, repository_id: UUID | None) -> str | None:
        """Fetch authoritative local repository root directory if repository exists."""
        if not repository_id or not self._repositories:
            return None
        repo = await self._repositories.get(repository_id)
        return repo.local_path if repo else None

    async def _resolve_user_role(self, workspace_id: UUID, user_id: UUID) -> WorkspaceRole:
        """Resolve authoritative user membership role in the workspace."""
        try:
            membership = await self._workspaces.get_membership(workspace_id, user_id)
            if membership:
                return WorkspaceRole(membership.role)
        except Exception:
            pass
        return WorkspaceRole.VIEWER

    async def _is_cancelled(self, session_id: UUID) -> bool:
        """Check if cancellation has been signaled for this session."""
        if self._cancellation_checker:
            return await self._cancellation_checker.is_cancelled(session_id)
        return False

    async def _handle_cancellation(
        self,
        session: AgentSessionRecord,
        metrics: ExecutionMetrics,
        start_time: float,
    ) -> AgentSessionRecord:
        """Cleanly terminate execution upon cancellation."""
        now = datetime.now(UTC)
        final_metrics = ExecutionMetrics(
            total_llm_calls=metrics.total_llm_calls,
            total_tool_calls=metrics.total_tool_calls,
            total_input_tokens=metrics.total_input_tokens,
            total_output_tokens=metrics.total_output_tokens,
            wall_time_seconds=metrics.wall_time_seconds + (time.monotonic() - start_time),
            estimated_cost_usd=metrics.estimated_cost_usd,
        )
        await self._sessions.update_metrics(session.id, final_metrics)
        validate_agent_transition(session.status, AgentStatus.CANCELLED)
        session = await self._sessions.update_status(
            session.id,
            AgentStatus.CANCELLED,
            cancelled_at=now,
            completed_at=now,
        )
        await self._emit(AgentEventType.CANCELLED, session.id)
        self._audit_log(AuditEventType.AGENT_CANCELLED, session)
        logger.info("Agent session %s cancelled cleanly", session.id)
        return session

    async def _handle_timeout(
        self,
        session: AgentSessionRecord,
        metrics: ExecutionMetrics,
        cumulative_wall_time: float,
        reason: str,
    ) -> AgentSessionRecord:
        """Transition session to TIMED_OUT when execution limit is reached."""
        now = datetime.now(UTC)
        final_metrics = ExecutionMetrics(
            total_llm_calls=metrics.total_llm_calls,
            total_tool_calls=metrics.total_tool_calls,
            total_input_tokens=metrics.total_input_tokens,
            total_output_tokens=metrics.total_output_tokens,
            wall_time_seconds=cumulative_wall_time,
            estimated_cost_usd=metrics.estimated_cost_usd,
            total_llm_retries=metrics.total_llm_retries,
        )
        await self._sessions.update_metrics(session.id, final_metrics)
        validate_agent_transition(session.status, AgentStatus.TIMED_OUT)
        session = await self._sessions.update_status(
            session.id,
            AgentStatus.TIMED_OUT,
            completed_at=now,
        )
        await self._emit(AgentEventType.LIMIT_REACHED, session.id, {"reason": reason})
        await self._emit(AgentEventType.TIMED_OUT, session.id, {"reason": reason})
        self._audit_log(AuditEventType.AGENT_LIMIT_REACHED, session, reason=reason)
        self._audit_log(AuditEventType.AGENT_TIMED_OUT, session, reason=reason)
        logger.warning("Session %s reached limit: %s", session.id, reason)
        return session

    async def _emit(
        self,
        event_type: AgentEventType,
        session_id: UUID,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Safely emit an agent lifecycle domain event."""
        try:
            event = AgentEvent(
                event_type=event_type,
                session_id=session_id,
                timestamp=datetime.now(UTC),
                data=data or {},
            )
            await self._events.publish(event)
        except Exception as exc:
            logger.warning(
                "Failed to publish event %s for session %s: %s",
                event_type,
                session_id,
                exc,
            )
