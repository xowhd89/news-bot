import streamlit as st
import requests
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
    record_text = "순위 | 구단명 | 승률 | 게임차\n---|---|---|---\n"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # [데이터 1] 차단 없는 다음 스포츠 KBO 순위 API 직접 호출
    try:
        rank_api_url = "https://sports.daum.net/prx/p/pub/kbo/ranking/team_ranking.json"
        res_rank = requests.get(rank_api_url, headers=headers, timeout=10)
        rank_data = res_rank.json()
        
        # JSON 데이터에서 순위표를 완벽한 마크다운 표 형태로 조립
        for team in rank_data['list']:
            rank = team['rank']
            name = team['nameKo']
            win_rate = team['winRate']
            game_diff = team['gameDiff']
            record_text += f"{rank} | {name} | {win_rate} | {game_diff}\n"
    except Exception as e:
        record_text = "순위 수집 실패 (API 오류)"

    # [데이터 2] 네이버 스포츠 KBO 최신 뉴스 API 직접 호출 (구글 대신 한국 트렌드 반영)
    try:
        news_api_url = "https://sports.news.naver.com/kbaseball/news/list?isphoto=N&page=1"
        res_news = requests.get(news_api_url, headers=headers, timeout=10)
        news_data = res_news.json()
        
        unique_news = []
        # 네이버 스포츠 뉴스 1페이지와 2페이지(총 40개)를 긁어옵니다.
        for page in [1, 2]:
            url = f"https://sports.news.naver.com/kbaseball/news/list?isphoto=N&page={page}"
            res = requests.get(url, headers=headers, timeout=10)
            data = res.json()
            
            for item in data.get('list', []):
                title = item.get('title', '')
                oid = item.get('oid', '')
                aid = item.get('aid', '')
                if title and title not in [n['title'] for n in unique_news]:
                    link = f"https://sports.news.naver.com/news?oid={oid}&aid={aid}"
                    unique_news.append({'title': title, 'link': link})
                    
        for i, news in enumerate(unique_news[:40]):
            news_text += f"{i+1}. 제목: {news['title']}\n링크: {news['link']}\n\n"
    except Exception as e:
        news_text = "뉴스 수집 실패 (API 오류)"
        
    return news_text, record_text

# 앱 실행 시 자동 분석 시작
with st.spinner("야구계 최신 동향을 완벽하게 분석하고 있습니다... (약 10초 소요)"):
    raw_news, raw_record = fetch_baseball_data()
    
    if "순위 수집 실패" in raw_record and "뉴스 수집 실패" in raw_news:
        st.error("데이터 통신에 실패했습니다. 화면을 새로고침 해 주십시오.")
    else:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
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
            아래 제공된 야구 데이터를 바탕으로 리포트를 작성하되, 다음의 **[절대 규칙]**을 반드시 지키십시오.
            
            [절대 규칙]
            1. 팩트 엄수 (환각 방지): 제공된 '제목'에 없는 점수, 타율, 소속팀을 절대 상상해서 지어내지 마십시오.
            2. 완벽한 중복 제거: 비슷한 주제나 동일한 선수를 다루는 기사 제목이 여러 개라면, **무조건 1개의 항목으로 통합**하십시오.
            3. 시각적 가독성: 각 뉴스 항목 앞에는 반드시 글머리 기호('-')를 붙이고, 항목 간 빈 줄(엔터)을 띄워 글씨가 뭉치지 않게 하십시오.
            
            -------------------------
            
            [섹션 1: 현재 KBO 구단 순위]
            제공된 [순위 데이터]는 이미 마크다운 표 형식으로 완성되어 있습니다. 
            이 데이터를 그대로, 1글자도 바꾸지 말고 정확하게 출력하십시오.
            
            [섹션 2: KBO 데일리 브리핑 (전체 흐름 파악)]
            제공된 기사 제목들을 종합하여 어제 KBO에서 가장 화제가 된 큰 줄기 2~3가지를 요약하십시오.
            
            [섹션 3: 구단별 주요 동향 요약]
            제공된 '기사 제목'들을 바탕으로 각 구단별 이슈를 찾아 구단당 1~2줄로 요약하십시오. (특정 구단 소식이 없다면 '특이 동향 없음' 표기)
            
            [섹션 4: KBO 실시간 뉴스 하이라이트]
            수집된 기사 데이터를 분석하여 가십성을 제거하십시오.
            위의 [절대 규칙]에 따라 중복을 완벽히 제거한 뒤, **가장 중요한 이슈 순서대로 총 15개 내외**의 리스트를 구성하십시오.
            각 이슈의 제목에는 원문 링크를 마크다운 양식으로 걸고, 설명은 오직 제목에서 유추할 수 있는 '팩트'만 1~2줄로 명확하게 적어주십시오.
            
            데이터:
            [순위 데이터]
            {raw_record}
            
            [당일 야구 뉴스 데이터 40개]
            {raw_news}
            """
            
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
                st.error("현재 구글 서버 트래픽 폭주로 일시적 마비 상태입니다. 1~2분 뒤 새로고침해 주세요.")
                    
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
