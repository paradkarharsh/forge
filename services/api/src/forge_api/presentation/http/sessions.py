"""Session management routes."""
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from forge_api.application.auth.session_service import SessionService
from forge_api.presentation.http.contracts import ok
from forge_api.presentation.http.dependencies import (
    client_ip,
    client_user_agent,
    current_claims,
    get_session_service,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    claims=Depends(current_claims),
    session_svc: SessionService = Depends(get_session_service),
):
    views = await session_svc.list_sessions(claims.user_id)
    return ok(
        [
            {
                "id": str(v.id),
                "device_name": v.device_name,
                "ip_address": v.ip_address,
                "user_agent": v.user_agent,
                "last_active_at": v.last_active_at.isoformat(),
                "expires_at": v.expires_at.isoformat(),
            }
            for v in views
        ]
    )


@router.delete("/{session_id}", status_code=204)
async def revoke_session(
    session_id: UUID,
    request: Request,
    claims=Depends(current_claims),
    session_svc: SessionService = Depends(get_session_service),
):
    await session_svc.revoke(
        session_id,
        claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )


@router.delete("", status_code=204)
async def revoke_all(
    request: Request,
    claims=Depends(current_claims),
    session_svc: SessionService = Depends(get_session_service),
):
    await session_svc.revoke_all(
        claims.user_id,
        ip_address=client_ip(request),
        user_agent=client_user_agent(request),
    )
