# app/api/magazine.py
from fastapi import APIRouter
from app.services.magazine_service import generate_ai_magazine
import httpx
from fastapi import Response

router = APIRouter(prefix="/magazine", tags=["magazine"])

@router.get("/generate")
def get_magazine(query: str):
    """
    [AI 매거진 생성 파이프라인]
    1. vector_search: 사용자 query 기반 RAG 유사도 검색으로 컨텍스트 확보
    2. LLM 브리핑: 추출된 원본 뉴스를 융합하여 3단계 인사이트 브리핑 도출
    3. 실시간 비주얼: 기사 맥락에 맞는 영문 프롬프트를 추출해 AI 이미지 생성
    -> 완성된 매거진 JSON 규격을 프론트엔드로 반환
    """
    result = generate_ai_magazine(query)
    return result

@router.get("/proxy-image")
async def proxy_image(url: str):
    """
    [보안 우회 프록시]
    외부 AI 이미지 생성 서버(Pollinations)의 리소스를 프론트엔드에서 직접 렌더링할 때
    발생하는 CORS 및 브라우저 차단 이슈를 해결하기 위한 백엔드 경유 엔드포인트.
    """
    # AI 이미지 생성 지연(Timeout)을 고려하여 비동기 대기 시간을 30초로 상향
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        # 💡 외부 바이너리 데이터를 그대로 패스스루(Pass-through) 하여 브라우저에 서빙
        return Response(content=response.content, media_type="image/jpeg")