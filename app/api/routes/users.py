from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ...api.deps import get_current_user
from ...core.database import get_db
from ...schemas.user import UserOut
from ...models.user import User

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserOut)
async def get_me(
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return UserOut.model_validate(current)
