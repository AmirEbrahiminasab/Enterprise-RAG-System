from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .auth.auth import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, verify_password, get_password_hash
from datetime import datetime, timedelta

from config.database import create_database, get_session, Document, User, UserCreate
from .documents.services import create_document
from .documents.preprocess import extract_text

@asynccontextmanager
async def lifespan(app):
    await create_database()
    yield

app = FastAPI(lifespan=lifespan)

## These two endpoints was implemented completely by AI
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


@app.post("/upload")
async def upload(file: UploadFile = File(...), session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    text = await extract_text(file)

    created_doc = await create_document(session, str(file.filename), text, current_user.id)

    return {"message": "File uploaded successfully"}


@app.get("/document")
async def get_all_documents(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    query = select(Document).where(Document.user_id == current_user.id)
    
    result = await session.execute(query)

    return {"documents": result.scalars().all()}




