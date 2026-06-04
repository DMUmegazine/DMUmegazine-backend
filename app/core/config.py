# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """
    [환경 설정 통합 관리]
    .env 파일의 민감한 정보 및 서버 전역 설정을 Pydantic 기반 클래스로 관리합니다.
    """
    PROJECT_NAME: str = "MegaZine API"
    # Docker 환경과 Local 환경에서의 기본 DATABASE_URL Fallback 지원
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:admin@db:5432/Megazine")

settings = Settings()