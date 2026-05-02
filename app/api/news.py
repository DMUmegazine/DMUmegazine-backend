import os
import sys
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import NewsMetadata
import urllib.request
import json
import uuid
import urllib.parse
import re
import ssl
from datetime import datetime

if "/app" not in sys.path:
    sys.path.append("/app")
    
try:
    from apiSecrets import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
except ImportError:
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "기본값")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "기본값")


router = APIRouter(prefix="/news", tags=["news"])

# ----- 텍스트 정제 함수 -----
def clean_news_text(text: str) -> str:
    if not text:
        return ""
    # HTML 태그 제거[cite: 8, 18]
    text = re.sub(r'<[^>]*>', '', text)
    # 특수 기호 복원 (naverNews 로직 반영)[cite: 8, 16, 18]
    text = text.replace("&quot;", '"')
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&#39;", "'")
    text = text.replace("&middot;", "·")
    return text.strip()

@router.post("/collect")
def collect_naver_news(query: str, db: Session = Depends(get_db)):
    # 1. 네이버 뉴스 검색 설정
    client_id = NAVER_CLIENT_ID
    client_secret = NAVER_CLIENT_SECRET
    
    encText = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encText}&display=1"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    
    # SSL 인증서 문제 방지 (naverNews 로직 반영)[cite: 8, 16]
    context = ssl._create_unverified_context()
    
    try:
        with urllib.request.urlopen(request, context=context) as response:
            items = json.loads(response.read().decode("utf-8")).get("items", [])
            saved_count = 0
            
            for item in items:
                # 2. 중복 체크 (originallink 기준)[cite: 8, 18, 19]
                link = item.get('originallink')
                exists = db.query(NewsMetadata).filter(NewsMetadata.originallink == link).first()
                
                if not exists:
                    # 3. 날짜 변환 로직 추가 (naverNews 로직 반영)[cite: 8, 16]
                    pub_date_str = item.get("pubDate", "")
                    try:
                        # 네이버 날짜 포맷: "Tue, 29 Apr 2026 14:30:00 +0900"[cite: 8, 16]
                        published_at = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
                    except:
                        published_at = None

                    # 4. 데이터 정제 및 객체 생성[cite: 18, 19]
                    new_news = NewsMetadata(
                        news_id=str(uuid.uuid4()),
                        title=clean_news_text(item.get('title')),
                        description=clean_news_text(item.get('description')),
                        originallink=link,
                        link=item.get('link'),
                        published_at=published_at # 추가된 날짜 데이터[cite: 8, 11]
                    )
                    db.add(new_news)
                    saved_count += 1
            
            db.commit()
            return {"status": "success", "query": query, "new_saved": saved_count}
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))