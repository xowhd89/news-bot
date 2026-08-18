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

# 본인의 API 키로 반드시 교체하십시오
GEMINI_API_KEY = "AQ.key"

def fetch_kbo_data():
    news_text = ""
    record_text = ""
    
    news_list = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for page in range(1, 3):
        url = f"https://sports.news.naver.com/kbaseball/news/list?isphoto=N&type=popular&page={page}"
        try:
            res = requests.get(url, headers=headers)
            news_list.extend(res.json().get('list', []))
        except:
            pass
            
    for i, news in enumerate(news_list[:30]):
        title = news.get('title')
        news_text += f"{i+1}. {title}\n"
        
    record_url = "https://sports.news.naver.com/kbaseball/record/index"
    try:
        res_record = requests.get(record_url, headers=headers)
        soup = BeautifulSoup(res_record.text, 'html.parser')
        table = soup.find('table')
        if table:
            record_text = table.get_text(separator=' ', strip=True)
    except:
        record_text = "순위 정보를 가져오지 못했습니다."
        
    return news_text, record_text

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("메시지를 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("분석 중...")
        
        try:
            raw_news, raw_record = fetch_kbo_data()
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            ai_prompt = f"""
            당신은 업무용 AI 어시스턴트입니다. 어떠한 이모지도 절대 사용하지 마십시오. 매우 건조하고 전문적인 문서 형식으로 아래 데이터를 분석하여 응답을 작성하십시오.
            
            제공된 데이터는 KBO 관련 30개의 최신 기사 제목과 현재 순위표 원시 데이터입니다.
            다음 3가지 섹션으로 나누어 결과를 도출하십시오.
            
            [섹션 1: 주요 뉴스 종합 요약]
            30개의 기사 중 주제가 겹치는 것은 하나로 묶어 중복을 제거하고, 가장 중요한 핵심 이슈 5가지만 선별하여 각각 2~3줄로 요약하십시오.
            
            [섹션 2: 구단별 주요 동향]
            제공된 30개의 기사 제목을 분석하여, 각 구단별(예: KIA, LG, 삼성 등 언급된 구단만)로 어떤 이슈가 있는지 요약하십시오. 각 구단당 1~2줄로 정리하십시오.
            
            [섹션 3: 현재 KBO 구단 순위]
            제공된 순위 원시 데이터를 바탕으로 1위부터 10위까지 순위표를 작성하십시오.
            표의 열은 [순위 / 구단명 / 승률 / 게임차] 4가지만 정확히 표시하십시오.
            
            데이터:
            [기사 제목 30개]
            {raw_news}
            
            [순위 원시 데이터]
            {raw_record}
            """
            
            res = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=ai_prompt,
            )
            
            result_text = res.text
            message_placeholder.markdown(result_text)
            st.session_state.messages.append({"role": "assistant", "content": result_text})
            
        except Exception as e:
            error_msg = f"데이터를 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주십시오. (에러 코드: {e})"
            message_placeholder.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
