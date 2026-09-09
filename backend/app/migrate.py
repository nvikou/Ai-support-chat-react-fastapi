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
    await conn.execute(text("""
        ALTER TABLE knowledge_documents
        ADD COLUMN IF NOT EXISTS status VARCHAR(20)
        DEFAULT 'indexed'
    """))
    await conn.execute(text("""
        ALTER TABLE knowledge_documents
        ADD COLUMN IF NOT EXISTS error_message TEXT
    """))
    await conn.execute(text("""
        ALTER TABLE knowledge_documents
        ADD COLUMN IF NOT EXISTS storage_path VARCHAR(512)
    """))
