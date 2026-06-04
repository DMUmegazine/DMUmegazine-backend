# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User, UserInterest
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["auth"])
# 비밀번호 단방향 암호화를 위한 bcrypt 컨텍스트 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: str

@router.post("/signup")
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    [회원가입 로직]
    이메일 중복을 체크하고, 수신된 평문 비밀번호를 bcrypt 알고리즘으로 해싱하여 DB에 안전하게 적재합니다.
    """
    user = db.query(User).filter(User.email == user_data.email).first()
    if user:
        raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")
    
    new_user = User(
        email=user_data.email,
        password=pwd_context.hash(user_data.password), # 💡 해싱 처리 핵심
        nickname=user_data.nickname
    )
    db.add(new_user)
    db.commit()
    return {"message": "회원가입 성공"}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/login")
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    [로그인 로직]
    유저 정보를 검증하고, 유저가 기존에 저장했던 관심사 태그를 취합하여 프론트엔드로 반환합니다.
    """
    user = db.query(User).filter(User.email == login_data.email).first()
    
    # 💡 pwd_context.verify: 입력된 평문과 DB의 해시값을 안전하게 비교
    if not user or not pwd_context.verify(login_data.password, user.password):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 틀렸습니다.")
    
    # 조인 대신 역참조 형태로 유저의 커스텀 태그 리스트 추출
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
    """
    [유저 커스텀 태그 업데이트]
    사용자가 선택한 카테고리 태그 갱신.
    데이터 정합성을 위해 기존 태그를 전체 삭제(Delete)한 뒤 새로운 태그를 삽입(Insert)하는 방식을 취합니다.
    """
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 기존 매핑 데이터 초기화
    db.query(UserInterest).filter(UserInterest.user_id == user.user_id).delete()
    
    # 프론트엔드에서 넘어온 신규 태그 배열 Bulk Insert
    for tag in data.tags:
        new_interest = UserInterest(
            user_id=user.user_id,
            type="CATEGORY", 
            content=tag
        )
        db.add(new_interest)
    
    db.commit()
    return {"message": "Tags updated successfully"}