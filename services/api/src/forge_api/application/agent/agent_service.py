"""Application service for Agent sessions, lifecycle, execution, and approvals.

Enforces:
- Workspace membership and role-based permissions
- Repository access boundaries
- Parent-child ownership (workspace -> session -> approval/tool_call/step)
- Prevention of all IDOR / BOLA vulnerabilities
- Durable background job enqueuing for worker execution
"""

import hmac
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from forge_api.domain.agent import (
    AgentEvent,
    AgentEventPublisher,
    AgentEventType,
    AgentLimits,
    AgentSessionRecord,
    AgentStatus,
    AgentStepRecord,
    AgentToolCallRecord,
    ToolCallStatus,
)
from forge_api.domain.approval import (
    AgentApprovalRecord,
    ApprovalStatus,
    compute_arguments_hash,
)
from forge_api.domain.audit import AuditEventType
from forge_api.domain.auth import WorkspaceRole
from forge_api.domain.errors import (
    AuthorizationError,
    DomainError,
    NotFoundError,
)
from forge_api.domain.repositories import (
    AgentApprovalRepository,
    AgentJobQueue,
    AgentSessionRepository,
    AgentStepRepository,
    AgentToolCallRepository,
    RepositoryRepository,
    WorkspaceRepository,
)
from forge_api.domain.repository import SyncJobType
from forge_api.domain.tool import redact_secrets
from forge_api.infrastructure.workers.agent_worker import RedisAgentCoordinator

logger = logging.getLogger(__name__)

RUN_ROLES = frozenset(
    {
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.MAINTAINER,
        WorkspaceRole.DEVELOPER,
    }
)

APPROVAL_ROLES = frozenset(
    {
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.MAINTAINER,
    }
)


