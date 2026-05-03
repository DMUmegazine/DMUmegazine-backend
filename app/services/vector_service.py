import os
from dotenv import load_dotenv
from google import genai
import chromadb

def vector_embedding():
    load_dotenv()

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    chroma_client = chromadb.PersistentClient(path="./chroma_data")
    collection = chroma_client.get_or_create_collection(name="news_embeddings")

    # 테스트용 뉴스 데이터
    test_news = [
        {"id": "news_1", "text": "엔비디아 AI 반도체 매출이 전년 대비 200% 증가했다", "category": "경제"},
        {"id": "news_2", "text": "한국은행이 기준금리를 3.5%로 동결하기로 결정했다", "category": "금융"},
        {"id": "news_3", "text": "현대자동차 전기차 판매량이 월 1만대를 돌파했다", "category": "산업"},
        {"id": "news_4", "text": "삼성전자가 차세대 반도체 공정에 5조원을 투자한다", "category": "경제"},
        {"id": "news_5", "text": "미국 연준이 금리 인하 가능성을 시사했다", "category": "금융"},
    ]

    # 텍스트 → 벡터 변환
    texts = [news["text"] for news in test_news]
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=texts
    )
    embeddings = [e.values for e in response.embeddings]

    # ChromaDB에 삽입
    collection.add(
        ids=[news["id"] for news in test_news],
        embeddings=embeddings,
        metadatas=[{"category": news["category"]} for news in test_news],
    )

    print(f"AI 스크립트 실행 완료: {collection.count()}건 저장됨", flush=True)