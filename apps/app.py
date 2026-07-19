from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
from contextlib import asynccontextmanager
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.database import create_database, get_session, Document
from .documents.services import create_document
from .documents.preprocess import extract_text

@asynccontextmanager
async def lifespan(app):
    await create_database()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/upload")
async def upload(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    text = await extract_text(file)

    created_doc = await create_document(session, str(file.filename), text)

    return {"message": "File uploaded successfully"}

@app.get("/documents")
async def get_documents(user_id: str, session: AsyncSession = Depends(get_session)):
    try:
        documents = await get_documents(session, UUID(user_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    return {"documents": documents}

@app.get("/document/all")
async def get_all_documents(session: AsyncSession = Depends(get_session)):
    query = select(Document)
    
    result = await session.execute(query)

    return {"documents": result.scalars().all()}




