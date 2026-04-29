from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: str
    
class UserOut(BaseModel):
    email: str
    nickname: str
    
    class Config:
        from_attributes = True