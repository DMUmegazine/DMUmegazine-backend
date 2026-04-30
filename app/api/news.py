from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import NewsMetadata
import urllib.request
import json
import uuid
import urllib.parse
import re

router = APIRouter(prefix="/news", tags=["news"])

@router.post("/collect")
def collect_naver_news(query: str, db: Session = Depends(get_db)):
    # API 키 설정[cite: 13]
    client_id = "UG53jYEc_qYIa4UbAPwX"
    client_secret = "32MjYwPr4B"
    
    encText = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encText}&display=10"
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    
    try:
        with urllib.request.urlopen(request) as response:
            items = json.loads(response.read().decode("utf-8")).get("items", [])
            saved_count = 0
            
            for item in items:
                # 1. 중복 체크를 먼저 해서 불필요한 객체 생성을 막습니다
                link = item.get('originallink')
                exists = db.query(NewsMetadata).filter(NewsMetadata.originallink == link).first()
                
                if not exists:
                    # 2. 정제 함수를 적용하여 깨끗한 텍스트를 만듭니다
                    cleaned_title = clean_news_text(item.get('title'))
                    cleaned_desc = clean_news_text(item.get('description'))
                    
                    new_news = NewsMetadata(
                        news_id=str(uuid.uuid4()),
                        title=cleaned_title, # 정제된 제목
                        description=cleaned_desc, # 정제된 내용
                        originallink=link,
                        link=item.get('link')
                    )
                    db.add(new_news)
                    saved_count += 1
            
            db.commit()
            return {"status": "success", "query": query, "new_saved": saved_count}
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

def clean_news_text(text: str) -> str:
    if not text:
        return ""
    # 1. HTML 태그 제거 (<b>, </b> 등)
    clean = re.sub(r'<[^>]*>', '', text)
    # 2. HTML 엔티티 변환
    clean = re.sub(r'&quot;', '"', clean)
    clean = re.sub(r'&amp;', '&', clean)
    clean = re.sub(r'&lt;', '<', clean)
    clean = re.sub(r'&gt;', '>', clean)
    clean = re.sub(r'&#39;', "'", clean)
    clean = re.sub(r'&middot;', '·', clean)
    # 3. 양쪽 공백 제거
    return clean.strip()