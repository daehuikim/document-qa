import streamlit as st
import openai
import ast
import json
import re
import warnings
warnings.filterwarnings("ignore", message=".*widget with key.*default value.*")


def _on_accept_improved():
    # 1) FB에서 받은 improved 문장을 꺼내 붙이기
    improved = st.session_state.fb["improved"]
    st.session_state.current_segment += "\n" + improved

    # 2) recommend_phase 초기화
    st.session_state.recommend_phase = False

    # 3) 다음 단계로 이동
    st.session_state.stage = "decide_continue"


def refine_extension(context: str, extension: str) -> str:
    prompt = (
        "아래 두 부분을 **초등학생이 만든 동화책** 어투로 자연스럽게 이어붙일 수 있게,"
        "말투와 문법을 통일하고, 비속어 없이 다듬어주세요."
        "작은 따옴표(\')와 큰 따옴표(\")를 적절한 사용법에 맞게 고쳐주도록 고려해줘."
        "\n\n"
        f"■ 앞이야기:\n{context}\n\n"
        f"■ 새로 쓴 부분:\n{extension}\n\n"
        "=> 다듬어진 ‘새로 쓴 부분’만 출력해주세요."
    )
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role":"user","content":prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def refine_story_to_childrens_book(story: str) -> str:
    prompt = (
        "아래 이야기를 **초등학생이 만든 동화책**처럼 읽히도록,"
        "말투와 문법을 통일하고, 비속어를 모두 제거한"
        "자연스러운 한국어 이야기로 바꿔주세요."
        "단, 새로운 내용이나 창의적 요소를 추가하지 말고,"
        "오직 문장 표현과 어투만 부드럽게 다듬어주세요.\n\n"
        f"원본 이야기:\n{story}\n\n"
        "=> 다듬어진 최종 이야기만 텍스트로 출력해주세요."
    )
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role":"user","content":prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


# Page configuration
st.set_page_config(layout="wide")

# --- Secrets & API Key Configuration ---
api_key = st.secrets["OPENAI_API_KEY"]
#api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key not found. Set it in .streamlit/secrets.toml or as environment variable OPENAI_API_KEY.")
    st.stop()
openai.api_key = api_key
client = openai.OpenAI()

# --- filtering ---
KOR_PROFANITY_REGEX = re.compile("[시씨씪슈쓔쉬쉽쒸쓉](?:[0-9]*|[0-9]+ *)[바발벌빠빡빨뻘파팔펄]|[섊좆좇졷좄좃좉졽썅춍봊]|[ㅈ조][0-9]*까|ㅅㅣㅂㅏㄹ?|ㅂ[0-9]*ㅅ|[ㅄᄲᇪᄺᄡᄣᄦᇠ]|[ㅅㅆᄴ][0-9]*[ㄲㅅㅆᄴㅂ]|[존좉좇][0-9 ]*나|[자보][0-9]+지|보빨|[봊봋봇봈볻봁봍] *[빨이]|[후훚훐훛훋훗훘훟훝훑][장앙]|[엠앰]창|애[미비]|애자|[가-탏탑-힣]색기|(?:[샊샛세쉐쉑쉨쉒객갞갟갯갰갴겍겎겏겤곅곆곇곗곘곜걕걖걗걧걨걬] *[끼키퀴])|새 *[키퀴]|[병븅][0-9]*[신딱딲]|미친[가-닣닥-힣]|[믿밑]힌|[염옘][0-9]*병|[샊샛샜샠섹섺셋셌셐셱솃솄솈섁섂섓섔섘]기|[섹섺섻쎅쎆쎇쎽쎾쎿섁섂섃썍썎썏][스쓰]|[지야][0-9]*랄|니[애에]미|갈[0-9]*보[^가-힣]|[뻐뻑뻒뻙뻨][0-9]*[뀨큐킹낑)|꼬[0-9]*추|곧[0-9]*휴|[가-힣]슬아치|자[0-9]*박꼼|빨통|[사싸](?:이코|가지|[0-9]*까시)|육[0-9]*시[랄럴]|육[0-9]*실[알얼할헐]|즐[^가-힣]|찌[0-9]*(?:질이|랭이)|찐[0-9]*따|찐[0-9]*찌버거|창[녀놈]|[가-힣]{2,}충[^가-힣]|[가-힣]{2,}츙|부녀자|화냥년|환[양향]년|호[0-9]*[구모]|조[선센][징]|조센|[쪼쪽쪾](?:[발빨]이|[바빠]리)|盧|무현|찌끄[레래]기|(?:하악){2,}|하[앍앜]|[낭당랑앙항남담람암함][ ]?[가-힣]+[띠찌]|느[금급]마|文在|在寅|(?<=[^\n])[家哥]|속냐|[tT]l[qQ]kf|Wls|[ㅂ]신|[ㅅ]발|[ㅈ]밥")

