from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import NewsMetadata
import urllib.request
import json
import uuid
import urllib.parse

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
                # 우리 DB 모델(news_metadata 테이블)에 맞게 저장[cite: 12, 17]
                new_news = NewsMetadata(
                    news_id=str(uuid.uuid4()),
                    title=item['title'],
                    description=item['description'],
                    originallink=item['originallink'],
                    link=item['link']
                )
                
                # 중복 체크[cite: 12, 13]
                exists = db.query(NewsMetadata).filter(NewsMetadata.originallink == item['originallink']).first()
                if not exists:
                    db.add(new_news)
                    saved_count += 1
            
            db.commit()
            return {"status": "success", "query": query, "new_saved": saved_count}
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))