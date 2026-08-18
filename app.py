import streamlit as st
import requests
from bs4 import BeautifulSoup
from google import genai

st.set_page_config(page_title="Gemini", layout="centered")
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

st.title("Gemini")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

def fetch_kbo_data():
    news_text = ""
    record_text = ""
    news_list = []
    
    # 봇 차단을 피하기 위해 실제 윈도우용 크롬 브라우저처럼 완벽히 위장
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://m.sports.naver.com/"
    }
    
    try:
        for page in range(1, 3):
            url = f"https://sports.news.naver.com/kbaseball/news/list?isphoto=N&type=popular&page={page}"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                news_list.extend(res.json().get('list', []))
            else:
                st.error(f"네이버 서버 접근 차단 (상태 코드: {res.status_code})")
    except Exception as e:
        pass
            
    for i, news in enumerate(news_list[:30]):
        title = news.get('title')
        oid = news.get('oid')
        aid = news.get('aid')
        link = f"https://m.sports.naver.com/kbaseball/article/{oid}/{aid}"
        news_text += f"{i+1}. 제목: {title}\n링크: {link}\n\n"
        
    record_url = "https://sports.news.naver.com/kbaseball/record/index"
    try:
        res_record = requests.get(record_url, headers=headers, timeout=5)
        soup = BeautifulSoup(res_record.text, 'html.parser')
        table = soup.find('table')
        if table:
            record_text = table.get_text(separator=' ', strip=True)
    except:
        record_text = "순위 정보를 가져오지 못했습니다."
        
    return news_text, record_text

with st.spinner("최신 KBO 데이터를 분석하고 있습니다..."):
    raw_news, raw_record = fetch_kbo_data()
    
    if not raw_news.strip():
        st.error("데이터를 읽어오지 못했습니다. 네이버 서버에 의해 접근이 차단되었을 수 있습니다.")
    else:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            ai_prompt = f"""
            당신은 업무용 AI 어시스턴트입니다. 어떠한 이모지도 절대 사용하지 마십시오. 
            매우 건조하고 전문적인 문서 형식으로 아래 데이터를 분석하여 응답을 작성하십시오.
            
            제공된 데이터는 KBO 관련 30개의 최신 기사 제목, 원문 링크, 현재 순위표 데이터입니다.
            다음 3가지 섹션으로 나누어 결과를 도출하십시오.
            
            [섹션 1: 주요 뉴스 종합 요약]
            30개의 기사 중 주제가 겹치는 것은 하나로 묶어 중복을 제거하고, 가장 중요한 핵심 이슈 5가지만 선별하여 각각 2~3줄로 요약하십시오.
            각 이슈의 제목에는 제공된 원문 링크를 마크다운 양식으로 걸어주세요.
            
            [섹션 2: 구단별 주요 동향]
            제공된 30개의 기사를 분석하여, 각 구단별로 어떤 이슈가 있는지 요약하십시오. 각 구단당 1~2줄로 정리하십시오.
            
            [섹션 3: 현재 KBO 구단 순위]
            제공된 순위 원시 데이터를 바탕으로 1위부터 10위까지 순위표를 작성하십시오.
            표의 열은 [순위 / 구단명 / 승률 / 게임차] 4가지만 정확히 표시하십시오.
            
            데이터:
            [기사 데이터 30개]
            {raw_news}
            
            [순위 원시 데이터]
            {raw_record}
            """
            
            res = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=ai_prompt,
            )
            
            st.markdown(res.text)
            
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
