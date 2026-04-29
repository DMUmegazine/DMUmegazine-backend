# app/models/user.py
from sqlalchemy import Column, String, DateTime, text, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base

class User(Base):
    __tablename__ = "users" # ✅ 소문자 통일
    user_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=text("now()"))

class UserInterest(Base):
    __tablename__ = "user_interests" # ✅ 소문자 통일
    interest_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    type = Column(String(20), nullable=False) # 'CATEGORY' or 'KEYWORD'
    content = Column(String(100), nullable=False)

class NewsMetadata(Base):
    __tablename__ = "news_metadata" # ✅ 소문자 통일 및 2.0 반영
    news_id = Column(UUID(as_uuid=True), primary_key=True)
    title = Column(Text, nullable=False)
    summary = Column(Text)
    description = Column(Text)
    originallink = Column(Text, unique=True, nullable=False)
    link = Column(Text, nullable=False)
    published_at = Column(DateTime)