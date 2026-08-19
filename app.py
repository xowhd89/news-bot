import streamlit as st
import requests
from bs4 import BeautifulSoup
from google import genai

# 1. 화면 위장 설정 (메뉴 숨김 및 타이틀)
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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # [우회 수집] 네이버 검색 뉴스 탭: 'KBO 프로야구', 관련도순(sort=0, 인기반영), 1일 이내(pd=4)
    try:
        count = 1
        for page in range(3): # 3페이지 (총 30개 기사)
            start = page * 10 + 1
            # sort=0 (관련도순, 인기순과 유사), pd=4 (최근 1일)
            url = f"https://search.naver.com/search.naver?where=news&query=KBO+프로야구&sm=tab_opt&sort=0&pd=4&start={start}"
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 검색 결과에서 기사 제목과 링크 추출
            articles = soup.find_all('a', {'class': 'news_tit'})
            for a in articles:
                title = a.get('title') or a.text
                link = a.get('href')
                news_text += f"{count}. 제목: {title}\n링크: {link}\n\n"
                count += 1
    except Exception as e:
        pass
        
    # KBO 순위 데이터 수집
    try:
        record_url = "https://www.koreabaseball.com/TeamRank/TeamRank.aspx"
        res_record = requests.get(record_url, headers=headers)
        soup = BeautifulSoup(res_record.text, 'html.parser')
        table = soup.find('table', {'class': 'tData'})
        if table:
            record_text = table.get_text(separator=' ', strip=True)
    except:
        record_text = "순위 정보를 가져오지 못했습니다."
        
    return news_text, record_text

# 화면 구동 시 자동 분석 실행
with st.spinner("가장 핫한 당일 KBO 뉴스를 분석하고 있습니다..."):
    raw_news, raw_record = fetch_kbo_data()
    
    if not raw_news.strip():
        st.error("데이터를 읽어오지 못했습니다. 새로고침을 시도해 주세요.")
    else:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            ai_prompt = f"""
            당신은 전문적인 스포츠 애널리스트입니다. 어떠한 이모지도 절대 사용하지 마십시오. 
            아래 제공된 당일 핫이슈 데이터를 분석하여 매우 건조하고 전문적인 문서 형식으로 응답을 작성하십시오.
            
            [섹션 1: 주요 이슈 종합 요약]
            제공된 30개의 기사를 모두 분석하여, 주제가 겹치는 것은 하나로 묶어 중복을 제거하십시오.
            기사에서 다루는 '모든 핵심 이슈를 빠짐없이' 분류하여 요약하십시오. (5개 제한 없이 모두 출력)
            (중요) 각 이슈의 제목에는 제공된 원문 링크를 마크다운 양식으로 걸어주세요.
            
            [섹션 2: 구단별 주요 동향]
            제공된 30개의 기사를 분석하여, 언급된 각 구단별 이슈를 1~2줄로 빠짐없이 요약하십시오.
            
            [섹션 3: 현재 KBO 구단 순위]
            제공된 순위 원시 데이터를 바탕으로 1위부터 10위까지 순위표를 작성하십시오.
            표의 열은 [순위 / 구단명 / 승률 / 게임차] 4가지만 정확히 표시하십시오.
            
            데이터:
            [당일 인기 기사 데이터 30개]
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
