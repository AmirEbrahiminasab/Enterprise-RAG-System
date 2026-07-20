from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr 
    password: str

class ChatCreate(BaseModel):
    title: str
    
class MessageCreate(BaseModel):
    content: str