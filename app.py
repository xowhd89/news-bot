import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from google import genai
import re
import time

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

def fetch_baseball_data():
    news_text = ""
    record_text = ""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    
    # [데이터 1] 뉴스 50개 넉넉히 수집 (풀을 넓혀야 중복 제거 후에도 남는 게 많음)
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

    # [데이터 2] KBO 순위표 수집처 변경 (네이버 통합검색 우회 활용)
    try:
        # 네이버에 'KBO 순위'를 검색한 결과 페이지를 요청
        rank_url = "https://search.naver.com/search.naver?where=nexearch&query=KBO+%EC%88%9C%EC%9C%84"
        res_record = requests.get(rank_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res_record.text, 'html.parser')
        
        # 검색 결과 중 테이블(table) 태그만 싹 뒤져서 순위표 데이터 추출
        tables = soup.find_all('table')
        for table in tables:
            text = table.get_text(separator=' ', strip=True)
            # 승률과 게임차가 포함된 표가 바로 우리가 찾는 KBO 순위표!
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

            ai_prompt = f"""
            당신은 최고의 전문 스포츠 애널리스트입니다. 어떠한 이모지도 사용하지 마십시오. 
            아래 제공된 최신 야구 데이터를 바탕으로 건조하고 읽기 쉬운 리포트를 작성하십시오.
            
            [섹션 1: 현재 KBO 구단 순위]
            제공된 [순위 원시 데이터]를 바탕으로 1위부터 10위까지 순위표를 가장 먼저 작성하십시오.
            표의 열은 [순위 / 구단명 / 승률 / 게임차] 4가지만 표시하십시오.
            
            [섹션 2: KBO 데일리 브리핑 (전체 흐름 파악)]
            수집된 기사들을 종합하여, 어제 경기 결과에 따른 순위 변동 상황과 오늘 KBO에서 주목해야 할 가장 큰 화두(큰 줄기)를 3~4줄로 굵직하게 요약하십시오.
            
            [섹션 3: 구단별 주요 동향 요약]
            제공된 기사를 분석하여, 언급된 각 구단별 이슈를 찾아 구단당 1~2줄로 요약하십시오. (특정 구단에 대한 소식이 없다면 '특이 동향 없음'이라고 표기하십시오.)
            
            [섹션 4: 실시간 주요 뉴스 하이라이트 (KBO & MLB)]
            수집된 50개의 기사 데이터를 분석하여 영양가 높은 진짜 야구 이슈만 선별하십시오.
            (중요) 같은 경기 결과나 동일한 사건을 다루는 **중복된 기사들은 완벽하게 하나로 통합하여 요약**하십시오. 중복된 내용이 리스트에 여러 번 나오면 안 됩니다.
            중복을 제거하더라도, 10개 구단의 주요 소식과 메이저리거 동향을 샅샅이 찾아내어 **최소 12개에서 최대 15개의 '서로 다른' 핵심 이슈**를 리스트 형태로 나열하십시오.
            각 이슈에 대한 설명은 **정확히 2줄 분량**으로 간결하고 디테일하게 요약하십시오.
            각 이슈의 제목에는 관련된 원문 링크를 마크다운 양식으로 걸어주세요.
            
            데이터:
            [순위 원시 데이터]
            {raw_record}
            
            [당일 야구 뉴스 데이터 50개]
            {raw_news}
            """
            
            # 완전 자동 우회 시스템 (503 에러 방어)
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
