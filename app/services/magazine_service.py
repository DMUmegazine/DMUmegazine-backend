# app/services/magazine_service.py
import os
import json
import urllib.parse
import re
import time
from openai import OpenAI
from app.services.vector_search import query_similar_news
from app.db.session import SessionLocal
from app.models.user import NewsMetadata

# OpenAI API 클라이언트 초기화
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def generate_ai_magazine(query: str):
    """
    [AI 매거진 코어 엔진]
    사용자의 검색어를 바탕으로 RAG(검색 증강 생성) 파이프라인을 가동하여 
    최종 매거진(JSON) 결과물을 프론트엔드로 반환합니다.
    
    Data Flow: 검색어 입력 -> 유사 기사 검색 -> DB에서 원문 확보 -> LLM 프롬프트 조립 -> JSON 파싱 -> 이미지 URL 조립
    """
    
    # 1. Vector Search (RAG의 Retriever 역할)
    # ChromaDB를 찔러 검색어와 가장 문맥이 유사한 상위 3개의 기사 ID를 가져옵니다.
    search_results = query_similar_news(query_text=query, top_k=3)
    
    if not search_results:
        return {"error": "관련 기사를 찾을 수 없습니다."}

    # 2. RDB 원본 데이터 확보
    # 벡터 DB에서 얻은 UUID로 PostgreSQL을 조회하여 실제 기사 텍스트와 메타데이터를 가져옵니다.
    news_ids = [res['news_id'] for res in search_results]
    
    db = SessionLocal()
    try:
        articles = db.query(NewsMetadata).filter(NewsMetadata.news_id.in_(news_ids)).all()
        # 검색된 유사도 순서를 유지하기 위한 매핑 로직
        article_map = {str(a.news_id): a for a in articles}
        ordered_articles = [article_map[nid] for nid in news_ids if nid in article_map]
    finally:
        db.close()

    # 3. LLM 컨텍스트 조립 및 프론트엔드 응답 규격(관련 기사 리스트) 맞춤화
    context_text = ""
    related_articles_response = []
    
    for idx, article in enumerate(ordered_articles):
        # AI에게 먹일 먹이(컨텍스트) 조립
        context_text += f"\n[기사 {idx+1}] 제목: {article.title}\n내용: {article.description}\n"
        
        # 언론사 이름 추출 (도메인 파싱)
        domain = "뉴스"
        if article.link:
            try:
                domain = article.link.split('/')[2].replace("n.news.", "")
            except:
                pass

        related_articles_response.append({
            "id": str(article.news_id),
            "tag": query[:6].upper(),
            "title": article.title,
            "summary": article.description[:100] + "..." if article.description else "",
            "source": domain,
            "publishedAt": article.published_at.strftime("%Y-%m-%d %H:%M") if article.published_at else "최근",
            "url": article.link
        })

    # 4. 프롬프트 엔지니어링 (시스템 프롬프트 + 제약 조건)
    # LLM이 반드시 정해진 JSON 포맷으로만 대답하도록 강력하게 통제합니다.
    prompt = f"""
    당신은 IT/경제 전문 매거진의 수석 편집장입니다. 
    아래 제공된 [기사 데이터]를 바탕으로 '{query}'에 대한 브리핑을 작성하세요.

    [기사 데이터]: 
    {context_text}

    [작성 규칙 - 반드시 지킬 것]:
    1. 반드시 아래 제공된 JSON 형식으로만 출력하세요. 마크다운(```json 등)은 절대 사용하지 말고 순수 JSON 문자열만 반환하세요.
    2. title: 독자의 시선을 끄는 매력적인 브리핑 제목
    3. briefings: 다음 3개의 항목을 정확히 포함하는 배열
       - icon: "⚡", question: "무슨 일이 발생했나?", answer: (1~2줄 요약)
       - icon: "⭐", question: "왜 중요한가?", answer: (1~2줄 요약)
       - icon: "📈", question: "앞으로 어떤 영향이 있을까?", answer: (1~2줄 요약)

    [출력 JSON 형태 예시]:
    {{
        "title": "...",
        "briefings": [
            {{"icon": "⚡", "question": "무슨 일이 발생했나?", "answer": "..."}},
            {{"icon": "⭐", "question": "왜 중요한가?", "answer": "..."}},
            {{"icon": "📈", "question": "앞으로 어떤 영향이 있을까?", "answer": "..."}}
        ]
    }}
    """

    target_model = "gpt-4o-mini" # 가성비와 속도를 고려한 모델 채택

    try:
        print(f"[AI Attempt] OpenAI {target_model} 모델로 매거진 생성 중...", flush=True)
        
        # 5. 매거진 브리핑 생성 (OpenAI API Call)
        summary_response = client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        raw_text = summary_response.choices[0].message.content.strip()
        
        # LLM이 마크다운 찌꺼기를 뱉을 것에 대비한 정규식 파싱 방어 로직
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            parsed_summary = json.loads(match.group(0))
        else:
            parsed_summary = {"title": f"{query} 분석 브리핑", "briefings": []}

        # 6. 맥락 기반 이미지 프롬프트 생성 (OpenAI API Call)
        image_prompt_req = f"Create a very simple, 5-word English image prompt for: '{query}'. Focus on objects, no people, no complex shadows."
        image_res = client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": image_prompt_req}],
            temperature=0.7
        )
        
        # 7. 이미지 서버 URL 조립 및 보안 프록시 우회
        # 생성된 텍스트에서 특수문자를 날리고 인코딩하여 Pollinations API URL을 만듭니다.
        clean_prompt = image_res.choices[0].message.content.replace('\n', ' ').replace('\r', '').replace('"', '').replace("'", "").strip()
        clean_prompt = re.sub(r'[^a-zA-Z0-9\s,]', '', clean_prompt)
        encoded_prompt = urllib.parse.quote(clean_prompt)
        
        timestamp = int(time.time())
        raw_image_url = f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){encoded_prompt}?width=800&height=800&nologo=true&t={timestamp}"

        # 프론트엔드의 CORS/HTTPS 혼합 콘텐츠 에러를 막기 위해 우리 백엔드의 프록시 주소로 감쌉니다.
        proxy_url = f"http://localhost:8000/magazine/proxy-image?url={urllib.parse.quote(raw_image_url)}"

        print(f"[AI Success] 프록시 적용 URL: {proxy_url}", flush=True)
        
        # 8. 최종 결과 반환
        return {
            "title": parsed_summary.get("title", f"{query} 분석 브리핑"),
            "tag": query[:6].upper(),
            "source": "MegaZine AI",
            "publishedAt": "방금 전",
            "briefings": parsed_summary.get("briefings", []),
            "relatedArticles": related_articles_response,
            "imageUrl": proxy_url 
        }
        
    except Exception as e:
        print(f"[AI Fatal] 생성 실패. (사유: {str(e)})", flush=True)
        return {"error": f"OpenAI 생성 실패: {str(e)}"}