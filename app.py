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

def fetch_baseball_data():
    news_text = ""
    record_text = ""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # [데이터 1] KBO + MLB 뉴스 수집
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

    # [데이터 2] KBO 순위표 우회 수집
    try:
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

# 앱 실행 시 자동 분석 시작
with st.spinner("야구계 최신 동향을 완벽하게 분석하고 있습니다..."):
    raw_news, raw_record = fetch_baseball_data()
    
    if not raw_news.strip() or "뉴스 수집 실패" in raw_news:
        st.error("데이터 통신에 실패했습니다. 화면을 새로고침 해 주십시오.")
    else:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # [완벽하게 개선된 미래 대비용 자동 검색 로직]
            target_model = 'gemini-1.5-flash' # 만약을 대비한 최후의 보루
            try:
                flash_models = []
                # 사용 가능한 모든 모델을 탐색
                for m in client.models.list():
                    if hasattr(m, 'supported_actions') and 'generateContent' in m.supported_actions:
                        # 1. 404 에러의 주범인 'models/' 텍스트를 깔끔하게 제거
                        clean_name = m.name.replace("models/", "")
                        # 2. 요금 폭탄(429 에러)을 피하기 위해 'flash' 모델만 수집
                        if 'flash' in clean_name.lower():
                            flash_models.append(clean_name)
                
                if flash_models:
                    # 3. 이름(버전)을 내림차순 정렬하여 가장 높은 버전을 1순위로!
                    flash_models.sort(reverse=True)
                    target_model = flash_models[0]
            except Exception:
                pass # 탐색 실패 시에도 기본값으로 문제없이 넘어가게 처리
            
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
            수집된 50개의 기사 중 영양가 높은 진짜 야구 이슈(경기 결과, 순위 싸움, 부상, 콜업, 트레이드 등)만 선별하십시오.
            국내 구단 소식과 메이저리거들의 활약상도 반드시 포함하여 **최소 12개 이상 최대한 많은 이슈**를 리스트 형태로 나열하십시오.
            각 이슈에 대한 설명은 **정확히 2줄 분량**으로 간결하고 디테일하게 요약하십시오.
            (중요) 각 이슈의 제목에는 관련된 원문 링크를 클릭할 수 있도록 마크다운 양식으로 걸어주세요.
            
            데이터:
            [순위 원시 데이터]
            {raw_record}
            
            [당일 야구 뉴스 데이터 50개]
            {raw_news}
            """
            
            # 찾아낸 최적의 최신 모델을 투입
            res = client.models.generate_content(
                model=target_model,
                contents=ai_prompt,
            )
            
            st.markdown(res.text)
            
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
