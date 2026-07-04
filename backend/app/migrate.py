from sqlalchemy import text


async def run_migrations(conn) -> None:
    await conn.execute(text("""
        ALTER TABLE conversations
        ADD COLUMN IF NOT EXISTS user_id VARCHAR(36)
    """))
    await conn.execute(text("""
        ALTER TABLE conversations
        ADD COLUMN IF NOT EXISTS title VARCHAR(255)
    """))
