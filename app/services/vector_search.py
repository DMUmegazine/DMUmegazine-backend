# app/services/vector_search.py
import os
from dotenv import load_dotenv
from google import genai
import chromadb

load_dotenv()

_genai_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

def get_chroma_client():
    """
    [벡터 DB 클라이언트 연결]
    도커 컨테이너가 재시작되어도 데이터가 날아가지 않도록
    로컬 스토리지('./chroma_data')에 파일 형태로 영속성을 보장(Persistent)합니다.
    """
    client = chromadb.PersistentClient(path="./chroma_data") 
    return client

def create_news_collection():
    """
    [벡터 DB 컬렉션 관리]
    RDB의 '테이블' 개념에 해당하는 '컬렉션'을 생성하거나 불러옵니다.
    임베딩에 사용된 차원 수와 모델 정보를 메타데이터로 남겨 유지보수를 용이하게 합니다.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name="news_embeddings", 
        metadata={ 
            "description": "DMUmegazine 뉴스 임베딩 컬렉션",
            "embedding_model": "gemini-embedding-001",
            "embedding_dimension": "3072"
        }
    )
    return collection

def query_similar_news(query_text: str, top_k: int = 5) -> list[dict]:
    """
    [시멘틱 유사도 검색 엔진]
    사용자의 검색어(단순 텍스트)를 구글 AI로 임베딩(좌표 변환)한 뒤,
    ChromaDB의 유클리디안 거리/코사인 유사도 연산을 통해 가장 관련 깊은 상위 N개의 기사를 뽑아냅니다.
    """
    # 1. 텍스트 -> 벡터 좌표로 인코딩
    response = _genai_client.models.embed_content(
        model="gemini-embedding-001",
        contents=query_text
    )
    query_embedding = response.embeddings[0].values

    # 2. ChromaDB 공간 내에서 가장 가까운 이웃 탐색(KNN)
    collection = create_news_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    # 3. 데이터 반환 포맷팅 
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