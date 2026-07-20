from config.database import Document

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


async def create_document(db: AsyncSession, title: str, path: str, user_id: UUID):
    doc = Document(title=title, path=path, user_id=user_id)

    db.add(doc)

    await db.commit()
    await db.refresh(doc)
    return doc
