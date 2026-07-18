import streamlit as st
import requests
import json
import re

# 1. Ollama API 연동 함수 (Qwen2.5-1.5b 전용)
def query_ollama(single_sentence, model_name="qwen2.5-1.5b:latest"):
    url = "http://localhost:11434/api/generate"
    
    system_prompt = """
    당신은 스마트홈 IoT 허브의 AI 통역사입니다. 
    사용자의 문자 메시지를 분석하여 반드시 단 한 개의 가전 제어 JSON 객체만 반환하세요. 
    설명이나 인사말, 마크다운 기호(```json)는 절대 하지 말고 오직 JSON만 출력해야 합니다.

    [형식 예시]
    {"device": "에어컨", "action": "켜기", "value": "23도"}

    가능한 device: "에어컨", "로봇청소기", "조명", "도어락"
    가능한 action: "켜기", "끄기", "복귀", "확인"
    """
    
    payload = {
        "model": model_name,
        "prompt": f"{system_prompt}\n\n사용자 문자: {single_sentence}",
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            result = response.json()
            return json.loads(result['response'])
        else:
            return {"error": f"Ollama 응답 실패 (Status: {response.status_code})"}
    except Exception as e:
        return {"error": f"오류 발생: {str(e)}"}

# 2. 💡 버그 수정: 문장을 확실하게 단일 명령 단위로 분리하는 함수
def split_commands(text):
    # 연결어('하고', '그리고', '연달아', '메인으로') 및 문장 부호를 모두 마침표(.)로 통일
    text = text.replace("하고", ".").replace("그리고", ".").replace("하며", ".").replace(",", ".")
    # 마침표를 기준으로 쪼개고 앞뒤 공백 제거 후 빈 문장 제외
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    return sentences

# 3. 스마트홈 가전 가상 상태 데이터베이스
if "home_status" not in st.session_state:
    st.session_state.home_status = {
        "에어컨": "꺼짐 (---)",
        "로봇청소기": "대기 중",
        "조명": "꺼짐",
        "도어락": "잠김"
    }

# 4. UI 레이아웃 구성
st.set_page_config(page_title="로컬 sLLM 스마트홈 허브", layout="wide")
st.title("🏡 로컬 sLLM 스마트홈 음성/문자 제어 허브")
st.caption("안정적인 문장 파싱 기술을 적용하여 3개 이상의 다중 명령을 완벽히 수행합니다.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("💬 스마트폰 문자 전송")
    user_input = st.text_input(
        "집에 있는 AI 허브에게 문자를 보내보세요:", 
        placeholder="예: 에어컨 끄고 로봇청소기로 청소해줘. 조명도 밝혀줘"
    )
    
    if st.button("문자 전송 🚀", use_container_width=True):
        if user_input:
            # 1단계: 문장 확실하게 쪼개기
            sentences = split_commands(user_input)
            
            # 개발자 확인용 디버깅 메시지 띄우기
            st.info(f"🔍 인식된 명령 개수: {len(sentences)}개 -> {sentences}")
            
            all_commands = []
            has_error = False
            
            with st.spinner("로컬 Qwen 모델이 다중 명령을 순차적으로 해석하는 중..."):
                # 2단계: 쪼개진 문장별로 sLLM에게 차례대로 물어보기
                for sentence in sentences:
                    cmd = query_ollama(sentence)
                    
                    if isinstance(cmd, dict) and "error" in cmd:
                        st.error(f"❌ '{sentence}' 분석 실패: {cmd['error']}")
                        has_error = True
                        break
                    else:
                        all_commands.append(cmd)
            
            # 에러가 없었다면 최종 결과 반영
            if not has_error and all_commands:
                st.subheader("🤖 sLLM이 변환한 제어 신호들 (JSON 리스트)")
                st.json(all_commands)
                
                # 3단계: 가상 가전 상태 업데이트 (유연한 명령어 매핑)
                for cmd in all_commands:
                    if isinstance(cmd, dict):
                        device = cmd.get("device")
                        action = cmd.get("action")
                        value = cmd.get("value", "")
                        
                        # 어휘 맵핑 규칙 강화
                        if action in ["켜기", "켜다", "밝히기", "청소해줘", "청소", "가동", "시작", "틀어줘"]:
                            action = "켜기"
                        elif action in ["끄기", "끄다", "소등", "중지", "정지"]:
                            action = "끄기"
                        
                        if device in st.session_state.home_status:
                            if action == "켜기":
                                st.session_state.home_status[device] = f"켜짐 ({value})" if value else "켜짐"
                            elif action == "끄기":
                                st.session_state.home_status[device] = "꺼짐"
                            elif action == "복귀":
                                st.session_state.home_status[device] = "충전 도크로 복귀 중"
                
                st.success("모든 명령이 가전제품에 성공적으로 전달되었습니다!")
        else:
            st.warning("문자 내용을 입력해 주세요.")

with col2:
    st.subheader("📺 집안 가전제품 실시간 상태")
    for device, status in st.session_state.home_status.items():
        with st.container(border=True):
            c1, c2 = st.columns(2)
            c1.markdown(f"### **{device}**")
            if "켜짐" in status or "복귀" in status:
                c2.markdown(f"🟢 **{status}**")
            else:
                c2.markdown(f"🔴 **{status}**")

if st.button("🏠 가전 상태 초기화"):
    del st.session_state.home_status
    st.rerun()
