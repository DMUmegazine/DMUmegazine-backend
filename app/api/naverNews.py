import os
import sys
import ssl
import urllib.request
import urllib.parse
import json
import uuid
import psycopg2
from datetime import datetime

sys.path.append('../..')
from apiSecrets import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
from dbSecrets import POSTGRES_HOST, POSTGRES_USER, POSTGRES_PW

# DB 연결
def get_db_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=5432,
        database="postgres",
        user=POSTGRES_USER,
        password=POSTGRES_PW
    )

# 뉴스 저장 (url 중복이면 스킵)
def save_news(items):
    conn = get_db_connection()
    cur = conn.cursor()
    saved, skipped = 0, 0

    for item in items:
        try:
            # 파싱 예: "Wed, 22 Apr 2026 00:51:00 +0900"
            pub_date_str = item.get('pubDate', '')
            try:
                published_at = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
            except:
                published_at = None

            cur.execute("""
                INSERT INTO News_Metadata (news_id, title, summary, source, url, published_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING
            """, (
                str(uuid.uuid4()),
                item.get('title'),
                item.get('description'),
                'naver_news',
                item.get('link'),
                published_at
            ))

            if cur.rowcount > 0:
                saved += 1
            else:
                skipped += 1

        except Exception as e:
            print(f"저장 오류: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"저장: {saved}건, 중복 스킵: {skipped}건")

# 네이버 뉴스 검색
def search_news(query):
    client_id = NAVER_CLIENT_ID
    client_secret = NAVER_CLIENT_SECRET

    encText = urllib.parse.quote(query)
    url = "https://openapi.naver.com/v1/search/news.json?query=" + encText

    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)

    context = ssl._create_unverified_context()
    response = urllib.request.urlopen(request, context=context)

    if response.getcode() == 200:
        data = json.loads(response.read().decode('utf-8'))
        return data.get('items', [])
    else:
        print("Error Code:", response.getcode())
        return []

# 실행
if __name__ == "__main__":
    items = search_news("전쟁")
    save_news(items)