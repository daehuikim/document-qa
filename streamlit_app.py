import streamlit as st
import openai
import os
import json

# Page configuration
st.set_page_config(layout="wide")

# --- Secrets & API Key Configuration ---
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key not found. Set it in .streamlit/secrets.toml or as environment variable OPENAI_API_KEY.")
    st.stop()
openai.api_key = api_key
client = openai.OpenAI()

# --- Helper Functions ---

def generate_questions(context: str) -> list[str]:
    prompt = (
        "다음 이야기를 이어쓰기 위해 적절한 질문을 3가지 만들어주세요.\n"
        "초등학생들이 이야기를 이어쓰는 질문이니까 뒷 이야기를 계속 이어나갈 수 있도록 유도할만한 질문들을 아래의 질문 타입들을 적절하게 섞어서 3가지만 생성해주세요.\n"
        "질문 타입의 예시\n"
        "1. 만약~라면 어떻게 될까? (가정형 질문) ex) 만약 도깨비 방망이가 말하는 물건이라면 어떻게 될까요?, ...\n"
        "2. 무슨 일이 생겼을까? 이어가기 질문...\n"
        "3. 인물의 마음이나 선택을 묻는 질문...\n"
        f"현재 이야기:\n{context}\n"
        "세 가지 질문을 각 줄에 하나씩 작성하세요."
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )
    text = response.choices[0].message.content
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[:3]


def generate_feedback(raw_text: str, context: str) -> dict:
    prompt = (
        "다음은 이야기 맥락과 사용자가 작성한 부분입니다.\n"
        f"맥락:\n{context}\n"
        f"사용자 작성:\n{raw_text}\n\n"
        "이 텍스트의 *틀린 부분*(errors)과 *고칠 방법*(suggestions), "
        "그리고 *개선된 버전*(improved) 세 가지를 반드시 JSON 객체 형식으로 반환해주세요.\n"
        "예시 형식:\n{\n  \"errors\": [...], \"suggestions\": [...], \"improved\": \"...\"\n}"
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )
    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"errors": ["피드백 생성 중 파싱 오류"], "suggestions": [], "improved": content}

# --- State Transition Helpers ---

def handle_start(summary: str):
    st.session_state.summary = summary
    st.session_state.current_segment = summary
    # 질문 생성 후, 각 질문에 대한 입력과 피드백 카운트를 초기화
    st.session_state.questions = generate_questions(summary)
    n = len(st.session_state.questions)
    st.session_state.raw_inputs = [""] * n
    st.session_state.feedback_counts = [0] * n
    st.session_state.stage = "choose_q"


def choose_question(idx: int):
    st.session_state.selected_q_idx = idx
    st.session_state.stage = "write"


def submit_raw_input(text: str):
    idx = st.session_state.selected_q_idx
    st.session_state.raw_inputs[idx] = text
    st.session_state.stage = "review"


def on_feedback_decision(is_done: bool):
    idx = st.session_state.selected_q_idx
    if is_done or st.session_state.feedback_counts[idx] >= 2:
        st.session_state.current_segment += "\n" + st.session_state.raw_inputs[idx]
        st.session_state.stage = "decide_continue"
    else:
        st.session_state.feedback_counts[idx] += 1
        st.session_state.stage = "write"


def decide_continue(continue_story: bool):
    if continue_story:
        # 다음 질문들 재생성
        st.session_state.questions = generate_questions(st.session_state.current_segment)
        n = len(st.session_state.questions)
        st.session_state.raw_inputs = [""] * n
        st.session_state.feedback_counts = [0] * n
        st.session_state.stage = "choose_q"
    else:
        st.session_state.stage = "done"

# --- Initialize Session State ---
if 'stage' not in st.session_state:
    st.session_state.stage = "init"

# --- UI Flow ---
if st.session_state.stage == "init":
    st.title("🖋️ Interactive Story Builder with File Upload")
    st.write("시작할 이야기 요약을 입력하거나, 문서 파일(.txt/.md)을 업로드하세요.")
    col1, col2 = st.columns(2)
    summary_input = ""
    with col1:
        summary_input = st.text_area("이야기 요약 입력", height=200)
    with col2:
        uploaded_file = st.file_uploader("문서 업로드 (.txt, .md)", type=["txt", "md"])
        if uploaded_file:
            try:
                summary_input = uploaded_file.read().decode('utf-8')
                st.success("파일에서 요약을 불러왔습니다.")
            except Exception:
                st.error("파일을 읽는 중 오류가 발생했습니다.")

    def _on_start():
        if summary_input.strip():
            with st.spinner("질문 생성 중... 잠시만 기다려주세요…"):
                handle_start(summary_input.strip())
    st.button("시작하기", on_click=_on_start)

elif st.session_state.stage == "choose_q":
    st.subheader("다음 전개를 이어갈 질문을 골라주세요:")
    for i, q in enumerate(st.session_state.questions):
        st.button(q, key=f"q{i}", on_click=lambda i=i: choose_question(i))

elif st.session_state.stage == "write":
    idx = st.session_state.selected_q_idx
    st.subheader(f"질문: {st.session_state.questions[idx]}")
    user_text = st.text_area("답변 입력", value=st.session_state.raw_inputs[idx], height=200)
    st.button("제출", on_click=lambda text=user_text: submit_raw_input(text))

elif st.session_state.stage == "review":
    idx = st.session_state.selected_q_idx
    st.subheader("🔍 피드백 영역")
    with st.spinner("피드백 생성 중..."):
        fb = generate_feedback(st.session_state.raw_inputs[idx], st.session_state.current_segment)
    st.session_state.fb = fb

    st.markdown("**❌ 틀린 부분 (errors):**")
    for err in fb.get("errors", []):
        st.markdown(f"- {err}")

    st.markdown("**💡 고칠 방법 (suggestions):**")
    for sug in fb.get("suggestions", []):
        st.markdown(f"- {sug}")

    st.markdown("**✨ 개선된 예시:**")
    st.text_area("", value=fb.get("improved", ""), height=200)

    def apply_improved():
        st.session_state.raw_inputs[idx] = st.session_state.fb.get("improved", "")
        on_feedback_decision(True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("수정하기", on_click=lambda: on_feedback_decision(False))
    with col2:
        st.button("완료하기", on_click=lambda: on_feedback_decision(True))
    with col3:
        st.button("개선 버전 적용하기", on_click=apply_improved)

elif st.session_state.stage == "decide_continue":
    st.subheader("📖 지금까지 이어진 이야기")
    st.text_area("", value=st.session_state.current_segment, height=300)
    st.subheader("이야기를 계속 이어쓰시겠습니까?")
    col1, col2 = st.columns(2)
    with col1:
        st.button("계속 이어쓰기", on_click=lambda: decide_continue(True))
    with col2:
        st.button("이야기 완성하기", on_click=lambda: decide_continue(False))

elif st.session_state.stage == "done":
    st.subheader("✅ 최종 완성된 이야기")
    st.text_area("Story", value=st.session_state.current_segment, height=400)
    st.success("이야기가 완성되었습니다! 복사하여 사용하세요.")