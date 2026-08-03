from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from forge_api.infrastructure.session_repository import SessionRepository
from forge_api.presentation.http.dependencies import current_user_id,get_session
from forge_api.infrastructure.audit import AuditLogger
router=APIRouter(prefix="/sessions",tags=["sessions"])
@router.get("")
async def list_sessions(user_id: str=Depends(current_user_id),db: AsyncSession=Depends(get_session)):
    return {"success":True,"data":[{"id":str(x.id),"device_name":x.device_name,"ip_address":x.ip_address,"user_agent":x.user_agent,"last_active_at":x.last_active_at,"expires_at":x.expires_at} for x in await SessionRepository(db).list_active(UUID(user_id))],"meta":{}}
@router.delete("/{session_id}",status_code=204)
async def revoke_session(session_id: UUID,user_id: str=Depends(current_user_id),db: AsyncSession=Depends(get_session)):
    if not (await SessionRepository(db).revoke(session_id,UUID(user_id))).rowcount: raise HTTPException(404,"session not found")
    AuditLogger(db).record("auth.session_revoked",UUID(user_id)); await db.commit()
@router.delete("",status_code=204)
async def revoke_all(user_id: str=Depends(current_user_id),db: AsyncSession=Depends(get_session)): await SessionRepository(db).revoke_all(UUID(user_id)); await db.commit()
