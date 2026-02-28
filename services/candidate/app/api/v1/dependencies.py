from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.candidate import CandidateService
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8003/v1/auth/login")

async def get_candidate_service(db: AsyncSession = Depends(get_db)) -> CandidateService:
    return CandidateService(db)

async def get_current_user_tg_id(
    token: str = Depends(oauth2_scheme)
) -> int:
    """
    Валидирует JWT токен и извлекает telegram_id.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        telegram_id: Optional[int] = payload.get("tg_id")
        
        if telegram_id is None:
            raise credentials_exception
            
        return telegram_id
        
    except JWTError:
        raise credentials_exception

async def require_auth(
    telegram_id: int = Depends(get_current_user_tg_id)
) -> int:
    """
    Просто возвращает ID, полученный из токена.
    """
    return telegram_id

async def verify_candidate_ownership(
    telegram_id: int,
    current_user_id: int = Depends(require_auth)
):
    """
    Проверка, что пользователь меняет свой профиль.
    """
    if telegram_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this profile."
        )
