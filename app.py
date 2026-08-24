import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from google import genai
import re
import time

# 1. 화면 설정
st.set_page_config(page_title="⚾ KBO Daily Report", layout="centered")
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

st.title("⚾ KBO & MLB 실시간 브리핑")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

def fetch_baseball_data():
    news_text = ""
    record_text = ""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # [데이터 1] 뉴스 50개 넉넉히 수집
    try:
        url = "https://news.google.com/rss/search?q=(KBO OR 프로야구) OR (메이저리그 OR 코리안리거 OR 류현진 OR 김하성 OR 이정후 OR 샌디에이고 OR 샌프란시스코)+when:1d&hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(url, headers=headers, timeout=10)
        root = ET.fromstring(res.text)
        
        for i, item in enumerate(root.findall('.//item')[:50]):
            title = item.find('title').text
            link = item.find('link').text
            news_text += f"{i+1}. 제목: {title}\n링크: {link}\n\n"
    except Exception as e:
        news_text = "뉴스 수집 실패"

    # [데이터 2] KBO 순위표 수집 (네이버 통합검색 우회)
    try:
        rank_url = "https://search.naver.com/search.naver?where=nexearch&query=KBO+%EC%88%9C%EC%9C%84"
        res_record = requests.get(rank_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res_record.text, 'html.parser')
        
        tables = soup.find_all('table')
        for table in tables:
            text = table.get_text(separator=' ', strip=True)
            if "승률" in text and "게임차" in text:
                record_text = text
                break
                
        if not record_text:
            record_text = "순위 수집 실패"
    except:
        record_text = "순위 수집 실패"
        
    return news_text, record_text

# 앱 실행 시 자동 분석 시작
with st.spinner("야구계 최신 동향을 완벽하게 분석하고 있습니다... (서버 상태에 따라 알아서 우회합니다)"):
    raw_news, raw_record = fetch_baseball_data()
    
    if not raw_news.strip() or "뉴스 수집 실패" in raw_news:
        st.error("데이터 통신에 실패했습니다. 화면을 새로고침 해 주십시오.")
    else:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # [자동 모델 검색]
            flash_models = []
            try:
                for m in client.models.list():
                    clean_name = m.name.replace("models/", "")
                    if "flash" in clean_name and "omni" not in clean_name and "exp" not in clean_name and "pro" not in clean_name:
                        flash_models.append(clean_name)
                flash_models.sort(reverse=True)
            except Exception:
                pass
                
            if not flash_models:
                flash_models = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.0-pro"]

            # [핵심] 프롬프트 단순화 및 우선순위 정렬 지시
            ai_prompt = f"""
            당신은 최고의 전문 스포츠 애널리스트입니다. 어떠한 이모지도 사용하지 마십시오. 
            아래 제공된 최신 야구 데이터를 바탕으로 사용자가 읽기 쉽도록 가독성을 극대화하여 리포트를 작성하십시오.
            
            [섹션 1: 현재 KBO 구단 순위]
            제공된 [순위 원시 데이터]를 바탕으로 1위부터 10위까지 순위표를 작성하십시오.
            (중요) 반드시 마크다운 표(Table) 형식(`| 순위 | 구단명 | 승률 | 게임차 |`)을 사용하여 엑셀처럼 깔끔하게 출력하십시오.
            
            [섹션 2: KBO 데일리 브리핑 (전체 흐름 파악)]
            어제 경기 결과에 따른 순위 변동 상황과 오늘 KBO에서 주목해야 할 가장 큰 화두를 요약하십시오.
            (중요) 글이 답답해 보이지 않도록 문장과 문장 사이에 적절히 줄바꿈(엔터)을 넣어 가독성을 높이십시오.
            
            [섹션 3: 구단별 주요 동향 요약]
            각 구단별 이슈를 찾아 구단당 1~2줄로 요약하십시오.
            (중요) 글머리 기호(Bullet points)를 사용하고, 각 구단 설명이 끝날 때마다 빈 줄(엔터 2번)을 넣어 항목 간 간격을 띄우십시오.
            
            [섹션 4: 실시간 주요 뉴스 하이라이트]
            수집된 50개의 기사 데이터를 분석하여 가십성이나 불필요한 기사는 과감히 제거하십시오.
            남은 알짜배기 기사들을 오직 다음 두 가지 카테고리로만 단순화하여 분류하십시오:
            - **[KBO 주요 뉴스]**
            - **[MLB 코리안리거 동향]**
            
            (중요) 각 카테고리 내에서 기사를 나열할 때는 무작위로 배치하지 말고, **현재 가장 화제가 되고 중요한 이슈(인기/중요도 순)가 가장 위로 올라오도록 우선순위를 매겨 배치**하십시오.
            두 카테고리를 합쳐서 총 12개~15개 내외의 리스트를 구성하십시오.
            각 이슈의 제목에는 관련된 원문 링크를 마크다운 양식으로 걸어주고, 설명은 딱 2줄 분량으로 상세히 적어주십시오.
            
            데이터:
            [순위 원시 데이터]
            {raw_record}
            
            [당일 야구 뉴스 데이터 50개]
            {raw_news}
            """
            
            # 완전 자동 우회 시스템
            success = False
            for model_name in flash_models:
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=ai_prompt,
                    )
                    st.markdown(res.text)
                    success = True
                    break
                    
                except Exception as api_e:
                    if "503" in str(api_e) or "UNAVAILABLE" in str(api_e) or "429" in str(api_e):
                        time.sleep(1.5)
                        continue 
                    else:
                        st.error(f"예상치 못한 오류 발생: {api_e}")
                        success = True
                        break
            
            if not success:
                st.error("현재 구글 서버 전체에 트래픽이 폭주하여 일시적으로 마비되었습니다. 1~2분 뒤에 새로고침해 주세요.")
                    
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
