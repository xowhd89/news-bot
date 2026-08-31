# ==========================================
# 일간 종합 동향 보고서 (Streamlit App)
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

st.set_page_config(page_title="일간 종합 동향 보고서", layout="wide")
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

def format_news_text(items, max_count=50):
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

    categories = [
        {"idx": 1, "name": "야구", "keywords": ["프로야구", "메이저리그"], "context": "KBO 리그 10개 구단 전체 및 코리안 메이저리거의 동향"},
        {"idx": 2, "name": "정치", "keywords": ["정치"], "context": "정치 및 국정 주요 정책 분야의 전반적인 동향"},
        {"idx": 3, "name": "경제", "keywords": ["경제"], "context": "글로벌 거시 경제 및 국내외 산업 분야의 전반적인 동향"},
        {"idx": 4, "name": "IT (AI 및 사이버 보안)", "keywords": ["인공지능", "사이버보안"], "context": "생성형 AI 및 정보보안/사이버보안 분야의 전반적인 동향"},
        {"idx": 5, "name": "사회 및 국제(세계) 동향", "keywords": ["사회", "국제"], "context": "국내 주요 사회 현안 및 해외 주요 재난/국제 정세 동향"}
    ]

    ai_model = genai.GenerativeModel(get_best_model())

    for cat in categories:
        with st.spinner(f"{cat['name']} 분야 분석 중..."):
            
            all_items = []
            for kw in cat["keywords"]:
                all_items.extend(fetch_news_items(kw, display_count=70))
            
            news_text, count = format_news_text(all_items, 50)

            if count > 0:
                prompt = f"""
당신은 {cat['name']} 분야 전문 데스크입니다. 수집된 뉴스 {count}개를 바탕으로 객관적인 업무용 보고서 톤으로 작성해 주세요. (출력 시 모든 이모지 사용 절대 금지)

반드시 아래의 두 구분자(===SUMMARY=== 와 ===DETAILS===)를 사용하여 답변을 두 영역으로 엄격히 분리하세요.

===SUMMARY===
- 특정 이슈나 구단/세력에 편중되지 않게 객관적으로 작성하세요.
- {cat['context']}을 5줄 내외의 분량으로 압축하여 전체 흐름을 요약해 주세요. 

===DETAILS===
- 수집된 뉴스 중 동일한 사건이나 중복된 기사는 완벽히 하나로 통합하세요.
- 단순 기관 홍보성 단신, 지자체 행사, 개인 미담 등 파급력이 낮은 소식은 제외하세요.
- 언론사 보도 집중도가 높고 사회·경제·국제적 파급력이 큰 핵심 이슈를 **최대 5~7개만 엄선**하여 나열하세요. (절대 7개를 초과하지 마세요)
- 각 고유 이슈마다 다음 형식을 반드시 지켜 나열하세요:
  * [이슈 타이틀]
  * (해당 이슈에 대한 1~2줄 내외의 핵심 요약)
  * [원문 기사 보기](제공된 실제 링크 URL)

[수집된 뉴스]
{news_text}
"""
                response_text = ai_model.generate_content(prompt).text
                
                match = re.search(r'===SUMMARY===(.*?)===DETAILS===(.*)', response_text, re.DOTALL)
                if match:
                    sum_part = match.group(1).strip()
                    det_part = match.group(2).strip()
                else:
                    sum_part = "형식 분리에 실패했습니다."
                    det_part = response_text.replace("===SUMMARY===", "").replace("===DETAILS===", "").strip()

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
