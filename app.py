import streamlit as st
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET # RSS 파싱을 위해 다시 등판!
from google import genai
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

st.title("⚾ KBO 실시간 브리핑")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

def fetch_baseball_data():
    news_text = ""
    record_text = ""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # [데이터 1] 막힐 걱정 없는 구글 뉴스 RSS 공식 뒷문 사용 (사용자님의 KBO 큐레이션 링크 기반)
    try:
        # 일반 웹페이지 주소가 아닌, 구글이 컴퓨터에게 제공하는 공식 RSS 주소
        rss_url = "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(rss_url, headers=headers, timeout=10)
        
        # 디자인 태그(HTML)를 찾는 게 아니라, 정형화된 데이터(XML)를 읽기 때문에 영구적으로 안정적입니다.
        root = ET.fromstring(res.text)
        
        unique_news = []
        for item in root.findall('.//item'):
            title = item.find('title').text
            link = item.find('link').text
            
            if title and len(title) > 8 and title not in [n['title'] for n in unique_news]:
                unique_news.append({'title': title, 'link': link})
                
                if len(unique_news) >= 60: # 60개 넉넉히 수집
                    break
                    
        for i, news in enumerate(unique_news):
            news_text += f"{i+1}. 제목: {news['title']}\n링크: {news['link']}\n\n"
    except Exception as e:
        news_text = "뉴스 수집 실패"

    # [데이터 2] KBO 순위표 (네이버 검색결과는 봇 방어막이 매우 약해서 가장 안전한 우회로입니다)
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

            # [핵심] 환각 방지 절대 규칙 유지
            ai_prompt = f"""
            당신은 최고의 전문 스포츠 애널리스트입니다. 어떠한 이모지도 사용하지 마십시오. 
            아래 제공된 야구 데이터를 바탕으로 리포트를 작성하되, 다음의 **[절대 규칙]**을 반드시 지키십시오.
            
            [절대 규칙]
            1. 팩트 엄수 (환각 방지): 당신은 기사의 '본문'이 아닌 오직 수집된 '제목'만 보고 있습니다. 따라서 제목에 없는 구체적인 점수, 타율, 소속팀 등을 상상해서 지어내지 마십시오. 모르면 절대 적지 마십시오.
            2. 완벽한 중복 제거: 비슷한 주제나 동일한 선수를 다루는 기사 제목이 여러 개라면, **무조건 단 1개의 항목으로 통합**하십시오.
            3. 시각적 가독성: 각 뉴스 항목 앞에는 반드시 글머리 기호('-')를 붙이고, 하나의 뉴스가 끝날 때마다 반드시 1줄의 빈 줄(엔터)을 띄워 글씨가 뭉치지 않게 하십시오.
            
            -------------------------
            
            [섹션 1: 현재 KBO 구단 순위]
            제공된 [순위 원시 데이터]를 바탕으로 1위부터 10위까지 순위표를 작성하십시오.
            (반드시 마크다운 표(Table) 형식(`| 순위 | 구단명 | 승률 | 게임차 |`)을 사용하여 출력)
            
            [섹션 2: KBO 데일리 브리핑 (전체 흐름 파악)]
            어제 경기 결과에 따른 순위 변동 상황과 오늘 KBO에서 주목해야 할 가장 큰 화두를 요약하십시오.
            
            [섹션 3: 구단별 주요 동향 요약]
            제공된 '기사 제목'들을 바탕으로 각 구단별 이슈를 찾아 구단당 1~2줄로 요약하십시오. (특정 구단 소식이 없다면 '특이 동향 없음' 표기)
            
            [섹션 4: KBO 실시간 뉴스 하이라이트]
            수집된 기사 데이터를 분석하여 가십성을 제거하십시오.
            위의 [절대 규칙]에 따라 중복을 완벽히 제거한 뒤, **가장 중요한 이슈 순서대로 총 15개 내외**의 리스트를 구성하십시오.
            각 이슈의 제목에는 원문 링크를 마크다운 양식으로 걸고, 설명은 오직 제목에서 유추할 수 있는 '팩트'만 1~2줄로 명확하게 적어주십시오.
            
            데이터:
            [순위 원시 데이터]
            {raw_record}
            
            [당일 야구 뉴스 데이터 60개]
            {raw_news}
            """
            
            # 자동 우회 시스템 (503 에러 방어)
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
