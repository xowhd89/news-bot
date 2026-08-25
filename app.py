import pandas as pd
import urllib.request
import json
import re
import google.generativeai as genai
import streamlit as st

# 깃허브 해킹 방지를 위해 스트림릿 시크릿에서 키를 불러옵니다.
NCP_CLIENT_ID = st.secrets["NCP_CLIENT_ID"]
NCP_CLIENT_SECRET = st.secrets["NCP_CLIENT_SECRET"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)

st.set_page_config(page_title="KBO 야구 브리핑 봇", page_icon="⚾")
st.title("⚾ 오늘의 KBO 뉴스 브리핑 봇")

if st.button("오늘의 야구 브리핑 가져오기"):
    with st.spinner("LG 트윈스 소식을 포함한 뉴스를 AI가 분석 중입니다..."):
        # 1. KBO 구단 순위 가져오기
        url = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
        storage_options = {'User-Agent': 'Mozilla/5.0'}
        tables = pd.read_html(url, storage_options=storage_options)
        clean_ranking = tables[0][['순위', '팀명', '승', '무', '패', '승률', '게임차']]

        st.subheader("🏆 오늘의 KBO 구단 순위")
        st.dataframe(clean_ranking, use_container_width=True)

        # 2. 최신 프로야구 뉴스 30개 수집
        search_word = urllib.parse.quote("프로야구")
        api_url = f"https://naverapihub.apigw.ntruss.com/search/v1/news?query={search_word}&display=30&sort=date"

        request = urllib.request.Request(api_url)
        request.add_header("X-NCP-APIGW-API-KEY-ID", NCP_CLIENT_ID)
        request.add_header("X-NCP-APIGW-API-KEY", NCP_CLIENT_SECRET)

        try:
            response = urllib.request.urlopen(request)
            data = json.loads(response.read().decode('utf-8'))
            news_text_list = []
            for item in data['items']:
                clean_title = re.sub(r'<.*?>|&quot;', '', item['title'])
                clean_desc = re.sub(r'<.*?>|&quot;', '', item['description'])
                news_text_list.append(f"- 제목: {clean_title}\n  내용: {clean_desc}")
            all_news_text = "\n\n".join(news_text_list)
        except Exception as e:
            st.error("뉴스 수집 실패")
            all_news_text = "뉴스 수집 실패"

        # 3. 무료 정식 모델 자동 선택 및 요약 생성
        if all_news_text != "뉴스 수집 실패":
            valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods and 'flash' in m.name.lower() and not any(x in m.name.lower() for x in ['preview', 'exp', 'omni', 'vision', 'embedding'])]
            selected_model = sorted(valid_models, reverse=True)[0] if valid_models else 'models/gemini-3.6-flash'
            
            model = genai.GenerativeModel(selected_model)
            prompt = f"""전체 뉴스 브리핑(LG 트윈스 이슈 집중), 구단별 분류, 중복 제거 후 3줄 요약 양식으로 요약해 줘.\n\n[수집된 뉴스]\n{all_news_text}"""
            summary_result = model.generate_content(prompt)

            st.divider()
            st.subheader("📰 오늘의 KBO 뉴스 브리핑")
            st.markdown(summary_result.text)
