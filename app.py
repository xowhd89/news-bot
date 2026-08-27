# ==========================================
# 일간 종합 동향 보고서 v1.1 (Streamlit App)
# ==========================================

import pandas as pd
import urllib.request
import json
import re
import datetime
from email.utils import parsedate_to_datetime
import google.generativeai as genai
import streamlit as st

# 1. API 세팅 및 설정
NCP_CLIENT_ID = st.secrets["NCP_CLIENT_ID"]
NCP_CLIENT_SECRET = st.secrets["NCP_CLIENT_SECRET"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)

st.set_page_config(page_title="일간 종합 동향 보고서 v1.1", layout="wide")
st.title("일간 종합 동향 보고서 (v1.1)")
st.write("최근 24시간 이내의 각 분야별 핵심 팩트와 맥락을 심층 분석한 일일 브리핑입니다.")

# 2. 공통 도우미 함수
def fetch_news_items(search_keyword, display_count=100):
    """단일 키워드로 기사를 검색해 24시간 이내의 아이템 리스트를 반환합니다."""
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

def format_news_text(items, max_count=50):
    """아이템 리스트를 프롬프트용 텍스트로 변환합니다."""
    target_items = items[:max_count]
    news_text_list = []
    for idx, item in enumerate(target_items, start=1):
        clean_title = re.sub(r'<.*?>|&quot;', '', item['title'])
        clean_desc = re.sub(r'<.*?>|&quot;', '', item['description'])
        link = item.get('originallink') or item.get('link')
        news_text_list.append(f"[{idx}번 뉴스]\n- 제목: {clean_title}\n- 내용: {clean_desc}\n- 링크: {link}")
    return "\n\n".join(news_text_list), len(target_items)

def get_best_model():
    valid_models = [
        m.name for m in genai.list_models()
        if 'generateContent' in m.supported_generation_methods
        and 'flash' in m.name.lower()
        and not any(x in m.name.lower() for x in ['preview', 'exp', 'omni', 'vision', 'embedding'])
    ]
    return sorted(valid_models, reverse=True)[0] if valid_models else 'models/gemini-3.6-flash'

# 3. 메인 실행 블록
if st.button("오늘의 5대 분야 종합 브리핑 생성하기", type="primary"):
    
    ai_model = genai.GenerativeModel(get_best_model())

    # ----------------------------------------------------
    # [1] 야구 (KBO + MLB 개별 수집 후 병합)
    # ----------------------------------------------------
    st.header("1. KBO 및 코리안 메이저리거 동향")
    with st.spinner("야구 순위표와 최신 뉴스를 분석 중입니다..."):
        try:
            url = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
            storage_options = {'User-Agent': 'Mozilla/5.0'}
            tables = pd.read_html(url, storage_options=storage_options)
            st.subheader("오늘의 KBO 구단 순위")
            st.dataframe(tables[0][['순위', '팀명', '승', '무', '패', '승률', '게임차']], use_container_width=True, hide_index=True)
        except Exception:
            st.error("순위표 데이터를 가져오는 데 실패했습니다.")

        # KBO 뉴스와 메이저리그 뉴스를 각각 수집하여 병합
        kbo_items = fetch_news_items("프로야구", display_count=70)
        mlb_items = fetch_news_items("메이저리그", display_count=30)
        all_baseball_items = kbo_items + mlb_items

        baseball_news, b_count = format_news_text(all_baseball_items, max_count=50)

        if b_count > 0:
            prompt_baseball = f"""
당신은 전문 야구 데스크입니다. 수집된 뉴스 {b_count}개를 바탕으로 업무용 보고서 톤으로 작성해 주세요. (출력 시 모든 이모지 사용 절대 금지)

1. KBO 리그 전체 종합 브리핑
- 특정 구단에 편중되지 않도록 객관적으로 10개 구단 전체의 주요 흐름과 화제를 2~3문단으로 요약.

2. 구단별 및 KBO 주요 뉴스
- 기사들을 [각 구단명] 또는 [KBO 일반 및 기타] 카테고리로 나누어 소제목을 달고, 그 직하단에 중복 제거된 이슈들을 나열하세요.
- 각 이슈는 다음 형식을 엄격히 지키세요:
  * [이슈 타이틀]
  * 1줄: 사실 관계 (팩트)
  * 2줄: 핵심 쟁점 또는 상황
  * 3줄: 향후 전망 또는 의미
  * [원문 기사 보기](실제 링크 URL)

3. 코리안 메이저리거 동향
- MLB 한국인 선수 관련 뉴스를 모아 위와 동일한 3줄 요약 및 원문 링크 형식으로 작성.

[수집된 뉴스]
{baseball_news}
"""
            st.markdown(ai_model.generate_content(prompt_baseball).text)
        else:
            st.warning("최근 24시간 내 유효한 야구 뉴스가 없습니다.")
    st.divider()

    # ----------------------------------------------------
    # [2] 정치 / [3] 경제 / [4] IT / [5] 사회 
    # ----------------------------------------------------
    categories = [
        {"title": "2. 정치 및 정책 동향", "keyword": "국내 정치 주요 정책 핵심 쟁점", "name": "정치"},
        {"title": "3. 거시 경제 및 산업 동향", "keyword": "글로벌 거시 경제 주요 산업 동향", "name": "경제"},
        {"title": "4. IT 및 보안 기술 동향", "keyword": "생성형 AI 인공지능 사이버보안 정보보안", "name": "IT"},
        {"title": "5. 사회 주요 쟁점", "keyword": "국내 사회 주요 사건 쟁점 이슈", "name": "사회"}
    ]

    for cat in categories:
        st.header(cat["title"])
        with st.spinner(f"{cat['name']} 분야의 최신 뉴스를 수집하고 맥락을 분석 중입니다..."):
            cat_items = fetch_news_items(cat["keyword"], display_count=100)
            news_text, count = format_news_text(cat_items, max_count=50)
            
            if count > 0:
                prompt_general = f"""
당신은 {cat['name']} 전문 데스크입니다. 수집된 뉴스 {count}개를 바탕으로 건조한 업무용 보고서 톤으로 작성해 주세요. (출력 시 모든 이모지 사용 절대 금지)

1. {cat['name']} 전체 종합 브리핑
- 오늘의 전체적인 핵심 흐름을 단 1문단(최대 3~4문장)으로 아주 짧고 간결하게 압축하여 요약해 주세요.

2. 카테고리별 주요 이슈 뉴스
- 수집된 뉴스 중 동일한 사건을 다룬 기사는 하나로 통합(중복 제거)하세요.
- 성격에 맞는 소제목(예: [국제 경제], [국내 정책] 등)으로 분류하고, 그 하단에 다음 형식을 지켜 나열하세요:
  * [이슈 타이틀]
  * 1줄: 사실 관계 (어떤 사건이나 발표가 있었는가)
  * 2줄: 핵심 쟁점 또는 관련자들의 입장
  * 3줄: 향후 예상되는 파급 효과나 일정
  * [원문 기사 보기](실제 링크 URL)

[수집된 뉴스]
{news_text}
"""
                st.markdown(ai_model.generate_content(prompt_general).text)
            else:
                st.warning(f"최근 24시간 내 유효한 {cat['name']} 뉴스가 없습니다.")
        
        st.divider()

st.success("모든 분야의 동향 보고서 작성이 완료되었습니다.")
