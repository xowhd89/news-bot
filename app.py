import pandas as pd
import urllib.request
import json
import re
import datetime
from email.utils import parsedate_to_datetime
import google.generativeai as genai
import streamlit as st

# ----------------------------------------------------
# 1. 스트림릿 시크릿에서 API 키 호출
# ----------------------------------------------------
NCP_CLIENT_ID = st.secrets["NCP_CLIENT_ID"]
NCP_CLIENT_SECRET = st.secrets["NCP_CLIENT_SECRET"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)

st.set_page_config(page_title="KBO 야구 브리핑 데스크", page_icon="⚾", layout="wide")
st.title("⚾ KBO 일간 뉴스 종합 브리핑 데스크")
st.write("실행 시점 기준 **최근 24시간 이내**의 최신 프로야구 뉴스(최대 50개)를 수집하여 AI가 심층 분석합니다.")

if st.button("오늘의 KBO 종합 브리핑 생성하기", type="primary"):
    with st.spinner("순위표 조회, 24시간 내 최신 뉴스 수집 및 AI 심층 분석 중입니다..."):
        
        # ----------------------------------------------------
        # 2. KBO 구단 순위 정보 표 (요구사항 1)
        # ----------------------------------------------------
        try:
            url = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
            storage_options = {'User-Agent': 'Mozilla/5.0'}
            tables = pd.read_html(url, storage_options=storage_options)
            clean_ranking = tables[0][['순위', '팀명', '승', '무', '패', '승률', '게임차']]

            st.subheader("📊 1. KBO 구단 순위")
            st.dataframe(clean_ranking, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error("순위표 데이터를 가져오는 중 문제가 발생했습니다.")

        # ----------------------------------------------------
        # 3. 최신 프로야구 뉴스 수집 (100개 호출 -> 24시간 이내 50개 필터링)
        # ----------------------------------------------------
        search_word = urllib.parse.quote("프로야구")
        # 넉넉하게 100개를 호출하여 24시간 이내의 데이터를 최대한 확보
        api_url = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={search_word}&display=100&sort=date"

        request = urllib.request.Request(api_url)
        request.add_header("X-NCP-APIGW-API-KEY-ID", NCP_CLIENT_ID)
        request.add_header("X-NCP-APIGW-API-KEY", NCP_CLIENT_SECRET)

        try:
            response = urllib.request.urlopen(request)
            data = json.loads(response.read().decode('utf-8'))

            # 시간 필터링 기준 (현재 시간 - 24시간)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            time_limit = now_utc - datetime.timedelta(hours=24)

            recent_items = []
            for item in data['items']:
                # 기사의 발행 시간(pubDate)을 파이썬 날짜 객체로 변환
                pub_date = parsedate_to_datetime(item['pubDate'])
                
                # 24시간 이내에 작성된 기사만 통과
                if pub_date >= time_limit:
                    recent_items.append(item)

            # 필터링된 기사 중 가장 최신순으로 50개만 자르기
            target_items = recent_items[:50]
            collected_count = len(target_items)

            news_text_list = []
            for idx, item in enumerate(target_items, start=1):
                clean_title = re.sub(r'<.*?>|&quot;', '', item['title'])
                clean_desc = re.sub(r'<.*?>|&quot;', '', item['description'])
                link = item.get('originallink') or item.get('link')
                
                news_text_list.append(
                    f"[{idx}번 뉴스]\n"
                    f"- 제목: {clean_title}\n"
                    f"- 내용: {clean_desc}\n"
                    f"- 링크: {link}"
                )

            all_news_text = "\n\n".join(news_text_list)
            st.success(f"✔️ 최근 24시간 이내의 유효 기사 **{collected_count}개**를 성공적으로 확보했습니다.")
            
        except Exception as e:
            st.error(f"뉴스 수집 중 오류 발생: {e}")
            all_news_text = "뉴스 수집 실패"
            collected_count = 0

        # ----------------------------------------------------
        # 4. AI 모델 자동 선택 및 정밀 브리핑 생성 (요구사항 2, 3, 4)
        # ----------------------------------------------------
        if all_news_text != "뉴스 수집 실패" and collected_count > 0:
            valid_models = [
                m.name for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
                and 'flash' in m.name.lower()
                and not any(x in m.name.lower() for x in ['preview', 'exp', 'omni', 'vision', 'embedding'])
            ]
            selected_model = sorted(valid_models, reverse=True)[0] if valid_models else 'models/gemini-3.6-flash'
            model = genai.GenerativeModel(selected_model)

            prompt = f"""
당신은 KBO 전문 야구 데스크입니다. 아래 제공된 [최근 24시간 이내 수집된 뉴스 {collected_count}개]를 바탕으로 다음 3개 섹션을 명확한 마크다운 규격으로 작성해 주세요.

---
### 2. 📝 전체 뉴스 종합 브리핑
- 수집된 기사 전체를 관통하는 오늘 KBO 리그의 주요 화제, 판도 변화, 주요 경기 흐름을 2~3문단으로 상세하고 짜임새 있게 작성해 주세요. (특히 LG 트윈스와 관련된 주요 이슈가 있다면 핵심 포커스로 다뤄주세요.)

---
### 3. 🏟️ 구단별 및 KBO 일반/기타 뉴스 분류
- 기사들을 구단별([LG 트윈스], [KIA 타이거즈], [두산 베어스] 등)로 명확히 분류해 주세요.
- 특정 구단 소속이 아닌 리그 정책(경기수 조정 등), 국가대표팀, 야구계 일반, 전직 감독/해설위원 등의 소식은 반드시 **[KBO 일반 및 기타 뉴스]** 카테고리를 별도로 만들어 분리 배치해 주세요.

---
### 4. 📋 중복 제거 뉴스 전수 목록 (3~4줄 요약 & 원문 링크)
- 수집된 모든 뉴스 중 동일한 경기 결과나 동일 사건을 다룬 기사들은 완벽하게 하나로 통합(중복 제거)하세요.
- 통합된 모든 고유 이슈를 빠짐없이 나열하고, 각 이슈마다 아래 형식을 엄격히 준수해 주세요:
  * **[이슈 타이틀]**
  * 핵심 사실 중심의 3~4줄 요약
  * 🔗 [원문 기사 보기](제공된 뉴스 데이터의 실제 링크 URL)
---

[수집된 뉴스 데이터]
{all_news_text}
"""
            summary_result = model.generate_content(prompt)

            st.divider()
            st.markdown(summary_result.text)
            
        elif collected_count == 0:
            st.warning("최근 24시간 이내에 작성된 프로야구 뉴스가 없습니다.")