def go_storybook():
    st.session_state.stage = "storybook"

def contains_profanity(text: str) -> bool:
    return bool(KOR_PROFANITY_REGEX.search(text))

def is_story_related(text: str) -> bool:
    # 최소 20자 기준만 사용
    return len(text.strip()) >= 20
# --- Helper Functions ---

def generate_questions(context: str) -> list[str]:
    prompt = (
        "다음 이야기를 이어쓰기 위해 적절한 질문을 3가지 만들어주세요.\n"
        "초등학생들이 이야기를 이어쓰는 질문이니까 뒷 이야기를 계속 이어나갈 수 있도록 유도할만한 질문들을 아래의 질문 타입들을 적절하게 섞어서 3가지만 생성해주세요.\n"
        "초등학생들의 수준에 맞게 호기심을 유발하면서, 어렵지 않은 단어들로 구성된 질문들로 뒷 이야기를 잘 이어가도록 유도해주세요.\n"
        "반드시 한국어로만 작성해주세요\n"
        "질문 타입의 예시\n"
        "1. 만약~라면 어떻게 될까? (가정형 질문) ex) 만약 도깨비 방망이가 말하는 물건이라면 어떻게 될까요?, ...\n"
        "2. 무슨 일이 생겼을까? 이어가기 질문...\n"
        "3. 인물의 마음이나 선택을 묻는 질문...\n"
        f"현재 이야기:\n{context}\n"
        "세 가지 질문을 각 줄에 하나씩 작성하세요."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )
    text = response.choices[0].message.content
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[:3]+["나 자신의 창의적인 이야기를 이어나갈래!"]


