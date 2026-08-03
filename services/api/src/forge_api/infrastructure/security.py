from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
import jwt
from pwdlib import PasswordHash
from forge_api.infrastructure.settings import Settings

_passwords = PasswordHash.recommended()
def hash_password(value: str) -> str: return _passwords.hash(value)
def verify_password(value: str, hashed: str) -> bool: return _passwords.verify(value, hashed)
def hash_refresh(value: str) -> str: return sha256(value.encode()).hexdigest()
def new_refresh() -> str: return token_urlsafe(48)
def create_access(user_id: str, settings: Settings) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(UTC) + timedelta(minutes=15)}, settings.jwt_secret.get_secret_value(), algorithm="HS256")
def decode_access(token: str, settings: Settings) -> str: return str(jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"])["sub"])
