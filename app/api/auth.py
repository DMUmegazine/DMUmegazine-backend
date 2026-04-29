from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User, UserInterest
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 요청 데이터 검증용 스키마
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: str

@router.post("/signup")
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    # 중복 체크
    user = db.query(User).filter(User.email == user_data.email).first()
    if user:
        raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
    
    # 저장 (비밀번호 해싱)
    new_user = User(
        email=user_data.email,
        password=pwd_context.hash(user_data.password),
        nickname=user_data.nickname
    )
    db.add(new_user)
    db.commit()
    return {"message": "회원가입 성공"}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/login")
def login(login_data: LoginRequest, db: Session = Depends(get_db)): # ◀ 여기 수정
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user or not pwd_context.verify(login_data.password, user.password):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 틀렸습니다.")
    
    user_tags = db.query(UserInterest).filter(UserInterest.user_id == user.user_id).all()
    tag_list = [t.content for t in user_tags] 
    
    return {
        "message": "로그인 성공",
        "user": {
            "nickname": user.nickname,
            "email": user.email,
            "tags": tag_list
        }
    }

class TagUpdateRequest(BaseModel):
    email: EmailStr
    tags: list[str]
    
@router.post("/update-tags")
def update_tags(data: TagUpdateRequest, db: Session = Depends(get_db)):
    # 1. 유저 찾기
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 2. 기존 관심사 삭제 (덮어쓰기 방식)
    db.query(UserInterest).filter(UserInterest.user_id == user.user_id).delete()
    
    # 3. 새로운 태그들 저장
    for tag in data.tags:
        new_interest = UserInterest(
            user_id=user.user_id,
            type="CATEGORY",  # 프론트에서 넘어온 성격에 따라 조정 가능
            content=tag
        )
        db.add(new_interest)
    
    db.commit()
    return {"message": "Tags updated successfully"}