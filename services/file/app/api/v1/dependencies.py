from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.services.file import FileService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8003/v1/auth/login")


async def get_service(db: AsyncSession = Depends(get_db)) -> FileService:
    return FileService(db)


async def get_current_user_tg_id(token: str = Depends(oauth2_scheme)) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        telegram_id: int | None = payload.get("tg_id")
        if telegram_id is None:
            raise credentials_exception
        return telegram_id
    except JWTError:
        raise credentials_exception
