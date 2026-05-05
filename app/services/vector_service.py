import os
from dotenv import load_dotenv
from google import genai
import chromadb
from app.db.session import SessionLocal
from app.models.user import NewsMetadata


def vector_embedding():
    load_dotenv()

    # 임베딩 안된 뉴스 조회
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

    # description 없는 뉴스 제외
    news_data = [
        {
            "id": str(news.news_id),   # ChromaDB용 문자열
            "uuid": news.news_id,      # RDB 업데이트용 UUID 원본
            "text": news.description,
        }
        for news in news_list
        if news.description
    ]

    # 임베딩
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    texts = [n["text"] for n in news_data]  # ✅ news_data 사용
    response = client.models.embed_content(model="gemini-embedding-001", contents=texts)
    embeddings = [e.values for e in response.embeddings]

    # ChromaDB 저장
    chroma_client = chromadb.PersistentClient(path="./chroma_data")
    collection = chroma_client.get_or_create_collection(name="news_embeddings")
    collection.add(
        ids=[n["id"] for n in news_data],  # ✅ news_data 사용
        embeddings=embeddings,
        metadatas=[{"title": n["text"][:50]} for n in news_data],
    )

    # news_id로 다시 조회해서 업데이트
    db = SessionLocal()
    try:
        ids = [n["uuid"] for n in news_data] # UUID 원본 그대로 사용
        db.query(NewsMetadata).filter(
            NewsMetadata.news_id.in_(ids)
        ).update({"is_embedded": True}, synchronize_session=False)
        db.commit()
    finally:
        db.close()

    # print(f"임베딩 완료: {collection.count()}건 저장됨", flush=True)

    # 로그 : 방금 추가한 건수
    print(f"임베딩 완료: {len(news_data)}건 저장됨", flush=True)