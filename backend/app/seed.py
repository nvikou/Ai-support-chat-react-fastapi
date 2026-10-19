from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User
from app.security import hash_password


async def seed_admin(db: AsyncSession) -> None:
    # Resolve settings at call time — module-level cache can capture
    # stale env from an earlier import during tests.
    settings = get_settings()
    result = await db.execute(select(User).where(User.role == "admin"))
    if result.scalar_one_or_none():
        return

    existing = await db.execute(
        select(User).where(User.email == settings.admin_email)
    )
    if existing.scalar_one_or_none():
        return

    admin = User(
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        full_name="Administrator",
        role="admin",
    )
    db.add(admin)
    await db.commit()