class AgentService:
    """Orchestrates agent HTTP operations against domain repositories and job queue."""

    def __init__(
        self,
        *,
        sessions: AgentSessionRepository,
        steps: AgentStepRepository,
        tool_calls: AgentToolCallRepository,
        approvals: AgentApprovalRepository,
        workspaces: WorkspaceRepository,
        repositories: RepositoryRepository,
        job_queue: AgentJobQueue,
        coordinator: RedisAgentCoordinator | None = None,
        event_publisher: AgentEventPublisher | None = None,
        audit: Any | None = None,
    ) -> None:
        self._sessions = sessions
        self._steps = steps
        self._tool_calls = tool_calls
        self._approvals = approvals
        self._workspaces = workspaces
        self._repositories = repositories
        self._job_queue = job_queue
        self._coordinator = coordinator
        self._events = event_publisher
        self._audit = audit

    def _audit_log(
        self,
        event_type: AuditEventType,
        session: AgentSessionRecord | None = None,
        *,
        user_id: UUID | None = None,
        workspace_id: UUID | None = None,
        session_id: UUID | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not self._audit:
            return
        wid = workspace_id or (session.workspace_id if session else None)
        sid = session_id or (session.id if session else None)
        uid = user_id or (session.user_id if session else None)
        safe_payload = {}
        if wid:
            safe_payload["workspace_id"] = str(wid)
        if sid:
            safe_payload["session_id"] = str(sid)
        if session and session.repository_id:
            safe_payload["repository_id"] = str(session.repository_id)
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
                user_id=uid,
                session_id=sid,
                reason=reason,
                payload=safe_payload,
            )
        except Exception as exc:
            logger.warning("Failed to record audit event %s: %s", event_type, exc)

    async def _require_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        allowed_roles: frozenset[WorkspaceRole] | None = None,
    ) -> WorkspaceRole:

        member = await self._workspaces.get_membership(workspace_id, user_id)
        if not member:
            raise AuthorizationError(
                "User is not a member of this workspace.",
                code="workspace_access_denied",
            )
        role = member.role if isinstance(member.role, WorkspaceRole) else WorkspaceRole(member.role)
        if allowed_roles and role not in allowed_roles:
            raise AuthorizationError(
                f"Role '{role.value}' is not authorized for this operation.",
                code="permission_denied",
            )
        return role

    async def _get_verified_session(
        self, workspace_id: UUID, session_id: UUID, user_id: UUID
    ) -> AgentSessionRecord:
        await self._require_member(workspace_id, user_id)
        session = await self._sessions.get(session_id)
        if not session or session.workspace_id != workspace_id:
            raise NotFoundError(
                f"Agent session '{session_id}' not found in workspace '{workspace_id}'.",
                code="agent_session_not_found",
            )
        return session

    async def create_session(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        objective: str,
        repository_id: UUID | None = None,
        conversation_id: UUID | None = None,
        model: str | None = None,
        limits: AgentLimits | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentSessionRecord:
        await self._require_member(workspace_id, user_id, RUN_ROLES)

        if repository_id is not None:
            repo = await self._repositories.get(repository_id)
            if not repo or repo.workspace_id != workspace_id:
                raise NotFoundError(
                    f"Repository '{repository_id}' not found in workspace '{workspace_id}'.",
                    code="repository_not_found",
                )

        session = await self._sessions.create(
            workspace_id=workspace_id,
            user_id=user_id,
            objective=objective,
            status=AgentStatus.CREATED,
            repository_id=repository_id,
            conversation_id=conversation_id,
            model=model,
            limits=limits or AgentLimits(),
            metadata=metadata or {},
        )
        logger.info("Created agent session %s in workspace %s", session.id, workspace_id)
        if self._events:
            try:
                await self._events.publish(
                    AgentEvent(
                        session_id=session.id,
                        event_type=AgentEventType.CREATED,
                        timestamp=session.created_at,
                        data={"workspace_id": str(workspace_id), "user_id": str(user_id)},
                    )
                )
            except Exception:
                pass
        self._audit_log(
            AuditEventType.AGENT_CREATED,
            session,
            user_id=user_id,
            payload={"objective": objective[:200]},
        )
        return session

    async def list_sessions(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        repository_id: UUID | None = None,
        status: AgentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AgentSessionRecord], int]:
        await self._require_member(workspace_id, user_id)
        if repository_id is not None:
            repo = await self._repositories.get(repository_id)
            if not repo or repo.workspace_id != workspace_id:
                raise NotFoundError(
                    f"Repository '{repository_id}' not found in workspace '{workspace_id}'.",
                    code="repository_not_found",
                )

        sessions = await self._sessions.list_by_workspace(
            workspace_id,
            repository_id=repository_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        total = await self._sessions.count_by_workspace(
            workspace_id,
            repository_id=repository_id,
            status=status,
        )
        return sessions, total

    async def get_session(
        self,
        *,
        workspace_id: UUID,
        session_id: UUID,
        user_id: UUID,
    ) -> AgentSessionRecord:
        return await self._get_verified_session(workspace_id, session_id, user_id)

    async def run_session(
        self,
        *,
        workspace_id: UUID,
        session_id: UUID,
        user_id: UUID,
    ) -> AgentSessionRecord:
        await self._require_member(workspace_id, user_id, RUN_ROLES)
        session = await self._get_verified_session(workspace_id, session_id, user_id)

        # Validate agent state: only CREATED or PLANNING can be launched with run
        if session.status in (
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
            AgentStatus.TIMED_OUT,
            AgentStatus.EXPIRED,
        ):
            raise DomainError(
                f"Cannot run session '{session_id}' in terminal status '{session.status.value}'.",
                code="invalid_agent_state",
            )

        if session.status in (AgentStatus.RUNNING, AgentStatus.WAITING_FOR_APPROVAL):
            raise DomainError(
                f"Session '{session_id}' is already active with status '{session.status.value}'.",
                code="agent_already_running",
            )

        # Enqueue durable background job for worker
        await self._job_queue.enqueue(
            session_id=session.id,
            job_type=SyncJobType.AGENT_EXECUTE.value,
            metadata={"enqueued_by": str(user_id)},
        )

        # Wake up workers via Redis notification if available
        if self._coordinator:
            await self._coordinator.notify_new_job()

        if self._events:
            try:
                await self._events.publish(
                    AgentEvent(
                        session_id=session.id,
                        event_type=AgentEventType.RUN_REQUESTED,
                        timestamp=datetime.now(UTC),
                        data={"user_id": str(user_id)},
                    )
                )
            except Exception:
                pass
        self._audit_log(
            AuditEventType.AGENT_RUN_REQUESTED,
            session,
            user_id=user_id,
        )

        logger.info("Enqueued AGENT_EXECUTE job for session %s", session.id)
        return session

    async def cancel_session(
        self,
        *,
        workspace_id: UUID,
        session_id: UUID,
        user_id: UUID,
    ) -> AgentSessionRecord:
        await self._require_member(workspace_id, user_id, RUN_ROLES)
        session = await self._get_verified_session(workspace_id, session_id, user_id)

        # Idempotent cancellation
        if session.status == AgentStatus.CANCELLED:
            return session

        if session.status in (
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.TIMED_OUT,
            AgentStatus.EXPIRED,
        ):
            # Already terminal, cancellation is a no-op
            return session

        now = datetime.now(UTC)
        updated = await self._sessions.update_status(
            session_id, AgentStatus.CANCELLED, cancelled_at=now
        )
        session = updated or session

        # Signal cancellation via Redis if available
        if self._coordinator:
            await self._coordinator.signal_cancellation(session_id)

        # Emit domain event
        if self._events:
            event = AgentEvent(
                session_id=session_id,
                event_type=AgentEventType.CANCELLED,
                timestamp=now,
                data={"cancelled_by": str(user_id)},
            )
            await self._events.publish(event)

        self._audit_log(
            AuditEventType.AGENT_CANCEL_REQUESTED,
            session,
            user_id=user_id,
        )
        self._audit_log(
            AuditEventType.AGENT_CANCELLED,
            session,
            user_id=user_id,
        )

        logger.info("Cancelled agent session %s", session_id)
        return session

    async def get_steps(
        self,
        *,
        workspace_id: UUID,
        session_id: UUID,
        user_id: UUID,
    ) -> list[AgentStepRecord]:
        await self._get_verified_session(workspace_id, session_id, user_id)
        return await self._steps.list_by_session(session_id)

    async def get_tool_calls(
        self,
        *,
        workspace_id: UUID,
        session_id: UUID,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentToolCallRecord]:
        await self._get_verified_session(workspace_id, session_id, user_id)
        return await self._tool_calls.list_by_session(session_id, limit=limit, offset=offset)

    async def get_approvals(
        self,
        *,
        workspace_id: UUID,
        session_id: UUID,
        user_id: UUID,
    ) -> list[AgentApprovalRecord]:
        await self._get_verified_session(workspace_id, session_id, user_id)
        return await self._approvals.list_by_session(session_id)

    async def grant_approval(
        self,
        *,
        workspace_id: UUID,
        session_id: UUID,
        approval_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> AgentApprovalRecord:
        await self._require_member(workspace_id, user_id, APPROVAL_ROLES)
        session = await self._get_verified_session(workspace_id, session_id, user_id)

        approval = await self._approvals.get(approval_id)
        if not approval or approval.session_id != session.id:
            raise NotFoundError(
                f"Approval '{approval_id}' not found for session '{session_id}'.",
                code="approval_not_found",
            )

        if approval.status != ApprovalStatus.PENDING:
            raise DomainError(
                f"Approval is already in status '{approval.status.value}'.",
                code="approval_already_decided",
            )

        now = datetime.now(UTC)
        if approval.expires_at and approval.expires_at <= now:
            await self._approvals.decide(
                approval.id, status=ApprovalStatus.EXPIRED, decided_by=user_id, decided_at=now
            )
            await self._sessions.update_status(session.id, AgentStatus.EXPIRED, completed_at=now)
            raise DomainError("Approval has expired.", code="approval_expired")

        tool_call = await self._tool_calls.get(approval.tool_call_id)
        if not tool_call or tool_call.session_id != session.id:
            raise NotFoundError(
                "Associated tool call not found for approval.",
                code="tool_call_not_found",
            )

        if tool_call.status != ToolCallStatus.PENDING_APPROVAL:
            raise DomainError(
                f"Tool call '{tool_call.id}' is in status '{tool_call.status.value}', "
                "expected 'pending_approval'.",
                code="tool_call_already_executed",
            )

        recomputed_hash = compute_arguments_hash(tool_call.arguments)
        if not hmac.compare_digest(recomputed_hash, approval.arguments_hash):
            logger.error("Tampered tool arguments for approval %s: hash mismatch.", approval.id)
            await self._tool_calls.complete(
                tool_call.id,
                status=ToolCallStatus.FAILED,
                error_message="Tampered tool arguments: cryptographic hash mismatch.",
            )
            await self._sessions.update_status(session.id, AgentStatus.FAILED, completed_at=now)
            raise DomainError(
                "Tampered tool arguments: cryptographic hash mismatch.",
                code="approval_hash_mismatch",
            )

        # Atomically transition approval to GRANTED
        decided = await self._approvals.decide(
            approval.id,
            status=ApprovalStatus.GRANTED,
            decided_by=user_id,
            reason=reason,
            decided_at=now,
        )

        # Transition session to RUNNING
        await self._sessions.update_status(session.id, AgentStatus.RUNNING)

        # Enqueue AGENT_RESUME job
        await self._job_queue.enqueue(
            session_id=session.id,
            job_type=SyncJobType.AGENT_RESUME.value,
            metadata={"resumed_by": str(user_id), "approval_id": str(approval.id)},
        )

        # Wake worker via Redis
        if self._coordinator:
            await self._coordinator.notify_new_job()

        # Emit event
        if self._events:
            event = AgentEvent(
                session_id=session.id,
                event_type=AgentEventType.APPROVAL_GRANTED,
                timestamp=now,
                data={
                    "approval_id": str(approval.id),
                    "tool_call_id": str(tool_call.id),
                    "decided_by": str(user_id),
                },
            )
            await self._events.publish(event)
            event_resumed = AgentEvent(
                session_id=session.id,
                event_type=AgentEventType.RESUMED,
                timestamp=now,
                data={"approval_id": str(approval.id)},
            )
            await self._events.publish(event_resumed)

        self._audit_log(
            AuditEventType.AGENT_APPROVAL_GRANTED,
            session,
            user_id=user_id,
            payload={
                "approval_id": str(approval.id),
                "tool_call_id": str(tool_call.id),
                "tool_name": approval.tool_name,
            },
        )
        self._audit_log(
            AuditEventType.AGENT_RESUMED,
            session,
            user_id=user_id,
            reason="approval_granted",
        )

        logger.info("Granted approval %s for session %s", approval.id, session.id)
        return decided or approval

    async def deny_approval(
        self,
        *,
        workspace_id: UUID,
        session_id: UUID,
        approval_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> AgentApprovalRecord:
        await self._require_member(workspace_id, user_id, APPROVAL_ROLES)
        session = await self._get_verified_session(workspace_id, session_id, user_id)

        approval = await self._approvals.get(approval_id)
        if not approval or approval.session_id != session.id:
            raise NotFoundError(
                f"Approval '{approval_id}' not found for session '{session_id}'.",
                code="approval_not_found",
            )

        if approval.status != ApprovalStatus.PENDING:
            raise DomainError(
                f"Approval is already in status '{approval.status.value}'.",
                code="approval_already_decided",
            )

        now = datetime.now(UTC)
        decided = await self._approvals.decide(
            approval.id,
            status=ApprovalStatus.DENIED,
            decided_by=user_id,
            reason=reason,
            decided_at=now,
        )

        # Complete tool call as failed/denied
        tool_call = await self._tool_calls.get(approval.tool_call_id)
        if tool_call and tool_call.session_id == session.id:
            msg = f"Human review rejected tool execution: {reason or 'No reason provided.'}"
            await self._tool_calls.complete(
                tool_call.id,
                status=ToolCallStatus.FAILED,
                error_message=msg,
                completed_at=now,
            )

        # Transition session to RUNNING so agent model can respond to denial
        await self._sessions.update_status(session.id, AgentStatus.RUNNING)

        # Enqueue AGENT_RESUME job
        await self._job_queue.enqueue(
            session_id=session.id,
            job_type=SyncJobType.AGENT_RESUME.value,
            metadata={"resumed_by": str(user_id), "approval_id": str(approval.id)},
        )

        if self._coordinator:
            await self._coordinator.notify_new_job()
        # Emit event
        if self._events:
            event = AgentEvent(
                session_id=session.id,
                event_type=AgentEventType.APPROVAL_DENIED,
                timestamp=now,
                data={
                    "approval_id": str(approval.id),
                    "decided_by": str(user_id),
                    "reason": reason,
                },
            )
            await self._events.publish(event)

        self._audit_log(
            AuditEventType.AGENT_APPROVAL_DENIED,
            session,
            user_id=user_id,
            reason=reason,
            payload={
                "approval_id": str(approval.id),
                "tool_name": approval.tool_name,
            },
        )

        logger.info("Denied approval %s for session %s", approval.id, session.id)
        return decided or approval
