# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "MegaZine API"
    # .env에서 가져오되, 없으면 기본값 사용
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:admin@db:5432/Megazine")

settings = Settings()