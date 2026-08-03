from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from forge_api.application.auth.dtos import OAuthIdentity
from forge_api.application.auth.oauth_service import OAuthService
from forge_api.infrastructure.oauth import exchange_code
from forge_api.infrastructure.settings import Settings, get_settings
from forge_api.presentation.http.dependencies import get_session
router=APIRouter(prefix="/oauth",tags=["oauth"])
@router.get("/{provider}/callback")
async def callback(provider: str, code: str=Query(min_length=1), redirect_uri: str=Query(min_length=1), db: AsyncSession=Depends(get_session), settings: Settings=Depends(get_settings)):
    try: profile=await exchange_code(provider,code,redirect_uri,settings)
    except (RuntimeError,ValueError) as error: raise HTTPException(503,"OAuth provider is not configured") from error
    subject=str(profile.get("sub") or profile.get("id") or "")
    if not subject: raise HTTPException(400,"OAuth provider response has no subject")
    user=await OAuthService(db).resolve(OAuthIdentity(provider,subject,profile.get("email")))
    await db.commit(); return {"user_id":str(user.id),"provider":provider}
