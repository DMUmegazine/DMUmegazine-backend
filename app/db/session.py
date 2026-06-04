# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from app.core.config import settings

"""
[데이터베이스 커넥션 풀 관리]
SQLAlchemy를 활용해 RDB(PostgreSQL)와의 연결 및 세션 생명 주기를 통제합니다.
"""

DATABASE_URL = settings.DATABASE_URL

# 💡 engine: 데이터베이스 통신의 핵심 객체. 컨넥션 풀링을 지원.
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    [Dependency Injection] 
    요청(Request) 단위마다 독립적인 DB 세션을 열고, 작업이 끝나면 안전하게 닫아주는 제너레이터입니다.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()