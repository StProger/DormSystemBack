from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ...core.database import get_db
from ...core.security import verify_password, create_access_token, hash_password
from ...models.user import User, UserRole
from ...schemas.auth import LoginIn, TokenOut
from ...schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(User).where(User.email == data.email))
    user = q.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(sub=str(user.id), role=user.role.value)
    return TokenOut(access_token=token)

# Удобный эндпоинт для первичного заведения админа (после — закомментируй/удали)
@router.post("/dev-create-admin", response_model=UserOut)
async def dev_create_admin(db: AsyncSession = Depends(get_db)):
    # !!! Не оставляй в проде. Для первого запуска.
    user = (await db.execute(select(User).where(User.email == "admin2@example.com"))).scalar_one_or_none()
    if user:
        return UserOut(
        id=str(user.id),
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        phone=user.phone
    )
    new_user = User(
        email="admin2@example.com",
        password_hash=hash_password("admin123"),
        role=UserRole.head,
        full_name="Dorm Admin",
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserOut(
        id=str(new_user.id),
        email=new_user.email,
        role=new_user.role,
        full_name=new_user.full_name,
        phone=new_user.phone
    )
