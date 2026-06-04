# app/services/vector_service.py
import os
from dotenv import load_dotenv
from google import genai
import chromadb
from app.db.session import SessionLocal
from app.models.user import NewsMetadata


def vector_embedding():
    """
    [데이터 동기화 (RDB -> Vector DB) 파이프라인]
    PostgreSQL에 새로 적재되었지만 아직 AI 뇌(ChromaDB)로 들어가지 않은 
    기사들(is_embedded=False)만 쏙쏙 뽑아서 일괄 임베딩 처리하는 함수입니다.
    """
    load_dotenv()

    # 1. 미처리 기사 탐색
    db = SessionLocal()
    try:
        news_list = (
            db.query(NewsMetadata).filter(NewsMetadata.is_embedded == False).all()
        )
    finally:
        db.close()

    if not news_list:
        print("임베딩할 새 뉴스 없음", flush=True)
        return

    # 본문이 없는 불량 기사는 제외하고 매핑
    news_data = [
        {
            "id": str(news.news_id),   # ChromaDB 매핑용 (String)
            "uuid": news.news_id,      # PostgreSQL 상태 변경용 (UUID Object)
            "text": news.description,
        }
        for news in news_list
        if news.description
    ]

    # 2. 텍스트 일괄 임베딩 (Google Gemini)
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    texts = [n["text"] for n in news_data] 
    response = client.models.embed_content(model="gemini-embedding-001", contents=texts)
    embeddings = [e.values for e in response.embeddings]

    # 3. ChromaDB에 벡터 데이터 Add
    chroma_client = chromadb.PersistentClient(path="./chroma_data")
    collection = chroma_client.get_or_create_collection(name="news_embeddings")
    collection.add(
        ids=[n["id"] for n in news_data],  
        embeddings=embeddings,
        metadatas=[{"title": n["text"][:50]} for n in news_data], # 확인을 위한 메타데이터 샘플 추가
    )

    # 4. RDB 상태값 업데이트 로직
    # 임베딩이 성공적으로 끝난 기사들에 대해 is_embedded 플래그를 True로 덮어씌웁니다.
    db = SessionLocal()
    try:
        ids = [n["uuid"] for n in news_data] 
        db.query(NewsMetadata).filter(
            NewsMetadata.news_id.in_(ids)
        ).update({"is_embedded": True}, synchronize_session=False)
        db.commit()
    finally:
        db.close()

    print(f"임베딩 완료: {len(news_data)}건 저장됨", flush=True)