# ==========================================
# 일간 종합 동향 보고서 v2.3 (Streamlit App)
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

# 이모지 배제, 정갈한 UI
st.set_page_config(page_title="일간 종합 동향 보고서 v2.3", layout="wide")
st.title("일간 종합 동향 보고서")
st.write("각 분야별 24시간 이내 최신 동향을 통합 요약 및 중요도 중심 상세 분석한 보고서입니다.")

# 2. 공통 도우미 함수
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

# 3. 메인 실행 블록
if st.button("보고서 생성 실행", type="primary"):
    
    rank_container = st.container()
    st.divider()
    summary_container = st.container()
    st.divider()
    detail_container = st.container()

    # [섹션 1] KBO 순위표
    with rank_container:
        st.header("1. 오늘의 KBO 구단 순위")
        try:
            url = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
            storage_options = {'User-Agent': 'Mozilla/5.0'}
            tables = pd.read_html(url, storage_options=storage_options)
            st.dataframe(tables[0][['순위', '팀명', '승', '무', '패', '승률', '게임차']], use_container_width=True, hide_index=True)
        except Exception:
            st.error("순위표 데이터를 가져오는 데 실패했습니다.")

    # [섹션 2 & 3] 헤더 사전 할당
    with summary_container:
        st.header("2. 분야별 종합 뉴스 요약")
    with detail_container:
        st.header("3. 분야별 주요 뉴스 상세 (중복 제거)")

    # 4. 분야별 키워드 및 AI 맞춤 지시문 설정
    categories = [
        {
            "idx": 1, 
            "name": "야구", 
            "keywords": ["프로야구", "메이저리그"], 
            "context": "KBO 리그 10개 구단 전체 및 코리안 메이저리거의 동향",
            "detail_rules": "- [KBO 및 국내 야구 동향]: 중요도 순으로 최대 10개 엄선\n- [코리안 메이저리거 동향]: 중요도 순으로 최대 5개 엄선"
        },
        {
            "idx": 2, 
            "name": "정치", 
            "keywords": ["정치"], 
            "context": "국정 운영, 주요 정당 현안, 입법 등 정치 전반의 동향",
            "detail_rules": "- 카테고리별로 소제목을 달고, 파급력이 큰 핵심 이슈를 최대 10개 엄선"
        },
        {
            "idx": 3, 
            "name": "경제", 
            "keywords": ["경제", "글로벌 증시"], 
            "context": "글로벌 거시 지표, 증시, 국내외 주요 산업 및 기업 동향",
            "detail_rules": "- [글로벌 거시 및 증시], [국내 산업 및 금융] 등으로 소제목을 달고, 최대 10개 엄선"
        },
        {
            "idx": 4, 
            "name": "IT (AI 및 사이버 보안)", 
            "keywords": ["인공지능", "생성형 AI", "사이버보안"], 
            "context": "AI 신기술, 글로벌 빅테크 동향, 데이터센터 인프라, 사이버 보안 위협 및 거버넌스 동향",
            "detail_rules": "- [AI 신기술 및 프론티어 모델]: 최대 4~5개 엄선\n- [AI 인프라 및 하드웨어 동향]: 최대 2~3개 엄선\n- [사이버 보안 및 기술 거버넌스]: 최대 2~3개 엄선\n(단순 홍보성 기사, 지자체/대학 행사 등 노이즈는 철저히 배제할 것)"
        },
        {
            "idx": 5, 
            "name": "사회 및 국제(세계) 동향", 
            "keywords": ["사회 주요 쟁점", "해외 주요 사건", "지구촌 재난", "글로벌 정세"], 
            "context": "국내 주요 사회 현안 및 해외 주요 재난, 국제 정세 동향",
            "detail_rules": "- [국내 주요 사회 현안]: 중요도 순으로 최대 5개 엄선\n- [해외 및 글로벌 지구촌 동향]: 중요도 순으로 최대 5개 엄선"
        }
    ]

    ai_model = genai.GenerativeModel(get_best_model())

    # 데이터 수집 및 AI 분석 반복
    for cat in categories:
        with st.spinner(f"{cat['name']} 분야 분석 중..."):
            
            # 다중 키워드를 순회하며 뉴스 통합 수집 (정보량 확대를 위해 수집량 증가)
            all_items = []
            for kw in cat["keywords"]:
                all_items.extend(fetch_news_items(kw, display_count=70))
            
            # 수집된 뉴스 중 70개를 넉넉하게 AI에게 전달 (다양성 확보)
            news_text, count = format_news_text(all_items, max_count=70)

            if count > 0:
                prompt = f"""
당신은 {cat['name']} 분야 전문 데스크입니다. 수집된 뉴스 {count}개를 바탕으로 객관적인 업무용 보고서 톤으로 작성해 주세요. (출력 시 모든 이모지 사용 절대 금지)

반드시 아래의 두 구분자(===SUMMARY=== 와 ===DETAILS===)를 사용하여 답변을 두 영역으로 엄격히 분리하세요.

===SUMMARY===
- 특정 이슈나 구단/세력에 편중되지 않게 객관적으로 작성하세요.
- {cat['context']}을 5줄 내외의 분량으로 압축하여 전체 흐름을 요약해 주세요. 

===DETAILS===
- 수집된 뉴스 중 동일한 사건이나 중복된 기사는 완벽히 하나로 통합하세요.
- 단편적인 단신이나 중요도가 낮은 지역 소식은 과감히 버리세요.
{cat['detail_rules']}
- 각 고유 이슈마다 다음 형식을 반드시 지켜 나열하세요:
  * [이슈 타이틀]
  * (해당 이슈에 대한 1~2줄 내외의 핵심 사실, 상황, 전망을 자연스럽게 이은 요약문)
  * [원문 기사 보기](제공된 실제 링크 URL)

[수집된 뉴스]
{news_text}
"""
                response_text = ai_model.generate_content(prompt).text
                
                # 정규식을 통한 섹션 분리
                match = re.search(r'===SUMMARY===(.*?)===DETAILS===(.*)', response_text, re.DOTALL)
                if match:
                    sum_part = match.group(1).strip()
                    det_part = match.group(2).strip()
                else:
                    sum_part = "형식 분리에 실패했습니다."
                    det_part = response_text.replace("===SUMMARY===", "").replace("===DETAILS===", "").strip()

                # 화면 출력 (순차적 렌더링)
                with summary_container:
                    st.subheader(f"{cat['idx']}) {cat['name']}")
                    st.markdown(sum_part)
                
                with detail_container:
                    st.subheader(f"{cat['idx']}) {cat['name']}")
                    st.markdown(det_part)
            
            else:
                with summary_container:
                    st.subheader(f"{cat['idx']}) {cat['name']}")
                    st.warning("유효한 뉴스가 없습니다.")
                with detail_container:
                    st.subheader(f"{cat['idx']}) {cat['name']}")
                    st.warning("유효한 뉴스가 없습니다.")

    st.success("모든 분야의 동향 보고서 작성이 완료되었습니다.")
