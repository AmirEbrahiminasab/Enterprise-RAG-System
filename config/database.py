from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, Float, Enum as SQLEnum
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import relationship, DeclarativeBase

import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, EmailStr

DATABASE_URL = "postgresql+asyncpg://dev_user:dev_password@local_postgres:5432/dev_database"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSession = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


class UserCreate(BaseModel):
    name: str
    email: EmailStr 
    password: str

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
    hashed_password = Column(String, nullable=False)

    documents = relationship('Document', back_populates='user')
    chats = relationship('Chat', back_populates='user')


class Document(Base):                                                                                                                                                                                                                                                                                                   
    __tablename__ = 'documents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))

    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING)

    user = relationship('User', back_populates='documents')


class Chat(Base):
    __tablename__ = 'chats'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))

    user = relationship('User', back_populates='chats')
    messages = relationship('Message', back_populates='chat')


class Message(Base):
    __tablename__ = 'messages'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(String, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    chat_id = Column(UUID(as_uuid=True), ForeignKey('chats.id'))

    chat = relationship('Chat', back_populates='messages')

async def create_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session():
    async with AsyncSession() as session:
        try:
            yield session
        finally:
            await session.close()