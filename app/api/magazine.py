# app/api/magazine.py
from fastapi import APIRouter, Response
from fastapi.responses import RedirectResponse
from app.services.magazine_service import generate_ai_magazine
import httpx
import urllib.parse

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
    [보안 우회 프록시 & 절대 안 깨지는 방어망]
    외부 AI 이미지 생성 서버(Pollinations)의 리소스를 프론트엔드로 안전하게 전달합니다.
    외부 서버가 죽었거나 지연될 경우, 500 에러 대신 '대체 이미지'로 브라우저를 우회시킵니다.
    """
    # 💡 혹시 모를 URL 이중 인코딩 꼬임 방지
    decoded_url = urllib.parse.unquote(url)
    if not decoded_url.startswith("http"):
        decoded_url = urllib.parse.unquote(decoded_url)

    # 💡 외부 서버의 봇 차단을 뚫기 위한 사람인 척(?) 하는 헤더 위장
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/*"
    }
    
    try:
        # verify=False: 간혹 발생하는 외부 서버의 SSL 인증서 만료 에러 무시
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, verify=False, headers=headers) as client:
            response = await client.get(decoded_url)
            
            # AI 서버가 정상적으로 그림을 그려서 줬다면 그대로 반환!
            if response.status_code == 200:
                return Response(content=response.content, media_type="image/jpeg")
            else:
                print(f"[Proxy Warning] AI 이미지 서버 튕김 (상태 코드: {response.status_code}) -> 대체 이미지로 방어합니다.", flush=True)
                
    except Exception as e:
        # 타임아웃 등 통신 에러가 나도 절대 서버를 멈추지 않고 잡아냅니다.
        print(f"[Proxy Exception] 통신 에러 발생: {str(e)} -> 대체 이미지로 방어합니다.", flush=True)

    # 💡 [핵심 방어] 에러 발생 시 브라우저에 500 에러를 던지지 않고, 
    # 매거진 테마에 맞는 멋진 검은색 플레이스홀더 이미지로 302 리다이렉트(이동) 시킵니다!
    fallback_url = "https://placehold.co/800x800/2A2A2A/34D399?text=AI+Image+Delayed"
    return RedirectResponse(url=fallback_url)