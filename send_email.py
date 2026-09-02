import os
import sys
import pandas as pd
import urllib.request
import json
import re
import datetime
from email.utils import parsedate_to_datetime
import google.generativeai as genai
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ==========================================
# 0. 🔍 깃허브 시크릿 연결 상태 스캐너 (디버깅용)
# ==========================================
print("--- 🔍 깃허브 시크릿 연결 상태 검사 ---")
keys_to_check = ["NCP_CLIENT_ID", "NCP_CLIENT_SECRET", "GEMINI_API_KEY", "GMAIL_ADDRESS", "GMAIL_PASSWORD"]
error_found = False

for k in keys_to_check:
    val = os.environ.get(k)
    if not val:
        print(f"❌ 실패: [{k}] 값이 텅 비어있습니다!")
        error_found = True
    else:
        print(f"✅ 성공: [{k}] 정상 연결됨 (길이: {len(val)}자)")

if error_found:
    print("-----------------------------------------")
    print("🚨 에러: 일부 시크릿 키를 찾지 못해 작업을 멈춥니다.")
    print("해결책: 깃허브 Settings -> Secrets에서 위 ❌ 표시된 키를 완전히 지우고 새 초록색 버튼으로 다시 만들어주세요. (이름 앞뒤에 띄어쓰기가 없어야 합니다!)")
    sys.exit(1)
else:
    print("🎉 모든 키가 완벽하게 연결되었습니다! 보고서 작성을 시작합니다.")
    print("-----------------------------------------\n")

# ==========================================
# 1. 환경 변수 및 API 세팅
# ==========================================
NCP_CLIENT_ID = os.environ.get("NCP_CLIENT_ID")
NCP_CLIENT_SECRET = os.environ.get("NCP_CLIENT_SECRET")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")

genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 2. 공통 도우미 함수
# ==========================================
def fetch_news_items(search_keyword, display_count=100):
    search_word = urllib.parse.quote(search_keyword)
    api_url = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={search_word}&display={display_count}&sort=date"
    request = urllib.request.Request(api_url)
    request.add_header("X-NCP-APIGW-API-KEY-ID", NCP_CLIENT_ID)
    request.add_header("X-NCP-APIGW-API-KEY", NCP_CLIENT_SECRET)

    try:
        response = urllib.request.urlopen(request)
        data = json.loads(response.read().decode('utf-8'))
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        time_limit = now_utc - datetime.timedelta(hours=24)

        recent_items = []
        for item in data['items']:
            pub_date = parsedate_to_datetime(item['pubDate'])
            if pub_date >= time_limit:
                recent_items.append(item)
        return recent_items
    except Exception:
        return []

def format_news_text(items, max_count=70):
    target_items = items[:max_count]
    news_text_list = []
    for idx, item in enumerate(target_items, start=1):
        clean_title = re.sub(r'<.*?>|&quot;', '', item['title'])
        clean_desc = re.sub(r'<.*?>|&quot;', '', item['description'])
        link = item.get('originallink') or item.get('link')
        news_text_list.append(f"[{idx}]\n- 제목: {clean_title}\n- 내용: {clean_desc}\n- 링크: {link}")
    return "\n\n".join(news_text_list), len(target_items)

def get_best_model():
    valid_models = [
        m.name for m in genai.list_models()
        if 'generateContent' in m.supported_generation_methods
        and 'flash' in m.name.lower()
        and not any(x in m.name.lower() for x in ['preview', 'exp', 'omni', 'vision', 'embedding'])
    ]
    return sorted(valid_models, reverse=True)[0] if valid_models else 'models/gemini-3.6-flash'

# ==========================================
# 3. 이메일 본문(HTML) 조립 시작
# ==========================================
today_str = (datetime.datetime.now() + datetime.timedelta(hours=9)).strftime("%Y년 %m월 %d일")

html_body = f"""
<html>
<head>
<style>
    body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; line-height: 1.6; color: #333; }}
    h1 {{ color: #1a252f; text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; }}
    h2 {{ color: #2c3e50; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
    h3 {{ color: #34495e; }}
    .kbo-table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; font-size: 14px; }}
    .kbo-table th, .kbo-table td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
    .kbo-table th {{ background-color: #f8f9fa; font-weight: bold; }}
    a {{ color: #2980b9; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<h1>📰 일간 종합 동향 보고서</h1>
<p style="text-align: center; color: #7f8c8d;">기준일: {today_str}</p>
"""

# [섹션 1] KBO 순위표
html_body += "<h2>1. 오늘의 KBO 구단 순위</h2>"
try:
    url = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
    storage_options = {'User-Agent': 'Mozilla/5.0'}
    tables = pd.read_html(url, storage_options=storage_options)
    df_kbo = tables[0][['순위', '팀명', '승', '무', '패', '승률', '게임차']]
    html_body += df_kbo.to_html(index=False, classes="kbo-table", border=0)
except Exception:
    html_body += "<p>순위표 데이터를 가져오는 데 실패했습니다.</p>"

# [섹션 2 & 3 데이터를 담을 변수]
summary_html = "<h2>2. 분야별 종합 뉴스 요약</h2>"
detail_html = "<h2>3. 분야별 주요 뉴스 상세 (중복 제거)</h2>"

