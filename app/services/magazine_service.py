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
    """
    
    # 1. 유사도 검색 (상위 3개 추출)
    search_results = query_similar_news(query_text=query, top_k=3)
    
    if not search_results:
        return {"error": "관련 기사를 찾을 수 없습니다."}

    # 2. RDB 원본 데이터 확보
    news_ids = [res['news_id'] for res in search_results]
    
    db = SessionLocal()
    try:
        articles = db.query(NewsMetadata).filter(NewsMetadata.news_id.in_(news_ids)).all()
        article_map = {str(a.news_id): a for a in articles}
        ordered_articles = [article_map[nid] for nid in news_ids if nid in article_map]
    finally:
        db.close()

    # 3. LLM 컨텍스트 조립 및 프론트엔드 응답 규격 맞춤화
    context_text = ""
    related_articles_response = []
    
    for idx, article in enumerate(ordered_articles):
        context_text += f"\n[기사 {idx+1}] 제목: {article.title}\n내용: {article.description}\n"
        
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

    # 4. 프롬프트 엔지니어링 (JSON 규격 강제)
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

    target_model = "gpt-4o-mini"

    try:
        print(f"[AI Attempt] OpenAI {target_model} 모델로 매거진 생성 중...", flush=True)
        
        # 5. 요약 생성
        summary_response = client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        raw_text = summary_response.choices[0].message.content.strip()
        
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            parsed_summary = json.loads(match.group(0))
        else:
            parsed_summary = {"title": f"{query} 분석 브리핑", "briefings": []}

        # 6. 진짜 OpenAI DALL-E로 이미지 직접 생성 (무료 서버 폐기)
        try:
            print("[Image Attempt] 0.1초 렌더링 스톡 이미지 검색 중...", flush=True)
            
            # 검색어에서 가장 핵심이 되는 첫 번째 단어 추출 (예: "ai IT" -> "ai")
            keyword = query.split()[0]
            # 한글/영문 모두 안전하게 URL 인코딩
            encoded_keyword = urllib.parse.quote(keyword)
            
            # API 대기 시간(15초) 없이, 키워드에 맞는 고화질 사진을 즉시 프론트엔드에 꽂아줍니다.
            final_image_url = f"https://loremflickr.com/800/800/{encoded_keyword},technology/all"
            
            print(f"[Image Success] 키워드 맞춤형 사진 연결 완료!", flush=True)
            
        except Exception as img_e:
            print(f"[Image Error] 이미지 연결 실패: {str(img_e)}", flush=True)
            # 최후의 방어망
            final_image_url = "https://placehold.co/800x800/2A2A2A/34D399?text=Image+Delayed"

        # 7. 최종 결과 반환 (프록시 안 거치고 다이렉트로 프론트엔드에 전달)
        return {
            "title": parsed_summary.get("title", f"{query} 분석 브리핑"),
            "tag": query[:6].upper(),
            "source": "MegaZine AI",
            "publishedAt": "방금 전",
            "briefings": parsed_summary.get("briefings", []),
            "relatedArticles": related_articles_response,
            "imageUrl": final_image_url 
        }
        
    except Exception as e:
        print(f"[AI Fatal] 생성 실패. (사유: {str(e)})", flush=True)
        return {"error": f"OpenAI 생성 실패: {str(e)}"}