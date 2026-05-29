from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware 
from contextlib import asynccontextmanager

from app.db.session import engine, Base
from app.api.auth import router as auth_router
from app.models.user import User
from app.api.news import router as news_router
from app.api import news, magazine
from app.services.scheduler import start_scheduler

# DB 테이블 생성
Base.metadata.create_all(bind=engine)

# 서버 시작 시 스케줄러 가동
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    
app = FastAPI(title="MegaZine API", lifespan=lifespan)

# 프론트엔드 연동을 위한 CORS 설정 (이게 없으면 연결이 안 돼요!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # 테스트 환경이므로 일단 모두 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(news_router)
app.include_router(magazine.router)

@app.get("/")
def home():
    return {"message": "MegaZine Backend Running!"}