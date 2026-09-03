# ==========================================
# 일간 종합 동향 보고서 v2.5 (Streamlit App)
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

st.set_page_config(page_title="일간 종합 동향 보고서 v2.5", layout="wide")
st.title("일간 종합 동향 보고서")
st.write("각 분야별 24시간 이내 최신 동향을 통합 요약 및 중요도 중심 상세 분석한 보고서입니다.")

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

if st.button("보고서 생성 실행", type="primary"):
    
    rank_container = st.container()
    st.divider()
    summary_container = st.container()
    st.divider()
    detail_container = st.container()

    with rank_container:
        st.header("1. 오늘의 KBO 구단 순위")
        try:
            url = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
            storage_options = {'User-Agent': 'Mozilla/5.0'}
            tables = pd.read_html(url, storage_options=storage_options)
            df_kbo = tables[0][['순위', '팀명', '승', '무', '패', '승률', '게임차']]
            
            # 모바일 화면 짤림 방지를 위한 반응형 HTML 테이블 렌더링
            html_table = df_kbo.to_html(index=False, classes="kbo-table", border=0)
            st.markdown(f"""
                <style>
                .kbo-table {{ width: 100%; text-align: center; font-size: 12px; border-collapse: collapse; }}
                .kbo-table th {{ text-align: center; background-color: #262730; color: white; padding: 6px; border-bottom: 1px solid #444; }}
                .kbo-table td {{ padding: 6px; border-bottom: 1px solid #333; }}
                </style>
                {html_table}
            """, unsafe_allow_html=True)
            
        except Exception:
            st.error("순위표 데이터를 가져오는 데 실패했습니다.")

    with summary_container:
        st.header("2. 분야별 종합 뉴스 요약")
    with detail_container:
        st.header("3. 분야별 주요 뉴스 상세 (중복 제거)")

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
            "detail_rules": "- [AI 신기술 및 프론티어 모델]: 최대 4~5개 엄선\n- [AI 인프라 및 하드웨어 동향]: 최대 2~3개 엄선\n- [사이버 보안 및 기술 거버넌스]: 최대 2~3개 엄선\n(단순 홍보성 기사, 행사 소식 등 노이즈는 철저히 배제)"
        },
        {
            "idx": 5, 
            "name": "사회 및 글로벌 동향", 
            "keywords": ["외신", "국제 정세", "특파원", "해외 재난"], 
            "context": "국내 주요 사회 현안 및 해외 주요 재난, 국제 정세 동향",
            "detail_rules": "- 국내 정치권 공방이나 주식/기업 관련 경제 뉴스는 철저히 배제하세요. (중복 방지)\n- [글로벌 주요 쟁점 및 정세]: 중요도 순으로 최대 5개 엄선\n- [해외 재난 및 사건사고]: 해외 재난 위주로 최대 5개 엄선"
        }
    ]

    ai_model = genai.GenerativeModel(get_best_model())

    for cat in categories:
        with st.spinner(f"{cat['name']} 분야 분석 중..."):
            all_items = []
            for kw in cat["keywords"]:
                all_items.extend(fetch_news_items(kw, display_count=70))
            
            news_text, count = format_news_text(all_items, max_count=70)

            if count > 0:
                prompt = f"""
당신은 {cat['name']} 분야 전문 데스크입니다. 수집된 뉴스 {count}개를 바탕으로 객관적인 보고서 톤으로 작성해 주세요. (이모지 절대 금지)

반드시 아래의 두 구분자(===SUMMARY=== 와 ===DETAILS===)를 사용하여 답변을 두 영역으로 분리하세요.

===SUMMARY===
- 특정 이슈에 편중되지 않게 객관적으로 작성하세요.
- 분량 제한을 해제합니다. 아래 ===DETAILS=== 에 선정된 **모든 개별 뉴스의 핵심 내용이 하나도 빠짐없이** 종합 요약 문단에 포함되어야 합니다.
- 선정된 각 이슈가 서로 유기적으로 연결된 하나의 풍성하고 완성된 브리핑 글이 되도록 작성해 주세요.

===DETAILS===
- 수집된 뉴스 중 동일한 사건이나 중복된 기사는 하나로 통합하세요.
- 단편적인 단신이나 중요도가 낮은 지역 소식은 버리세요.
{cat['detail_rules']}
- 각 이슈마다 다음 형식을 반드시 지켜 나열하세요:
  * [이슈 타이틀]
  * (해당 이슈에 대한 1~2줄 내외의 요약문)
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