def generate_feedback(raw_text: str, context: str) -> dict:
    prompt = (
        "다음은 이야기 맥락과 사용자가 작성한 부분입니다.\n"
        f"맥락:\n{context}\n"
        f"사용자 작성:\n{raw_text}\n\n"
       "이 텍스트의 *잘한 부분*(positives), *틀린 부분*(errors), *고칠 방법*(suggestions), "
        "그리고 *개선된 버전*(improved) 세 가지를 반드시 JSON 객체 형식으로 반환해주세요.\n"
        "이 피드백은 초등학생들을 위한 피드백임으로 초등학생들이 이해하기 쉽게 기초적인 내용으로 반드시 한국어로만 작성해주세요.\n"
        "교육적인 목적의 피드백을 위하여 반드시 맞춤법을 맞추고 비속어 약어 (ㅋㅋ, ㅎㅎ 등)의 사용을 지적해주고 교육적인 내용을 긍정적으로보게 해주세요.\n"
        "예시 형식:\n{\n  \"positives\": [...], \"errors\": [...], \"suggestions\": [...], \"improved\": \"...\"\n}"
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )
    content = response.choices[0].message.content
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
        match = re.search(r"(\{.*\})", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        try:
            return ast.literal_eval(content)
        except (ValueError, SyntaxError):
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

    # --- 새 질문마다 review 상태 초기화 ---
    st.session_state.edit_mode = False
    st.session_state.fb_needs_update = True
    st.session_state.pop("fb", None)
    st.session_state.pop("edit_text", None)
    st.session_state.recommend_phase = False
    # ----------------------------------------

    st.session_state.stage = "write"


def submit_raw_input(text: str):
    idx = st.session_state.selected_q_idx
    st.session_state.raw_inputs[idx] = text
    st.session_state.stage = "review"
    
def _on_raw_submit_with_spinner(text: str):
    # 1) 빈 입력 체크
    if not text.strip():
        st.error("답변을 입력해주세요.")
        return

    # 2) 욕설 검출
    if contains_profanity(text):
        st.error("비속어가 포함되지 않은 답변을 작성해주세요.")
        return

    # 3) 길이 체크
    if not is_story_related(text):
        st.error("최소 20자 이상의 답변을 입력해주세요.")
        return

    # 모두 통과 시, 스피너와 함께 피드백 단계로 이동
    with st.spinner("피드백 생성 중... 잠시만 기다려주세요…"):
        submit_raw_input(text)

def handle_raw_submit(text: str):
    # 1) 빈 입력 체크
    if not text.strip():
        st.error("답변을 입력해주세요.")
        return

    # 2) 욕설 검출
    if contains_profanity(text):
        st.error("비속어가 포함되지 않은 답변을 작성해주세요.")
        return

    # 3) 길이 체크
    if not is_story_related(text):
        st.error("최소 20자 이상의 답변을 입력해주세요.")
        return

    # 모두 통과 시 제출
    submit_raw_input(text)

def on_feedback_decision(is_done: bool):
    idx = st.session_state.selected_q_idx
    if is_done or st.session_state.feedback_counts[idx] >= 2:
        # 1) 원본 앞이야기
        context = st.session_state.current_segment
        # 2) 사용자가 쓴 새 부분
        ext = st.session_state.raw_inputs[idx]
        # 3) 톤 통일 다듬기
        refined_ext = refine_extension(context, ext)
        # 4) 붙이기
        st.session_state.current_segment += "\n" + refined_ext
        # 5) 다음으로
        st.session_state.stage = "decide_continue"
    else:
        st.session_state.feedback_counts[idx] += 1
        st.session_state.stage = "write"

def _on_apply_improved():
    idx = st.session_state.selected_q_idx
    # 1) 추천 예시를 edit buffer에 넣고
    st.session_state.edit_text = st.session_state.fb["improved"]
    # 2) recommend_phase를 켜서 두 가지 선택지 화면으로 전환
    st.session_state.recommend_phase = True

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
        
example_title=[
    "✅ 1. **시간**의 흐름에 따라 요약",
    "✅ 2. **장소**의 이동에 따라 요약",
    "✅ 3. **이야기 구조**에 따라 요약 \n\n(발단–전개–위기–절정–결말)",
    "✅ 4. **육하원칙**에 따라 요약 \n\n(누가, 언제, 어디서, 무엇을, 어떻게, 왜)",
    "✅ 5. **등장인물** 중심 요약"
]

examples=[
    "**옛날**에 흥부와 놀부 형제가 살았어요. **그러던 어느 날,** 욕심 많은 형 놀부는 착한 동생 흥부를 집에서 내쫓았고, 흥부는 가난하지만 성실하게 살아갔어요. **그러던 중,** 어느 날 흥부는 다친 제비를 우연히 발견하고 정성껏 치료해 주었어요. **며칠 뒤,** 제비는 고마움의 표시로 박씨 한 알을 물어다 주었고, 흥부는 그 박씨를 정성껏 가꾸었어요. **그러자** 박이 자라 열매가 맺혔고, 그 속에서는 금은보화가 나와 흥부는 큰 부자가 되었어요. **이 소식을 들은** 놀부는 욕심을 부려 일부러 제비 다리를 부러뜨린 뒤 박씨를 얻었어요. 하지만 **박을 가르고 나자** 그 안에서는 괴물과 벌이 튀어나와 놀부는 크게 혼쭐이 났어요.",
    "흥부는 **자신의 집**에서 아내와 아이들과 함께 가난하게 살고 있었어요. 어느 날, **집 앞 마당**에서 다친 제비를 발견하고 정성껏 치료해 주었죠. 그 후 제비가 물어다 준 박씨를 받아 **집 근처 밭에** 심었고, 시간이 지나 박을 따 보니 그 속에는 금은보화가 가득 들어 있었어요. 이 소식을 들은 놀부는 **흥부의 집**을 찾아가 어떤 일이 있었는지 듣고 그대로 따라 하기로 해요.**자기 집 마당**에 박씨를 심고 박이 자라자 자르는데, 그 속에서 괴물이 튀어나와 **집 안이** 엉망이 되어 버렸어요.결국 놀부는 **자신의 집**에서 큰 혼쭐이 나고, 스스로의 잘못을 깨닫게 되었답니다.",
    "**발단:** 흥부와 놀부는 성격이 매우 달랐고, 놀부는 흥부를 집에서 내쫓았어요.\n\n**전개:** 흥부는 다친 제비를 치료해 주고, 제비는 박씨를 물어다 주었어요.\n\n**위기:** 박 속에서 금은보화가 나와 흥부는 부자가 되었고, 놀부는 이를 보고 흉내를 냈어요.\n\n**절정:** 놀부는 일부러 제비를 다치게 해 박씨를 얻었지만, 박 속에서는 괴물과 벌이 나왔어요.\n\n**결말:** 놀부는 벌을 받고 자신의 잘못을 뉘우쳤으며, 형제는 다시 화해하게 되었어요.",
    "**누가:** 흥부와 놀부 형제가\n\n**언제:** 옛날에\n\n**어디서:** 같은 마을에서 살았어요.\n\n**무엇을:** 흥부는 제비를 도와 박씨를 얻고 부자가 되었고, 놀부는 그걸 따라 하다가 벌을 받았어요.\n\n**어떻게:** 흥부는 착하게 행동했고, 놀부는 욕심을 부렸어요.\n\n**왜:** 흥부는 제비를 진심으로 도와주었고, 놀부는 부자가 되고 싶은 마음에 따라 했기 때문이에요.",
    "**흥부**는 가난했지만 마음이 착해 다친 **제비**를 정성껏 돌봐 주었어요. 제비가 가져온 박씨를 심었더니, 박 속에서 금은보화가 나와 큰 부자가 되었어요. \n\n**놀부**는 그 이야기를 듣고 흥부를 따라 했지만, 욕심을 부려 제비를 일부러 다치게 했어요. 결국 놀부가 키운 박에서는 괴물과 벌이 나왔고, 놀부는 크게 혼이 났어요. 그 일로 놀부는 자신의 잘못을 깨닫고 흥부와 화해하게 되었어요."
    ]

# --- Initialize Session State ---
if 'stage' not in st.session_state:
    st.session_state.stage = "init"
    
if 'recommend_phase' not in st.session_state:
    st.session_state.recommend_phase = False

# --- UI Flow ---
if st.session_state.stage == "init":
    st.title("🖋️ 인터랙티브 스토리로 만드는 나만의 이야기")
    st.write("이야기를 쓰기 전에, 앞에서 어떤 일이 있었는지 요약해서 써 보세요. 아래 예시를 참고해도 좋아요!")

    # ─── 중앙에 입력창 + 버튼 ───────────────────────
    c1, c2, c3 = st.columns([1, 8, 1])
    with c2:
        summary_input = st.text_area("이야기 요약 입력", height=100, width=4000)

        def _on_start():
            # 1) 빈 입력 체크
            if not summary_input.strip():
                st.error("이야기를 입력해주세요.")
                return

            # 2) 욕설 검출
            if contains_profanity(summary_input):
                st.error("비속어가 포함되지 않은 이야기를 작성해주세요.")
                return

            # 3) 길이 체크
            if not is_story_related(summary_input):
                st.error("최소 20자 이상의 이야기 요약을 입력해주세요.")
                return

            # 모두 통과 시 시작
            with st.spinner("질문 생성 중... 잠시만 기다려주세요…"):
                handle_start(summary_input.strip())

        btn_l, btn_c, btn_r = st.columns([5, 2, 5])
        with btn_c:
            st.button("시작하기", on_click=_on_start)
    
    


    # ─── 상단에 5가지 예시 칸 ─────────────────────────
    example_cols = st.columns(5)
    for i, col in enumerate(example_cols, start=0):
        col.markdown(f" {example_title[i]} \n\n{examples[i]}")
    st.markdown("---")
    # ────────────────────────────────────────────────

elif st.session_state.stage == "choose_q":
    st.subheader("📖 지금까지 이야기")
    st.text_area("", value=st.session_state.current_segment or "이야기가 아직 없습니다.", height=200,disabled=True)
    st.subheader("다음 전개를 이어갈 질문을 골라주세요:")
    for i, q in enumerate(st.session_state.questions):
        st.button(q, key=f"q{i}", on_click=lambda i=i: choose_question(i))

elif st.session_state.stage == "write":
    idx = st.session_state.selected_q_idx
    st.subheader(f"📖 지금까지 이야기")
    st.text_area("", value=st.session_state.current_segment or "이야기가 아직 없습니다.", height=200,disabled=True)
    st.subheader(f"질문: {st.session_state.questions[idx]}")
    user_text = st.text_area(
        "답변 입력",
        value=st.session_state.raw_inputs[idx],
        height=200
    )
    st.button(
        "답변을 완성했어요.",
        on_click=lambda t=user_text: _on_raw_submit_with_spinner(t)
    )

elif st.session_state.stage == "review":
    idx = st.session_state.selected_q_idx

    # 1) edit_mode, fb_needs_update 초기화
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False
    if "fb_needs_update" not in st.session_state:
        st.session_state.fb_needs_update = True

    # 2) 피드백 생성 (최초 진입 또는 재제출 때만)
    if st.session_state.fb_needs_update:
        with st.spinner("피드백 생성 중... 잠시만 기다려주세요…"):
            fb = generate_feedback(
                st.session_state.raw_inputs[idx],
                st.session_state.current_segment
            )
        st.session_state.fb = fb
        st.session_state.fb_needs_update = False
    else:
        fb = st.session_state.fb

    # 3) 피드백 출력
       
    st.markdown("**🟢 잘한 부분:**")
    for good in fb.get("positives", []):
        st.markdown(f"- {good}")
    
    st.markdown("**❌ 다시 생각해 볼 부분:**")
    for err in fb.get("errors", []):
        st.markdown(f"- {err}")

    st.markdown("**💡 이렇게 바꿔보면 어때요?**")
    for sug in fb.get("suggestions", []):
        st.markdown(f"- {sug}")

    st.markdown("**✨ 추천 예시:**")
    st.markdown(f"> {fb.get('improved','').replace(chr(10), ' ')}")
    
    st.subheader(f"📖 지금까지 이야기")
    st.text_area("", value=st.session_state.current_segment or "이야기가 아직 없습니다.", height=200,disabled=True)
 

    # 4) edit_text 초기화
    if "edit_text" not in st.session_state:
        st.session_state.edit_text = st.session_state.raw_inputs[idx]

    st.subheader("✏️ 작성한 이야기")
    st.text_area(
        "",                # 라벨 텍스트
        key="edit_text",   # value= 절대 쓰지 않습니다
        height=200,
        disabled=not st.session_state.edit_mode
    )

    if not st.session_state.edit_mode:
        # “추천 예시” 누른 직후라면
        if st.session_state.recommend_phase:
            col1, col2 = st.columns(2)
            with col1:
                st.button(
                    "✏️ 조금 더 고쳐볼래요",
                    on_click=lambda: (
                        st.session_state.__setitem__('recommend_phase', False),
                        st.session_state.__setitem__('edit_mode', True)
                    )
                )
            with col2:
                st.button(
                    "✅ 이대로 사용할게요",
                    on_click=_on_accept_improved
                )
        # 아직 “추천 예시” 전이라면 (기존 3버튼)
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.button(
                    "✏️ 답변을 고칠래요.",
                    on_click=lambda: st.session_state.__setitem__("edit_mode", True)
                )
            with col2:
                st.button(
                    "✅ 답변을 완성했어요.",
                    on_click=lambda: on_feedback_decision(True)
                )
            with col3:

                st.button(
                    "👍 추천 예시를 사용할래요.",
                    on_click=_on_apply_improved
                )
    else:
        # ─── 수정 모드 ───
        def _on_edit_submit():
            new_text = st.session_state.edit_text

            # 1) 빈 입력
            if not new_text.strip():
                st.error("답변을 입력해주세요.")
                return
            # 2) 욕설 검출
            if contains_profanity(new_text):
                st.error("비속어가 포함되지 않은 답변을 작성해주세요.")
                return
            # 3) 길이 체크
            if not is_story_related(new_text):
                st.error("최소 20자 이상의 답변을 입력해주세요.")
                return

            # 통과 시 한 번 클릭으로 처리
            with st.spinner("피드백 생성 중... 잠시만 기다려주세요…"):
                st.session_state.raw_inputs[idx] = new_text
                st.session_state.fb_needs_update = True
                st.session_state.edit_mode = False

        # on_click에 콜백만 연결하면 single-click 동작
        st.button("수정을 완료했어요.", on_click=_on_edit_submit)

elif st.session_state.stage == "decide_continue":
    st.subheader("📖 지금까지 이어진 이야기")
    st.text_area("", value=st.session_state.current_segment, height=300,disabled=True)
    st.subheader("이야기를 계속 이어쓰시겠습니까?")
    col1, col2 = st.columns(2)
    with col1:
        st.button("계속 이어쓰기", on_click=lambda: decide_continue(True))
    with col2:
        st.button("이야기 완성하기", on_click=lambda: decide_continue(False))

elif st.session_state.stage == "done":
    st.subheader("✅ 최종 완성된 이야기")
    st.text_area("Story", value=st.session_state.current_segment, height=400,disabled=True)
    # 2-1. 처음 진입 시 한 번만 교정된 이야기 받아오기
    if "refined_story" not in st.session_state:
        with st.spinner("최종 이야기를 다듬는 중… 잠시만 기다려주세요"):
            refined = refine_story_to_childrens_book(st.session_state.current_segment)
            # session_state 에 저장하고, 이후 스토리북에도 이 버전을 사용
            st.session_state.refined_story = refined
            st.session_state.current_segment = refined

    # 2-2. 다듬어진 이야기 보여주기
    st.subheader("✅ 최종 완성된 이야기")
    st.text_area("Story", value=st.session_state.refined_story, height=400,disabled=True)
    st.success("이야기가 완성되었습니다! 복사하여 사용하세요.")
