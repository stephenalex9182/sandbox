import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.database.db import get_db
from backend.database.models import User
from backend.auth.security import decode_token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try: uid = decode_token(token)
    except (jwt.PyJWTError, ValueError, KeyError): raise HTTPException(401, "Invalid or expired access token")
    user = db.get(User, uid)
    if not user: raise HTTPException(401, "User account not found")
    return user
