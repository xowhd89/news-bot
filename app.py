import pandas as pd
import urllib.request
import json
import re
import datetime
from email.utils import parsedate_to_datetime
import google.generativeai as genai
import streamlit as st

# ==========================================
# 1. API 세팅 및 설정
# ==========================================
NCP_CLIENT_ID = st.secrets["NCP_CLIENT_ID"]
NCP_CLIENT_SECRET = st.secrets["NCP_CLIENT_SECRET"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)

st.set_page_config(page_title="일간 종합 브리핑 데스크", page_icon="📰", layout="wide")
st.title("📰 일간 종합 뉴스 브리핑 데스크")
st.write("야구, 정치, 경제, IT, 사회 순으로 최근 24시간 이내의 팩트와 맥락을 심층 분석합니다.")

# ==========================================
# 2. 공통 도우미 함수 (자동 수집 및 모델 선택)
# ==========================================
def fetch_latest_news(search_keyword):
    """지정된 키워드로 100개를 검색해 24시간 이내 최신 기사 최대 50개를 반환합니다."""
    search_word = urllib.parse.quote(search_keyword)
    api_url = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={search_word}&display=100&sort=date"

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

        target_items = recent_items[:50]
        collected_count = len(target_items)

        news_text_list = []
        for idx, item in enumerate(target_items, start=1):
            clean_title = re.sub(r'<.*?>|&quot;', '', item['title'])
            clean_desc = re.sub(r'<.*?>|&quot;', '', item['description'])
            link = item.get('originallink') or item.get('link')
            news_text_list.append(f"[{idx}번 뉴스]\n- 제목: {clean_title}\n- 내용: {clean_desc}\n- 링크: {link}")

        return "\n\n".join(news_text_list), collected_count
    except Exception as e:
        return "뉴스 수집 실패", 0

def get_best_model():
    """무료 정식 Flash 모델을 찾아 반환합니다."""
    valid_models = [
        m.name for m in genai.list_models()
        if 'generateContent' in m.supported_generation_methods
        and 'flash' in m.name.lower()
        and not any(x in m.name.lower() for x in ['preview', 'exp', 'omni', 'vision', 'embedding'])
    ]
    return sorted(valid_models, reverse=True)[0] if valid_models else 'models/gemini-3.6-flash'

# ==========================================
# 3. 메인 실행 블록
# ==========================================
if st.button("오늘의 5대 분야 종합 브리핑 생성하기", type="primary"):
    
    ai_model = genai.GenerativeModel(get_best_model())

    # ----------------------------------------------------
    # [1] 야구 (기존 로직 100% 동일 유지)
    # ----------------------------------------------------
    st.header("⚾ 1. KBO 프로야구 데스크")
    with st.spinner("야구 순위표와 최신 뉴스를 분석 중입니다..."):
        try:
            url = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
            storage_options = {'User-Agent': 'Mozilla/5.0'}
            tables = pd.read_html(url, storage_options=storage_options)
            st.subheader("📊 오늘의 KBO 구단 순위")
            st.dataframe(tables[0][['순위', '팀명', '승', '무', '패', '승률', '게임차']], use_container_width=True, hide_index=True)
        except Exception:
            st.error("순위표 데이터를 가져오는 데 실패했습니다.")

        baseball_news, b_count = fetch_latest_news("프로야구")
        if b_count > 0:
            prompt_baseball = f"""
당신은 KBO 전문 야구 데스크입니다. 아래 [수집된 뉴스 {b_count}개]를 바탕으로 작성해 주세요.
1. 📝 전체 뉴스 종합 브리핑: 오늘 KBO 주요 화제를 2~3문단으로 상세하게 (LG 트윈스 관련 이슈 집중).
2. 🏟️ 구단별 및 기타 뉴스 분류: 기사를 구단별로 묶고, 리그 규정이나 일반 소식은 [KBO 일반 및 기타 뉴스]로 분리.
3. 📋 중복 제거 뉴스 목록: 동일 사건 기사는 하나로 합치고, [이슈 타이틀] / 3줄 요약 / 🔗 [원문 기사 보기](실제 링크) 형식 준수.

[수집된 뉴스]
{baseball_news}
"""
            st.markdown(ai_model.generate_content(prompt_baseball).text)
        else:
            st.warning("수집된 야구 뉴스가 없습니다.")
    st.divider()

    # ----------------------------------------------------
    # [2] 정치 / [3] 경제 / [4] IT / [5] 사회 (반복 로직)
    # ----------------------------------------------------
    categories = [
        {"title": "🏛️ 2. 정치 및 정책 데스크", "keyword": "국내 정치 주요 정책 핵심 쟁점", "name": "정치"},
        {"title": "📈 3. 거시 경제 데스크", "keyword": "글로벌 거시 경제 주요 산업 동향", "name": "경제"},
        {"title": "💻 4. IT (AI 및 사이버 보안) 데스크", "keyword": "생성형 AI 인공지능 사이버보안 정보보안", "name": "IT(AI 및 사이버 보안)"},
        {"title": "🏢 5. 사회 주요 쟁점 데스크", "keyword": "국내 사회 주요 사건 쟁점 이슈", "name": "사회"}
    ]

    for cat in categories:
        st.header(cat["title"])
        with st.spinner(f"{cat['name']} 분야의 최신 뉴스를 수집하고 맥락을 분석 중입니다..."):
            news_text, count = fetch_latest_news(cat["keyword"])
            
            if count > 0:
                prompt_general = f"""
당신은 {cat['name']} 전문 데스크입니다. 아래 [수집된 뉴스 {count}개]를 바탕으로 2개 섹션을 작성해 주세요.

---
### 1. 📝 {cat['name']} 전체 종합 브리핑
- 수집된 기사 전체를 관통하는 오늘의 핵심 쟁점과 큰 줄기를 2~3문단으로 압축 정리해 주세요.

---
### 2. 📋 중복 제거 뉴스 전수 목록 (3줄 요약 & 원문 링크)
- 수집된 50개 뉴스 중 동일한 사건이나 유사한 분석을 다룬 기사들은 완벽하게 하나로 통합(중복 제거)하세요.
- 통합된 고유 이슈를 빠짐없이 나열하고, 각 이슈마다 아래 형식을 엄격히 준수해 주세요:
  * **[이슈 타이틀]**
  * 1줄: 무슨 사건(발언/발표)이 있었는가?
  * 2줄: 핵심 쟁점 또는 관련자들의 입장
  * 3줄: 향후 예상되는 파급 효과나 일정
  * 🔗 [원문 기사 보기](제공된 기사의 실제 원문 링크 URL)
---
[수집된 뉴스]
{news_text}
"""
                st.markdown(ai_model.generate_content(prompt_general).text)
            else:
                st.warning(f"최근 24시간 내 유효한 {cat['name']} 뉴스가 없습니다.")
        
        st.divider()

st.success("모든 분야의 브리핑이 완료되었습니다!")
