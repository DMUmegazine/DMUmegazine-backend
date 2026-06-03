import os
import urllib.request
import json
import urllib.parse
import ssl
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.models.user import NewsMetadata
from app.api.news import clean_news_text             # 기존 정제 함수 그대로 사용
from app.services.vector_service import vector_embedding # 기존 임베딩 함수 그대로 사용

# 자동 수집할 5개 주제 설정
TOPICS = ["IT", "경제", "사회", "사고", "스포츠"]

def collect_and_embed_news_job():
    print(f"\n[Scheduler] ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 뉴스 자동 수집 시작", flush=True)
    
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    context = ssl._create_unverified_context()
    
    db = SessionLocal()
    try:
        total_saved = 0
        seen_links = set() # 💡 1. 이번 수집 턴에서 이미 본 기사 링크를 담아둘 장바구니
        
        for topic in TOPICS:
            # 검색어에 '뉴스'를 붙여 품질 향상 (원치 않으면 제거 가능)
            encText = urllib.parse.quote(f"{topic} 뉴스") 
            url = f"https://openapi.naver.com/v1/search/news.json?query={encText}&display=10"
            
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", client_id)
            request.add_header("X-Naver-Client-Secret", client_secret)
            
            with urllib.request.urlopen(request, context=context) as response:
                items = json.loads(response.read().decode("utf-8")).get("items", [])
                
                for item in items:
                    link = item.get("originallink")
                    
                    # 💡 2. 장바구니 검사: 다른 주제에서 방금 담은 기사라면 즉시 통과
                    if link in seen_links:
                        continue
                        
                    # 3. DB 검사: 완전히 결제(Commit)되어 있는 기사인지 확인
                    exists = db.query(NewsMetadata).filter(NewsMetadata.originallink == link).first()
                    
                    if not exists:
                        seen_links.add(link) # 💡 4. 완벽한 새 기사라면 장바구니에 기록
                        
                        pub_date_str = item.get("pubDate", "")
                        try:
                            published_at = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
                        except:
                            published_at = None
                        
                        new_news = NewsMetadata(
                            title=clean_news_text(item.get("title")),
                            description=clean_news_text(item.get("description")),
                            originallink=link,
                            link=item.get("link"),
                            published_at=published_at,
                        )
                        db.add(new_news)
                        total_saved += 1
                        
        db.commit()
        print(f"[Scheduler] ✅ {total_saved}건의 새 뉴스 RDB 저장 완료.", flush=True)
        
        # 💡 새 뉴스가 저장되었을 때만 기존 임베딩 함수 호출!
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
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    
    # 🚨 테스트용: 1분마다 실행
    # scheduler.add_job(collect_and_embed_news_job, 'cron', minute='*')
    # 실전용 오전 8시, 오후 8시 한번씩 실행 
    scheduler.add_job(collect_and_embed_news_job, 'cron', hour='8,20', minute=0)

    scheduler.add_job(collect_and_embed_news_job, 'date')
    
    scheduler.start()
    print("[Scheduler] 🟢 뉴스 자동 수집 스케줄러가 시작되었습니다.", flush=True)