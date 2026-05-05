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


# /app 경로가 없을 경우 Python 모듈 탐색 경로에 추가
if "/app" not in sys.path:
    sys.path.append("/app")

# .env에서 네이버 API 인증 정보 로드
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

router = APIRouter(prefix="/news", tags=["news"])


# ----- 텍스트 정제 -----
def clean_news_text(text: str) -> str:
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

    client_id = NAVER_CLIENT_ID
    client_secret = NAVER_CLIENT_SECRET

    # 한글 키워드 URL 인코딩
    encText = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encText}"

    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)

    # SSL 인증서 검증 우회 (일부 환경에서 인증서 오류 방지)
    context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(request, context=context) as response:
            items = json.loads(response.read().decode("utf-8")).get("items", [])
            saved_count = 0

            for item in items:
                # originallink 기준으로 이미 저장된 뉴스인지 확인
                link = item.get("originallink")
                exists = (
                    db.query(NewsMetadata)
                    .filter(NewsMetadata.originallink == link)
                    .first()
                )

                if not exists:
                    # datetime 객체로 날짜 변환
                    pub_date_str = item.get("pubDate", "")
                    try:
                        published_at = datetime.strptime(
                            pub_date_str, "%a, %d %b %Y %H:%M:%S %z"
                        )
                    except:
                        published_at = None  # 날짜 파싱 실패 시 None으로 저장

                    # 텍스트 정제 후 DB 객체 생성 (news_id, is_embedded는 DB 자동 생성)
                    new_news = NewsMetadata(
                        title=clean_news_text(item.get("title")),
                        description=clean_news_text(item.get("description")),
                        originallink=link,
                        link=item.get("link"),
                        published_at=published_at,
                    )
                    db.add(new_news)
                    saved_count += 1

            # 모든 뉴스 저장 완료 후 한 번에 커밋
            db.commit()
            
            background_tasks.add_task(vector_embedding) #데이터 임베딩
            
            return {"status": "success", "query": query, "new_saved": saved_count}

    except Exception as e:
        # 오류 발생 시 롤백
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
def search_ai_news(query: str):

    # 사용자가 입력한 query를 그대로 vector 로직에 전달
    results = query_similar_news(query_text=query)
    return results