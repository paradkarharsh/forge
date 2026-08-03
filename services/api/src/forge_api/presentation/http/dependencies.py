from collections.abc import AsyncGenerator
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from forge_api.infrastructure.database import create_session_factory
from forge_api.infrastructure.settings import Settings, get_settings
from forge_api.infrastructure.security import decode_access
async def get_session(settings: Settings = Depends(get_settings)) -> AsyncGenerator[AsyncSession, None]:
    async with create_session_factory(settings)() as session: yield session
_bearer=HTTPBearer()
def current_user_id(token: HTTPAuthorizationCredentials = Depends(_bearer), settings: Settings = Depends(get_settings)):
    try: return decode_access(token.credentials,settings)
    except Exception as error: raise HTTPException(401,"invalid access token") from error
