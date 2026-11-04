"""답 엔진 만들기: 도우미 창과 평가 프로그램이 같은 엔진을 쓰게 한곳에서 부품을 끼운다(티켓 33, 이전 stand_in.build_engine).

부품: 미리 만든 설명서 벡터 + 질문마다 OpenAI 임베딩(티켓 31), luna 질문 바꾸기 3개(흘려 받아 검색어가 먼저 닫힌 1개, 티켓 43·44),
진짜 답변 모델(answer_model, 생각 수준은 Settings.reasoning). 모두 돈이 든다(질문마다 아주 조금).
엔진 이름은 "임베딩+질문 바꾸기+답변"(예: text-embedding-3-large+gpt-6-luna×3+gpt-6-luna)으로 시간 기록·평가 결과에 남는다.
"""

from collections.abc import Sequence
from pathlib import Path

from blender_tutor import answer_model, manual_vectors
from blender_tutor.answer_engine import AnswerEngine, Rewriter, Settings
from blender_tutor.answer_model import OpenAIAnswerModel
from blender_tutor.beginner_scope import OpenAIModel, openai_key
from blender_tutor.manual_chunks import load_chunks
from blender_tutor.menu_names import load_menu_names
from blender_tutor.paths import MENU_CHOICES, MENU_TITLES
from blender_tutor.progress import Course

EMBEDDINGS = (manual_vectors.MODEL,)  # 고를 수 있는 임베딩(bge-m3는 생기는 티켓에서 더한다)
REWRITE_MODEL, REWRITE_EFFORT, REWRITE_COUNT = "gpt-6-luna", "none", 3  # 질문 바꾸기(HISTORY [127], 질문마다 약 $0.00025. 5개는 이득이 작아 되돌림, [135])


def answer_model_for(settings: Settings) -> OpenAIAnswerModel:
    """진짜 답변 모델을 settings.reasoning 생각 수준으로 만든다(만드는 곳은 여기 하나). 키가 없으면 SystemExit.
    2개를 동시에 보내 먼저 온 것을 쓰는 방법은 이득이 작아 되돌렸다(HISTORY [135])."""
    return OpenAIAnswerModel(answer_model.MODEL, openai_key(), settings.reasoning.value)


def rewriters_for(settings: Settings, key: str) -> list[OpenAIModel]:
    """질문 바꾸기 모델 REWRITE_COUNT개. 동시에 부르므로 하나씩 따로 둔다(받은 토큰 수를 셀 때 서로 덮어쓰지 않게)."""
    return [OpenAIModel(REWRITE_MODEL, key, REWRITE_EFFORT, settings.rewrite_timeout) for _ in range(REWRITE_COUNT)]


def build_engine(
    data_dir: Path,
    model: OpenAIAnswerModel | None = None,
    menu_choices: Path = MENU_CHOICES,
    menu_titles: Path = MENU_TITLES,
    courses: Sequence[Course] = (),
    settings: Settings = Settings(),
    embedding: str = manual_vectors.MODEL,
    rewriters: Sequence[Rewriter] | None = None,
) -> AnswerEngine:
    """data_dir(보통 data/)의 청크·설명서 벡터·메뉴 이름 사전으로 엔진을 만든다.

    청크 파일이나 설명서 벡터 파일이 없으면 FileNotFoundError, 벡터가 청크와 다르면 ValueError, OpenAI 키가 없으면 SystemExit.
    메뉴 이름 사전이 없으면 메뉴 이름을 영어 그대로 보인다. courses는 연습 과정 밖 질문에 권할 연습 과정이고,
    벡터는 이름 + 한 줄 설명 + 비슷한 말(Course.search_text)로 만들어 data_dir/vectors/에 저장해 두고 바뀐 것만 다시 만든다(HISTORY [109]).
    model을 주지 않으면 answer_model_for(settings)로 만든다. 평가 프로그램은 요금을 세려고 같은 함수로 만들어 넘긴다.
    엔진 이름의 답변 칸은 끼운 모델의 이름(model.model)이다. rewriters도 주면 그것을 쓴다(실측 프로그램이 호출마다 시각을 재려고 감싼 것).
    """
    if embedding not in EMBEDDINGS:
        raise ValueError(f"모르는 임베딩 {embedding} (고를 수 있는 것: {', '.join(EMBEDDINGS)})")
    chunks = load_chunks(data_dir / "chunks" / "manual_chunks.jsonl")
    vectors = manual_vectors.load(manual_vectors.path_for(embedding, data_dir), chunks)
    key = openai_key()
    embedder = manual_vectors.OpenAIEmbedder(embedding, key)
    rewriters = list(rewriters or rewriters_for(settings, key))
    model = model or answer_model_for(settings)
    names = load_menu_names(data_dir, menu_choices, menu_titles)
    texts = [course.search_text for course in courses]
    course_vectors = manual_vectors.cached(texts, embedder, manual_vectors.courses_path_for(embedding, data_dir), settings.timeout)
    name = f"{embedding}+{REWRITE_MODEL}×{len(rewriters)}+{model.model}"
    return AnswerEngine(
        chunks, vectors, embedder, model, settings=settings,
        menu_names=names, courses=courses, course_vectors=course_vectors, name=name, rewriters=rewriters,
    )
