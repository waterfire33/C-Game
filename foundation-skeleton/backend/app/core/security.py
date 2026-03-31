from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt


from pwdlib import PasswordHash

from app.core.config import get_settings



ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()




def hash_password(password: str) -> str:
    return password_hash.hash(password)




def verify_password(plain_password: str, stored_hash: str) -> bool:
    # Try pwdlib first
    try:
        if password_hash.verify(plain_password, stored_hash):
            return True
    except Exception:
        pass
    # Fallback: try legacy Passlib-bcrypt, and if successful, re-hash with pwdlib
    try:
        from passlib.context import CryptContext
        legacy_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        if legacy_context.verify(plain_password, stored_hash):
            # Optionally: re-hash and return new hash for storage
            # This requires a DB update, so only return True here
            return True
    except Exception:
        pass
    return False


def create_access_token(subject: str, tenant_id: str) -> str:
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {"sub": subject, "tenant_id": tenant_id, "exp": expire}
    return jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)
