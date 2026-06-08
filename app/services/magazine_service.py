import os
import json
import urllib.parse
import re
import concurrent.futures
from openai import OpenAI
from app.services.vector_search import query_similar_news
from app.db.session import SessionLocal
from app.models.user import NewsMetadata

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def generate_ai_magazine(query: str):
    
    # 1. [Query Transformation] 키워드 동기화
    print(f"[Query Transform] 원본 검색어 분석 중: {query}", flush=True)
    keyword_prompt = f"""
    당신은 검색어 최적화 AI입니다. 
    사용자의 질문에서 '어떻게', '미치는 영향', '알려줘' 등은 버리고 핵심 '명사 키워드'만 추출하세요.
    1) search_keyword: 벡터 DB 검색용 한국어 명사
    2) image_keyword: 이미지 생성용 영문 번역 키워드
    질문: {query}
    [출력 JSON 예시]:
    {{"search_keyword": "AI 주식 경제 IT", "image_keyword": "AI stock economy IT"}}
    """
    
    try:
        transform_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": keyword_prompt}],
            temperature=0.0
        )
        match = re.search(r'\{.*\}', transform_response.choices[0].message.content.strip(), re.DOTALL)
        keywords_data = json.loads(match.group(0)) if match else {"search_keyword": query, "image_keyword": "technology"}
    except:
        keywords_data = {"search_keyword": query, "image_keyword": "technology"}
        
    smart_query = keywords_data.get("search_keyword", query)
    img_keyword = keywords_data.get("image_keyword", "technology")
    print(f"[Query Transform] 🎯 DB검색: {smart_query} / 🎨 이미지: {img_keyword}", flush=True)

    # 2. 유사도 검색 및 RDB 데이터 확보
    search_results = query_similar_news(query_text=smart_query, top_k=3)
    if not search_results:
        return {"error": "관련 기사를 찾을 수 없습니다."}

    db = SessionLocal()
    try:
        articles = db.query(NewsMetadata).filter(NewsMetadata.news_id.in_([res['news_id'] for res in search_results])).all()
        article_map = {str(a.news_id): a for a in articles}
        ordered_articles = [article_map[res['news_id']] for res in search_results if res['news_id'] in article_map]
    finally:
        db.close()

    context_text = ""
    related_articles_response = []
    for idx, article in enumerate(ordered_articles):
        context_text += f"\n[기사 {idx+1}] {article.title}\n{article.description}\n"
        domain = article.link.split('/')[2].replace("n.news.", "") if article.link else "뉴스"
        related_articles_response.append({
            "id": str(article.news_id),
            "tag": query.split()[-1].upper() if len(query.split()) > 0 else "NEWS",
            "title": article.title,
            "summary": article.description[:100] + "..." if article.description else "",
            "source": domain,
            "publishedAt": article.published_at.strftime("%Y-%m-%d %H:%M") if article.published_at else "최근",
            "url": article.link
        })

    # 💡 [병렬 작업 1] 텍스트 생성 함수 (내용을 더 깊고 풍부하게 요구)
    def fetch_text_briefing():
        prompt = f"""
        당신은 수석 편집장입니다. [기사 데이터]의 팩트만을 근거로 '{query}'에 대한 브리핑을 작성하세요.
        각 답변(answer)은 단순 요약이 아닌, **전문적인 통찰이 담긴 3~4줄 이상의 깊이 있는 분석**으로 풍부하게 작성하세요.
        [기사 데이터]: {context_text}
        [출력 JSON 예시]:
        {{"title": "...", "briefings": [
            {{"icon": "⚡", "question": "무슨 일이 발생했나?", "answer": "(풍부한 3~4줄 팩트)"}},
            {{"icon": "⭐", "question": "왜 중요한가?", "answer": "(풍부한 3~4줄 팩트)"}},
            {{"icon": "📈", "question": "앞으로 어떤 영향이 있을까?", "answer": "(풍부한 3~4줄 팩트)"}}
        ]}}
        """
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.2)
        match = re.search(r'\{.*\}', res.choices[0].message.content.strip(), re.DOTALL)
        return json.loads(match.group(0)) if match else {"title": f"{smart_query} 브리핑", "briefings": []}

    # 💡 [병렬 작업 2] 이미지 생성 함수
    def fetch_image():
        image_prompt = f"Abstract minimal vector art of {img_keyword}"
        res = client.images.generate(model="gpt-image-1-mini", prompt=image_prompt, size="1024x1024", n=1, quality="low")
        img_data = res.data[0]
        if getattr(img_data, 'b64_json', None): return f"data:image/png;base64,{img_data.b64_json}"
        elif getattr(img_data, 'url', None): return f"http://localhost:8000/magazine/proxy-image?url={urllib.parse.quote(img_data.url)}"
        return "https://placehold.co/800x800/2A2A2A/34D399?text=Image+Delayed"

    # 💡 [하이라이트] 스레드를 사용하여 두 AI에게 동시에 일을 시킵니다! (속도 2배 향상)
    print(f"[AI & Image] 병렬 생성 시작...", flush=True)
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_text = executor.submit(fetch_text_briefing)
            future_img = executor.submit(fetch_image)
            
            parsed_summary = future_text.result()
            final_image_url = future_img.result()
    except Exception as e:
        print(f"[Parallel Error] {e}", flush=True)
        return {"error": "AI 병렬 생성 중 오류가 발생했습니다."}

    # 3. 최종 결과 반환
    return {
        "title": parsed_summary.get("title", f"{smart_query} 브리핑"),
        "tag": query.split()[-1].upper() if len(query.split()) > 0 else "NEWS",
        "source": "MegaZine AI",
        "publishedAt": "방금 전",
        "briefings": parsed_summary.get("briefings", []),
        "relatedArticles": related_articles_response,
        "imageUrl": final_image_url 
    }