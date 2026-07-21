from config.database import Document, Chat, Message, DocumentStatus

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update


async def create_document(db: AsyncSession, title: str, path: str, chat_id: UUID):
    doc = Document(title=title, path=path, chat_id=chat_id)

    db.add(doc)

    await db.commit()
    await db.refresh(doc)
    return doc


async def create_chat(db: AsyncSession, title: str, user_id: UUID):
    chat = Chat(title=title, user_id=user_id)

    db.add(chat)

    await db.commit()
    await db.refresh(chat)
    return chat


async def create_message(db: AsyncSession, content: str, chat_id: UUID):
    message = Message(content=content, chat_id=chat_id)

    db.add(message)

    await db.commit()
    await db.refresh(message)
    return message

async def update_document_status(db: AsyncSession, document_id: UUID, status_doc: DocumentStatus):
    await db.execute(update(Document).where(Document.id == document_id).values(status=status_doc))
    
    await db.commit()
    