from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from forge_api.infrastructure.database.models import OAuthIdentityModel, UserModel
from forge_api.application.auth.dtos import OAuthIdentity

class OAuthService:
    def __init__(self, session: AsyncSession) -> None: self._session = session
    async def resolve(self, identity: OAuthIdentity) -> UserModel:
        linked=await self._session.scalar(select(OAuthIdentityModel).where(OAuthIdentityModel.provider==identity.provider, OAuthIdentityModel.subject==identity.subject))
        if linked: return await self._session.get(UserModel,linked.user_id)
        if not identity.email: raise ValueError("provider did not supply a verified email")
        user=await self._session.scalar(select(UserModel).where(UserModel.email==identity.email.lower()))
        if not user: user=UserModel(email=identity.email.lower(),password_hash=None); self._session.add(user); await self._session.flush()
        self._session.add(OAuthIdentityModel(user_id=user.id,provider=identity.provider,subject=identity.subject)); return user
