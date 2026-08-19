import streamlit as st
import requests
import xml.etree.ElementTree as ET
from google import genai

# 1. 화면 위장 설정
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
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # ---------------------------------------------------------
    # [수집처 변경 1] 네이버 대신 차단 없는 구글 뉴스 RSS 사용
    # 구글 뉴스에서 'KBO 프로야구' 검색 결과를 RSS로 가져옵니다.
    # ---------------------------------------------------------
    try:
        url = "https://news.google.com/rss/search?q=KBO+프로야구+when:1d&hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(url, headers=headers, timeout=10)
        root = ET.fromstring(res.text)
        
        # 상위 30개 기사 추출
        for i, item in enumerate(root.findall('.//item')[:30]):
            title = item.find('title').text
            link = item.find('link').text
            news_text += f"{i+1}. 제목: {title}\n링크: {link}\n\n"
    except Exception as e:
        print(f"뉴스 수집 오류: {e}")
        pass

    # ---------------------------------------------------------
    # [수집처 변경 2] 나무위키 KBO 리그 문서에서 순위 정보 가져오기 시도
    # KBO 공식 사이트도 차단될 수 있으므로 AI가 분석할 수 있도록 
    # 뉴스 기사 텍스트를 통해 순위 동향을 파악하도록 유도합니다.
    # ---------------------------------------------------------
    record_text = "순위 정보는 실시간 뉴스 내용을 바탕으로 분석해 주세요."
        
    return news_text, record_text

# 화면 구동 시 자동 분석 실행
with st.spinner("가장 핫한 당일 KBO 뉴스를 분석하고 있습니다..."):
    raw_news, raw_record = fetch_kbo_data()
    
    if not raw_news.strip():
        st.error("데이터를 읽어오지 못했습니다. 잠시 후 다시 시도해 주세요.")
    else:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            ai_prompt = f"""
            당신은 전문적인 스포츠 애널리스트입니다. 어떠한 이모지도 절대 사용하지 마십시오. 
            아래 제공된 당일 KBO 뉴스 데이터를 분석하여 매우 건조하고 전문적인 문서 형식으로 응답을 작성하십시오.
            
            [섹션 1: 주요 이슈 종합 요약]
            제공된 30개의 기사를 모두 분석하여, 주제가 겹치는 것은 하나로 묶어 중복을 제거하십시오.
            기사에서 다루는 '모든 핵심 이슈를 빠짐없이' 분류하여 요약하십시오. (5개 제한 없이 모두 출력)
            (중요) 각 이슈의 제목에는 제공된 원문 링크를 마크다운 양식으로 걸어주세요.
            
            [섹션 2: 구단별 주요 동향]
            제공된 30개의 기사를 분석하여, 언급된 각 구단별 이슈를 1~2줄로 빠짐없이 요약하십시오.
            
            [섹션 3: 현재 순위 동향 분석]
            기사 제목과 내용들을 종합하여 현재 KBO 상위권, 중위권, 하위권 구단들의 순위 경쟁 상황을 3~4줄로 분석해 주십시오. (공식 순위표 수집이 차단되었으므로 기사 내용 기반으로 유추)
            
            데이터:
            [당일 뉴스 데이터 30개]
            {raw_news}
            """
            
            res = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=ai_prompt,
            )
            
            st.markdown(res.text)
            
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
