# app/services/scheduler.py
import os
import urllib.request
import json
import urllib.parse
import ssl
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.models.user import NewsMetadata
from app.api.news import clean_news_text
from app.services.vector_service import vector_embedding

TOPICS = ["IT", "경제", "사회", "사고", "스포츠"]

def collect_and_embed_news_job():
    """
    [데이터 수집 자동화 워커]
    지정된 주제(TOPICS)의 최신 뉴스를 네이버 API에서 긁어와 중복을 제거하고 RDB에 저장합니다.
    저장이 끝나면 벡터 DB(ChromaDB) 임베딩 프로세스를 자동으로 트리거합니다.
    """
    print(f"\n[Scheduler] ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 뉴스 자동 수집 시작", flush=True)
    
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    context = ssl._create_unverified_context()
    
    db = SessionLocal()
    try:
        total_saved = 0
        # 💡 중복 데이터 방어 핵심 로직 1: 트랜잭션 도중 발생하는 교집합(예: IT이면서 경제인 뉴스) 방어망
        seen_links = set() 
        
        for topic in TOPICS:
            encText = urllib.parse.quote(f"{topic} 뉴스") 
            url = f"[https://openapi.naver.com/v1/search/news.json?query=](https://openapi.naver.com/v1/search/news.json?query=){encText}&display=10"
            
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            with urllib.request.urlopen(request, context=context) as response:
                items = json.loads(response.read().decode("utf-8")).get("items", [])
                
                for item in items:
                    link = item.get("originallink")
                    
                    # 장바구니 검사: 방금 전 다른 주제에서 담은 기사라면 가볍게 Pass
                    if link in seen_links:
                        continue
                        
                    # 중복 데이터 방어 핵심 로직 2: DB 단 검사. 이미 과거에 적재된 기사인지 2차 확인
                    exists = db.query(NewsMetadata).filter(NewsMetadata.originallink == link).first()
                    
                    if not exists:
                        seen_links.add(link) # 완전히 새로운 기사만 장바구니에 승인
                        
                        pub_date_str = item.get("pubDate", "")
                        try:
                            published_at = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
                        except:
                            published_at = None
                        
                        # 텍스트 내 HTML 태그 정제 후 ORM 객체 생성
                        new_news = NewsMetadata(
                            title=clean_news_text(item.get("title")),
                            description=clean_news_text(item.get("description")),
                            originallink=link,
                            link=item.get("link"),
                            published_at=published_at,
                        )
                        db.add(new_news)
                        total_saved += 1
                        
        db.commit() # 트랜잭션 일괄 커밋
        print(f"[Scheduler] ✅ {total_saved}건의 새 뉴스 RDB 저장 완료.", flush=True)
        
        # 신규 데이터가 적재되었을 때만 벡터 임베딩 파이프라인 호출
        if total_saved > 0:
            print("[Scheduler] 🚀 벡터 DB 임베딩 시작...", flush=True)
            vector_embedding() 
            print("[Scheduler] 🎯 벡터 DB 임베딩까지 모두 완료.", flush=True)
            
    except Exception as e:
        db.rollback()
        print(f"[Scheduler] ❌ 오류 발생: {str(e)}", flush=True)
    finally:
        db.close()


def start_scheduler():
    """
    [스케줄러 기동 함수]
    FastAPI 서버가 올라올 때 라이프사이클에 맞춰 백그라운드 스케줄러를 가동합니다.
    """
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    
    # 정기 수집: 독자 트래픽이 높은 매일 08:00, 20:00에 실행
    scheduler.add_job(collect_and_embed_news_job, 'cron', hour='8,20', minute=0)

    # 💡 킥스타터: 도커 서버 구동 시 비동기로 즉시 1회 가동하여 초기 데이터를 셋업
    scheduler.add_job(collect_and_embed_news_job, 'date')
    
    scheduler.start()
    print("[Scheduler] 🟢 뉴스 자동 수집 스케줄러가 시작되었습니다.", flush=True)