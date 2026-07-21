from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .auth.auth import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, verify_password, get_password_hash, check_chat_access
from datetime import timedelta

from config.database import create_database, get_session, Document, User, Chat, Message
from config.elastic import create_elastic_index
from config.schemas import UserCreate, ChatCreate, MessageCreate
from config.s3 import upload_to_s3
from .documents.services import create_document, create_chat, create_message
from workers.cpu_document_worker import start_document_processing


@asynccontextmanager
async def lifespan(app):
    await create_database()
    await create_elastic_index()
    yield

app = FastAPI(lifespan=lifespan)

## These two endpoints were implemented completely by AI
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/signup")
async def sign_up(user_data: UserCreate, session: AsyncSession = Depends(get_session)):
    query = select(User).where(User.email == user_data.email)
    result = await session.execute(query)
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email already registered"
        )
    
    hashed_pwd = get_password_hash(user_data.password)
    
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hashed_pwd
    )
    
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    
    return {
        "message": "User created successfully", 
        "user_id": new_user.id
    }


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/new_chat")
async def create_new_chat(chat_data: ChatCreate, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    chat = await create_chat(session, chat_data.title, current_user.id)

    return {"message": "Chat created successfully with id {}".format(chat.id)}

@app.get("/chat")
async def get_all_chats(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    query = select(Chat).where(Chat.user_id == current_user.id)

    result = await session.execute(query)
    chats = result.scalars().all()

    if not chats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chats not found",
        )

    return {"chats": chats}

@app.get("/chat/{chat_id}")
async def get_chat(chat_id: UUID, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    query = select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    result = await session.execute(query)
    chat = result.scalars().first()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    return {"chat": chat}

@app.get("/chat/{chat_id}/messages")
async def get_messages(chat_id: UUID, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    query = select(Message).join(Chat).where(Message.chat_id == chat_id, Chat.user_id == current_user.id)
    result = await session.execute(query)
    messages = result.scalars().all()

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Messages not found",
        )

    return {"messages": messages}

@app.get("/chat/{chat_id}/documents")
async def fetch_documents(chat_id: UUID, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    _ = await check_chat_access(current_user, chat_id, session)
    query = select(Document).join(Chat).where(Document.chat_id == chat_id, Chat.user_id == current_user.id)
    result = await session.execute(query)
    documents = result.scalars().all()

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documents not found",
        )

    return {"documents": documents}

@app.post("/chat/{chat_id}/new_message")
async def create_new_message(chat_id: UUID, message_data: MessageCreate, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    _ = await check_chat_access(current_user, chat_id, session)
    new_msg = await create_message(session, message_data.content, chat_id)

    return {"message": "Message created successfully with id {}".format(new_msg.id)}

@app.post("/chat/{chat_id}/upload")
async def upload(chat_id: UUID, file: UploadFile = File(...), session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    _ = await check_chat_access(current_user, chat_id, session)

    file_path = await upload_to_s3(file)

    created_doc = await create_document(session, str(file.filename), file_path, chat_id)

    start_document_processing.delay(session, created_doc.id, file_path, chat_id)

    return {"message": "Document uploaded successfully with id {}".format(created_doc.id)}


    
