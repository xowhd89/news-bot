import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from google import genai

# 1. 화면 설정
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
    
    # [뉴스] 구글 뉴스 RSS (차단 없는 안전한 수집처)
    try:
        url = "https://news.google.com/rss/search?q=KBO+프로야구+when:1d&hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(url, headers=headers, timeout=10)
        root = ET.fromstring(res.text)
        for i, item in enumerate(root.findall('.//item')[:30]):
            title = item.find('title').text
            link = item.find('link').text
            news_text += f"{i+1}. 제목: {title}\n링크: {link}\n\n"
    except Exception as e:
        news_text = "뉴스 수집 실패"

    # [순위] '우회 프록시 서버'를 통해 KBO 공식 홈페이지 데이터 추출 (차단 원천 방지)
    try:
        # api.allorigins.win 프록시를 거쳐 KBO 사이트에 우회 접속합니다.
        proxy_url = "https://api.allorigins.win/raw?url=https://www.koreabaseball.com/TeamRank/TeamRank.aspx"
        res_record = requests.get(proxy_url, headers=headers, timeout=15)
        soup = BeautifulSoup(res_record.text, 'html.parser')
        table = soup.find('table', {'class': 'tData'})
        if table:
            record_text = table.get_text(separator=' ', strip=True)
        else:
            record_text = "순위 수집 실패"
    except:
        record_text = "순위 수집 실패"
        
    return news_text, record_text

# 앱 실행 시 자동 분석
with st.spinner("가장 핫한 당일 KBO 뉴스를 분석하고 있습니다..."):
    raw_news, raw_record = fetch_kbo_data()
    
    if not raw_news.strip() or "뉴스 수집 실패" in raw_news:
        st.error("데이터를 읽어오지 못했습니다. 새로고침을 시도해 주세요.")
    else:
        try:
            # 3.6-flash 대신 가장 안정적인 최신 기본 모델 사용
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            ai_prompt = f"""
            당신은 전문적인 스포츠 애널리스트입니다. 어떠한 이모지도 절대 사용하지 마십시오. 
            아래 제공된 당일 KBO 데이터를 바탕으로 건조하고 전문적인 리포트를 작성하십시오.
            
            [섹션 1: 현재 KBO 구단 순위]
            제공된 [순위 원시 데이터]를 바탕으로 1위부터 10위까지 순위표를 가장 먼저 작성하십시오.
            표의 열은 [순위 / 구단명 / 승률 / 게임차] 4가지만 표시하십시오.
            
            [섹션 2: 주요 뉴스 종합 요약 (최대한 많이 다룰 것)]
            제공된 30개의 기사를 분석하여 주요 이슈를 뽑아내십시오.
            단, 4~5개로 너무 압축하지 말고, 사소한 기사라도 버리지 말고 **최소 10개 이상, 최대한 많은 이슈**를 뽑아서 나열하십시오.
            내용이 길어지면 안 됩니다. 각 이슈에 대한 설명은 **정확히 1~2줄 분량**으로 간결하게 핵심만 요약하십시오.
            (중요) 각 이슈의 제목에는 관련된 원문 링크를 마크다운 양식으로 걸어주세요.
            
            [섹션 3: 구단별 동향 정리]
            제공된 기사를 분석하여, 언급된 각 구단별 이슈를 1~2줄로 빠짐없이 요약하십시오.
            
            데이터:
            [순위 원시 데이터]
            {raw_record}
            
            [당일 뉴스 데이터 30개]
            {raw_news}
            """
            
            res = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=ai_prompt,
            )
            
            st.markdown(res.text)
            
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
