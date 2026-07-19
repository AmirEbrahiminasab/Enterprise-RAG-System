from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, Float, Enum as SQLEnum
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import relationship, DeclarativeBase

import uuid
from datetime import datetime
from enum import Enum

DATABASE_URL = "postgresql+asyncpg://dev_user:dev_password@localhost:5432/dev_database"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# RabbitMQ enum
class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class User(Base):
    __tablename__ = 'users'                                                                                                                     
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)                                                                                                                                                   
    email = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship('Document', back_populates='user')


class Document(Base):                                                                                                                                                                                                                                                                                                   
    __tablename__ = 'documents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))

    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING)

    user = relationship('User', back_populates='documents')


async def create_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session():
    async with AsyncSession() as session:
        try:
            yield session
        finally:
            await session.close()