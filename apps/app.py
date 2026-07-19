from fastapi import FastAPI, File, UploadFile, HttpException, Depends
from contextlib import asynccontextmanager
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import create_database, get_session
from .documents.services import create_document

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
    created_doc = await create_document(session, file.filename, file.file)

    return {"message": "File uploaded successfully"}

@app.get("/documents")
async def get_documents(user_id: str, session: AsyncSession = Depends(get_session)):
    documents = await get_documents(session, UUID(user_id))

    return {"documents": documents}

