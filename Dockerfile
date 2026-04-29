# 1. 베이스 이미지 설정 (파이썬 3.12 - 승민 님 환경 최적화)
FROM python:3.12.3-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 필수 패키지 설치 (psycopg2 컴파일용 빌드 도구 포함)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. FastAPI 실행 (포트 8000)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]