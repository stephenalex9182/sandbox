from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from backend.config import get_settings
hasher = PasswordHash.recommended()
def hash_password(password: str) -> str: return hasher.hash(password)
def verify_password(password: str, encoded: str) -> bool: return hasher.verify(password, encoded)
def create_token(user_id: int) -> str:
    s = get_settings(); exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, s.jwt_secret, algorithm="HS256")
def decode_token(token: str) -> int:
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    return int(payload["sub"])