categories = [
    {
        "idx": 1, "name": "야구", "keywords": ["프로야구", "메이저리그"], 
        "context": "KBO 리그 10개 구단 전체 및 코리안 메이저리거의 동향",
        "detail_rules": "- [KBO 및 국내 야구 동향]: 중요도 순으로 최대 10개 엄선\n- [코리안 메이저리거 동향]: 중요도 순으로 최대 5개 엄선"
    },
    {
        "idx": 2, "name": "정치", "keywords": ["정치"], 
        "context": "국정 운영, 주요 정당 현안, 입법 등 정치 전반의 동향",
        "detail_rules": "- 카테고리별로 소제목을 달고, 파급력이 큰 핵심 이슈를 최대 10개 엄선"
    },
    {
        "idx": 3, "name": "경제", "keywords": ["경제", "글로벌 증시"], 
        "context": "글로벌 거시 지표, 증시, 국내외 주요 산업 및 기업 동향",
        "detail_rules": "- [글로벌 거시 및 증시], [국내 산업 및 금융] 등으로 소제목을 달고, 최대 10개 엄선"
    },
    {
        "idx": 4, "name": "IT (AI 및 사이버 보안)", "keywords": ["인공지능", "생성형 AI", "사이버보안"], 
        "context": "AI 신기술, 글로벌 빅테크 동향, 데이터센터 인프라, 사이버 보안 위협 및 거버넌스 동향",
        "detail_rules": "- [AI 신기술 및 프론티어 모델]: 최대 4~5개 엄선\n- [AI 인프라 및 하드웨어 동향]: 최대 2~3개 엄선\n- [사이버 보안 및 기술 거버넌스]: 최대 2~3개 엄선"
    },
    {
        "idx": 5, "name": "사회 및 글로벌 동향", "keywords": ["외신", "국제 정세", "특파원", "해외 재난"], 
        "context": "국내 주요 사회 현안 및 해외 주요 재난, 국제 정세 동향",
        "detail_rules": "- 국내 정치권 공방이나 경제 뉴스는 철저히 배제하세요.\n- [글로벌 주요 쟁점 및 정세]: 중요도 순으로 최대 5개 엄선\n- [해외 재난 및 사건사고]: 해외 재난 위주로 최대 5개 엄선"
    }
]

ai_model = genai.GenerativeModel(get_best_model())

for cat in categories:
    all_items = []
    for kw in cat["keywords"]:
        all_items.extend(fetch_news_items(kw, display_count=70))
    
    news_text, count = format_news_text(all_items, max_count=70)

    if count > 0:
        prompt = f"""
당신은 {cat['name']} 분야 전문 데스크입니다. 수집된 뉴스 {count}개를 바탕으로 객관적인 보고서 톤으로 작성해 주세요. (이모지 절대 금지)

반드시 아래의 두 구분자(===SUMMARY=== 와 ===DETAILS===)를 사용하여 답변을 분리하세요.
중요: 마크다운 기호(*, # 등)를 절대 사용하지 말고, 반드시 HTML 태그(<p>, <ul>, <li>, <strong>, <h3>, <a href="..."> 등)를 사용하여 구성하세요.

===SUMMARY===
- 특정 이슈에 편중되지 않게 객관적으로 작성하세요.
- {cat['context']}을 5줄 내외의 분량으로 압축하여 전체 흐름을 <p> 태그로 요약해 주세요.

===DETAILS===
- 동일한 사건이나 중복된 기사는 하나로 통합하세요. 단편적인 지역 소식은 버리세요.
{cat['detail_rules']}
- 각 이슈는 <ul>과 <li> 태그를 사용하여 나열하고, 제목은 <strong>으로 강조하세요.
- 기사 원문 링크는 반드시 <a href="실제링크">원문 기사 보기</a> 형태로 작성하세요.

[수집된 뉴스]
{news_text}
"""
        try:
            response_text = ai_model.generate_content(prompt).text
            match = re.search(r'===SUMMARY===(.*?)===DETAILS===(.*)', response_text, re.DOTALL)
            if match:
                sum_part = match.group(1).strip()
                det_part = match.group(2).strip()
            else:
                sum_part = "<p>형식 분리에 실패했습니다.</p>"
                det_part = response_text.replace("===SUMMARY===", "").replace("===DETAILS===", "").strip()

            summary_html += f"<h3>{cat['idx']}) {cat['name']}</h3>\n{sum_part}\n"
            detail_html += f"<h3>{cat['idx']}) {cat['name']}</h3>\n{det_part}\n"
            
        except Exception:
            summary_html += f"<h3>{cat['idx']}) {cat['name']}</h3><p>AI 분석 중 오류가 발생했습니다.</p>"
            detail_html += f"<h3>{cat['idx']}) {cat['name']}</h3><p>AI 분석 중 오류가 발생했습니다.</p>"
    else:
        summary_html += f"<h3>{cat['idx']}) {cat['name']}</h3><p>유효한 뉴스가 없습니다.</p>"
        detail_html += f"<h3>{cat['idx']}) {cat['name']}</h3><p>유효한 뉴스가 없습니다.</p>"

html_body += summary_html
html_body += detail_html
html_body += "</body></html>"

# ==========================================
# 4. 이메일 전송 로직
# ==========================================
try:
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"[일간 브리핑] 종합 동향 보고서 ({today_str})"
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = GMAIL_ADDRESS

    part = MIMEText(html_body, 'html')
    msg.attach(part)

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
    server.sendmail(GMAIL_ADDRESS, GMAIL_ADDRESS, msg.as_string())
    server.quit()
    print("📧 이메일 발송 성공!")
except Exception as e:
    print(f"📧 이메일 발송 실패: {e}")
