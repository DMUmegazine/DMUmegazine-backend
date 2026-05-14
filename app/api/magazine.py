from fastapi import APIRouter
from app.services.magazine_service import generate_ai_magazine

router = APIRouter(prefix="/magazine", tags=["magazine"])

@router.get("/generate")
def get_magazine(query: str):
    """
    1. 유사도 검색 (vector_search)
    2. 뉴스 요약 (Gemini LLM)
    3. 이미지 프롬프트 생성 (Gemini LLM)
    결과를 한 번에 반환하여 프론트의 레이아웃을 채웁니다.
    """
    result = generate_ai_magazine(query)
    return result