# init_backend.py
import os

"""
[Backend Initialization Script]
백엔드 프로젝트의 초기 폴더 구조와 필수 파일들을 자동으로 생성하는 스크립트입니다.
"""

# 생성할 디렉토리 구조 정의
folders = [
    "app/api",       # 라우터 엔드포인트
    "app/core",      # 설정 및 공통 모듈
    "app/db",        # 데이터베이스 연결 및 세션 관리
    "app/models",    # SQLAlchemy ORM 모델
    "app/schemas"    # Pydantic 데이터 검증 스키마
]

# 생성할 빈 파일 목록 정의
files = [
    ".env",
    "app/main.py",
    "app/api/endpoints.py",
    "app/db/session.py",
    "app/db/cache.py",  # [MAG-06] 캐싱 로직용
    "app/models/user.py",
    "app/schemas/magazine.py",
    "requirements.txt",
    "Dockerfile"
]

# 1. 폴더 생성 (이미 존재하면 무시)
for f in folders: 
    os.makedirs(f, exist_ok=True)

# 2. 빈 파일 생성 (이미 존재하면 덮어쓰지 않음)
for f in files:
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as file: 
            file.write("")

print("✅ Backend Repository Structure Ready!")