import os
from google import genai
from app.services.vector_search import query_similar_news
from app.db.session import SessionLocal
from app.models.user import NewsMetadata

_genai_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

def generate_ai_magazine(query: str):
    # 1. 유사도 검색 (상위 3개 추출 - UI 디자인에 맞춤)
    search_results = query_similar_news(query_text=query, top_k=3)
    
    if not search_results:
        return {"error": "관련 기사를 찾을 수 없습니다."}

    # 2. PostgreSQL DB에서 실제 기사 데이터 가져오기
    news_ids = [res['news_id'] for res in search_results]
    
    db = SessionLocal()
    try:
        # DB에서 ID가 일치하는 기사들 조회
        articles = db.query(NewsMetadata).filter(NewsMetadata.news_id.in_(news_ids)).all()
        
        # 벡터 검색 순서(유사도 높은 순)를 유지하기 위해 매핑
        article_map = {str(a.news_id): a for a in articles}
        ordered_articles = [article_map[nid] for nid in news_ids if nid in article_map]
    finally:
        db.close()

    # 3. LLM에게 전달할 컨텍스트 조립 및 프론트엔드 반환용 리스트 생성
    context_text = ""
    related_articles_response = []
    
    for idx, article in enumerate(ordered_articles):
        # AI 요약용 컨텍스트
        context_text += f"\n[기사 {idx+1}] 제목: {article.title}\n내용: {article.description}\n"
        
        # 오른쪽 리스트용 데이터 (프론트엔드에서 바로 쓸 수 있게 포맷팅)
        related_articles_response.append({
            "id": str(article.news_id),
            "title": article.title,
            "description": article.description[:100] + "..." if article.description else "", # 너무 길면 자름
            "link": article.link,
            "published_at": article.published_at.strftime("%Y-%m-%d %H:%M") if article.published_at else "최근"
        })

    # 4. 프롬프트 엔지니어링 (왼쪽 영역 제어)
    prompt = f"""
    당신은 IT/경제 전문 매거진의 수석 편집장입니다. 
    아래 제공된 [기사 데이터]를 바탕으로 '{query}'에 대한 브리핑을 작성하세요.

    [기사 데이터]: 
    {context_text}

    [작성 규칙 - 반드시 지킬 것]:
    1. 맨 첫 줄에는 독자의 시선을 끄는 매력적인 브리핑 제목을 작성하세요.
    2. 아래 3개의 소제목을 **정확히 동일하게** 사용하세요.
    3. 각 소제목 아래의 내용은 글머리 기호('-')를 사용하여 **최대 2줄 이내**로 아주 간결하고 핵심만 작성하세요.

    [출력 형식]:
    (매력적인 제목)

    ⚡ 무슨 일이 발생했나?
    - (내용 1~2줄)

    ⭐ 왜 중요한가?
    - (내용 1~2줄)

    📈 앞으로 어떤 영향이 있을까?
    - (내용 1~2줄)
    """

    target_model = "gemini-2.5-flash"

    try:
        print(f"[AI Attempt] 매거진 생성 중... (검색된 기사: {len(ordered_articles)}건)", flush=True)
        
        # 왼쪽 영역: 요약 생성
        summary_response = _genai_client.models.generate_content(
            model=target_model,
            contents=prompt
        )

        # 가운데 영역: 이미지 생성용 프롬프트 (단 1줄로 강제하여 로딩 시간 최적화)
        image_prompt_req = f"Create ONLY ONE concise, English image generation prompt to illustrate this news topic: '{query}'. No explanations, no markdown, just the raw prompt string."
        image_res = _genai_client.models.generate_content(
            model=target_model,
            contents=image_prompt_req
        )

        print("[AI Success] 매거진 생성 완료!", flush=True)
        
        # 5. 프론트엔드가 요구하는 완벽한 JSON 구조로 반환
        return {
            "summary": {
                "content": summary_response.text,        # 왼쪽 AI 브리핑 영역
                "image_prompt": image_res.text.strip()   # 가운데 이미지 영역
            },
            "related_articles": related_articles_response # 오른쪽 관련 뉴스 리스트
        }
        
    except Exception as e:
        print(f"[AI Fatal] 생성 실패. (사유: {str(e)})", flush=True)
        return {"error": f"AI 생성을 실패했습니다: {str(e)}"}