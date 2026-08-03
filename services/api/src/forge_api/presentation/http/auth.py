from datetime import UTC, datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from forge_api.infrastructure.database.models import SessionModel, UserModel
from forge_api.infrastructure.security import create_access, hash_password, hash_refresh, new_refresh, verify_password
from forge_api.infrastructure.settings import Settings, get_settings
from forge_api.presentation.http.dependencies import get_session
from forge_api.presentation.http.dependencies import current_user_id
from forge_api.infrastructure.audit import AuditLogger
router = APIRouter(prefix="/auth", tags=["auth"])
class Credentials(BaseModel): email: EmailStr; password: str = Field(min_length=12, max_length=128)
def issue(user: UserModel, db: AsyncSession, settings: Settings, response: Response, request: Request) -> dict[str, str]:
    refresh = new_refresh(); db.add(SessionModel(user_id=user.id, refresh_hash=hash_refresh(refresh), expires_at=datetime.now(UTC)+timedelta(days=30),ip_address=request.client.host if request.client else None,user_agent=request.headers.get("user-agent"),device_name=request.headers.get("sec-ch-ua-platform")))
    response.set_cookie("forge_refresh", refresh, httponly=True, secure=settings.environment != "development", samesite="lax", path="/auth")
    return {"access_token": create_access(str(user.id), settings), "token_type": "bearer"}
@router.post("/refresh")
async def refresh(response: Response, request: Request, forge_refresh: str | None = Cookie(default=None), db: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    if not forge_refresh: raise HTTPException(401, "missing refresh token")
    session=await db.scalar(select(SessionModel).where(SessionModel.refresh_hash==hash_refresh(forge_refresh)))
    if not session or session.revoked_at or session.expires_at < datetime.now(UTC):
        if session: await db.execute(update(SessionModel).where(SessionModel.family_id==session.family_id).values(revoked_at=datetime.now(UTC))); AuditLogger(db).record("auth.refresh_reuse_detected",session.user_id)
        await db.commit(); response.delete_cookie("forge_refresh",path="/auth"); raise HTTPException(401,"refresh token rejected")
    session.replaced_at=datetime.now(UTC); session.revoked_at=datetime.now(UTC)
    user=await db.get(UserModel,session.user_id)
    replacement=new_refresh()
    db.add(SessionModel(user_id=user.id,refresh_hash=hash_refresh(replacement),expires_at=datetime.now(UTC)+timedelta(days=30),family_id=session.family_id,ip_address=request.client.host if request.client else None,user_agent=request.headers.get("user-agent"),device_name=request.headers.get("sec-ch-ua-platform")))
    response.set_cookie("forge_refresh",replacement,httponly=True,secure=settings.environment != "development",samesite="lax",path="/auth")
    AuditLogger(db).record("auth.refresh_rotated",user.id); await db.commit(); return {"access_token":create_access(str(user.id),settings),"token_type":"bearer"}
@router.post("/register", status_code=201)
async def register(body: Credentials, response: Response, request: Request, db: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    if await db.scalar(select(UserModel).where(UserModel.email == body.email.lower())): raise HTTPException(409, "email already registered")
    user=UserModel(email=body.email.lower(), password_hash=hash_password(body.password)); db.add(user); await db.flush(); result=issue(user, db, settings, response, request); await db.commit(); return result
@router.post("/login")
async def login(body: Credentials, response: Response, request: Request, db: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    user=await db.scalar(select(UserModel).where(UserModel.email == body.email.lower()))
    if not user or not user.password_hash or not verify_password(body.password,user.password_hash): raise HTTPException(401,"invalid credentials")
    result=issue(user,db,settings,response,request); await db.commit(); return result
@router.post("/logout-all", status_code=204)
async def logout_all(response: Response, user_id: str = Depends(current_user_id), db: AsyncSession = Depends(get_session)):
    await db.execute(update(SessionModel).where(SessionModel.user_id==UUID(user_id),SessionModel.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)))
    AuditLogger(db).record("auth.logout_all",UUID(user_id)); await db.commit(); response.delete_cookie("forge_refresh",path="/auth"); return {"success":True,"data":{},"meta":{}}
@router.post("/logout", status_code=204)
async def logout(response: Response): response.delete_cookie("forge_refresh", path="/auth")
