from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from forge_api.infrastructure.database.models import MembershipModel, WorkspaceModel
from forge_api.presentation.http.dependencies import current_user_id, get_session
router = APIRouter(prefix="/workspaces", tags=["workspaces"])
class WorkspaceInput(BaseModel): name: str = Field(min_length=2, max_length=120)
async def membership(workspace_id: UUID, user_id: str, db: AsyncSession) -> MembershipModel:
    value=await db.scalar(select(MembershipModel).where(MembershipModel.workspace_id==workspace_id, MembershipModel.user_id==UUID(user_id)))
    if not value: raise HTTPException(status.HTTP_403_FORBIDDEN,"workspace access denied")
    return value
@router.get("")
async def list_workspaces(user_id: str=Depends(current_user_id), db: AsyncSession=Depends(get_session)):
    rows=await db.execute(select(WorkspaceModel, MembershipModel.role).join(MembershipModel).where(MembershipModel.user_id==UUID(user_id), WorkspaceModel.deleted_at.is_(None)))
    return [{"id":str(w.id),"name":w.name,"role":role} for w,role in rows]
@router.post("",status_code=201)
async def create_workspace(body: WorkspaceInput,user_id: str=Depends(current_user_id),db: AsyncSession=Depends(get_session)):
    workspace=WorkspaceModel(name=body.name.strip()); db.add(workspace); await db.flush(); db.add(MembershipModel(workspace_id=workspace.id,user_id=UUID(user_id),role="owner")); await db.commit(); return {"id":str(workspace.id),"name":workspace.name,"role":"owner"}
@router.patch("/{workspace_id}")
async def rename_workspace(workspace_id: UUID,body: WorkspaceInput,user_id: str=Depends(current_user_id),db: AsyncSession=Depends(get_session)):
    member=await membership(workspace_id,user_id,db)
    if member.role not in ("owner","admin"): raise HTTPException(403,"insufficient role")
    workspace=await db.get(WorkspaceModel,workspace_id)
    if not workspace or workspace.deleted_at: raise HTTPException(404,"workspace not found")
    workspace.name=body.name.strip(); await db.commit(); return {"id":str(workspace.id),"name":workspace.name}
