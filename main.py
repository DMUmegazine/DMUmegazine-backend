# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware 
from contextlib import asynccontextmanager

from app.db.session import engine, Base
from app.api.auth import router as auth_router
from app.models.user import User
from app.api.news import router as news_router
from app.api import news, magazine
from app.services.scheduler import start_scheduler

# [DB 초기화] 애플리케이션 시작 전 선언된 모든 ORM 모델을 RDB에 테이블로 생성
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    [Lifecycle Manager]
    FastAPI 서버가 구동될 때 백그라운드 스케줄러(뉴스 자동 수집)를 함께 시작합니다.
    """
    start_scheduler()
    yield
    
app = FastAPI(title="MegaZine API", lifespan=lifespan)

# [CORS 설정] 프론트엔드(React/Next.js)에서 API에 접근할 수 있도록 교차 출처 리소스 공유 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # 테스트용 오픈, 운영 시 도메인 지정 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [Router 등록] 각 도메인별 API 엔드포인트를 메인 앱에 연결
app.include_router(auth_router)
app.include_router(news_router)
app.include_router(magazine.router)

@app.get("/")
def home():
    """헬스 체크용 루트 엔드포인트"""
    return {"message": "MegaZine Backend Running!"}