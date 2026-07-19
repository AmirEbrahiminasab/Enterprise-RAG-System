from config.database import Document

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_documents(db: AsyncSession, user_id: UUID):
    query = select(Document).where(Document.user_id == user_id)
    
    results = await db.execute(query)
    return results.scalars().all()

async def create_document(db: AsyncSession, title: str, path: str):
    doc = Document(title=title, path=path)

    db.add(doc)

    await db.commit()
    await db.refresh(doc)
    return doc
