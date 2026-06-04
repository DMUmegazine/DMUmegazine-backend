# app/api/news.py
import os
import sys
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import NewsMetadata
import urllib.request
import json
import urllib.parse
import re
import ssl
from datetime import datetime
from fastapi import BackgroundTasks
from app.services.vector_service import vector_embedding
from app.services.vector_search import query_similar_news

if "/app" not in sys.path:
    sys.path.append("/app")

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

router = APIRouter(prefix="/news", tags=["news"])


def clean_news_text(text: str) -> str:
    """
    [데이터 정제 로직]
    API 응답에 포함된 불필요한 HTML 태그 및 특수 인코딩 문자를 순수 텍스트로 치환합니다.
    (LLM 프롬프트 품질 향상 목적)
    """
    if not text:
        return ""
    text = re.sub(r"<[^>]*>", "", text)
    text = text.replace("&quot;", '"')
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&#39;", "'")
    text = text.replace("&middot;", "·")
    return text.strip()


@router.post("/collect")
def collect_naver_news(query: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    [ETL 파이프라인] 네이버 뉴스 API 수집 및 DB 적재
    검색어 기반으로 기사를 수집하고, 중복 필터링 후 RDB에 저장합니다.
    저장이 완료되면 비동기 워커를 통해 ChromaDB 벡터 임베딩을 트리거합니다.
    """
    client_id = NAVER_CLIENT_ID
    client_secret = NAVER_CLIENT_SECRET

    encText = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encText}"

    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)

    context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(request, context=context) as response:
            items = json.loads(response.read().decode("utf-8")).get("items", [])
            saved_count = 0

            for item in items:
                # 💡 무결성 검증: 동일한 원본 링크가 DB에 존재하는지 확인하여 중복 적재 방지
                link = item.get("originallink")
                exists = (
                    db.query(NewsMetadata)
                    .filter(NewsMetadata.originallink == link)
                    .first()
                )

                if not exists:
                    pub_date_str = item.get("pubDate", "")
                    try:
                        published_at = datetime.strptime(
                            pub_date_str, "%a, %d %b %Y %H:%M:%S %z"
                        )
                    except:
                        published_at = None

                    # 💡 스키마 매핑 및 트랜잭션 추가
                    new_news = NewsMetadata(
                        title=clean_news_text(item.get("title")),
                        description=clean_news_text(item.get("description")),
                        originallink=link,
                        link=item.get("link"),
                        published_at=published_at,
                    )
                    db.add(new_news)
                    saved_count += 1

            # N건의 뉴스 데이터를 DB에 일괄 커밋
            db.commit()
            
            # 💡 RDB 저장이 끝난 후 응답 속도 저하를 막기 위해 백그라운드에서 임베딩 작업 수행
            background_tasks.add_task(vector_embedding) 
            
            return {"status": "success", "query": query, "new_saved": saved_count}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
def search_ai_news(query: str):
    """
    [벡터 DB 검색] 
    사용자가 입력한 검색어(태그 조합 포함)를 벡터 DB 서비스로 패스스루 하여 유사도를 계산합니다.
    """
    results = query_similar_news(query_text=query)
    return results