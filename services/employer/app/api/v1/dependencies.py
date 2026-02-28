from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.employer import EmployerService
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8003/v1/auth/login")

async def get_service(db: AsyncSession = Depends(get_db)) -> EmployerService:
    return EmployerService(db)

async def get_current_user_tg_id(token: str = Depends(oauth2_scheme)) -> int:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        tg_id = payload.get("tg_id")
        if tg_id is None: raise HTTPException(status_code=401)
        return tg_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
