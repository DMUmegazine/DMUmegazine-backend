import os
from dotenv import load_dotenv
from google import genai
import chromadb

load_dotenv()

_genai_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

def get_chroma_client():
    """ChromaDB 클라이언트 생성"""
    client = chromadb.PersistentClient(path="./chroma_data") # 데이터 ./chroma_data 디렉토리에 파일로 저장. (이게 있어야 프로세스 종료 후에도 유지)
    return client

def create_news_collection():
    """뉴스 임베딩 저장용 컬렉션 생성"""
    client = get_chroma_client()

    collection = client.get_or_create_collection( # 컬렉션이 이미 존재하면 가져오고, 없으면 새로 생성
        name="news_embeddings", # 뉴스 임베딩만 저장하는 테?이블
        metadata={ # 컬렉션에 대한 정보, 그냥 진짜 정보임
            "description": "DMUmegazine 뉴스 임베딩 컬렉션",
            "embedding_model": "gemini-embedding-001",
            "embedding_dimension": "3072"
        }
    )

    print(f"컬렉션 이름: {collection.name}")
    print(f"현재 저장된 문서 수: {collection.count()}")
    print(f"메타데이터: {collection.metadata}")

    return collection

def query_similar_news(query_text: str, top_k: int = 5) -> list[dict]:
    """검색어와 유사한 뉴스 ID 리스트를 반환"""

    # 1. 검색어 -> 벡터 변환
    response = _genai_client.models.embed_content(
        model="gemini-embedding-001",
        contents=query_text
    )
    query_embedding = response.embeddings[0].values

    # 2. ChromaDB에서 유사도 검색
    collection = create_news_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    # 3. 결과 정리
    output = []
    for i in range(len(results["ids"][0])):
        output.append({
            "news_id": results["ids"][0][i],
            "distance": results["distances"][0][i],
            "metadata": results["metadatas"][0][i] if results["metadatas"] else None
        })

    print(f"\n[AI Search] 쿼리: {query_text}", flush=True)
    for res in output:
        print(f">> 검색된 ID: {res['news_id']} | 거리: {res['distance']:.4f}", flush=True)

    return output