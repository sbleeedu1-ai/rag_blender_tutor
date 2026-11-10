"""엔진 만들기(티켓 26·31·33): 만들어 둔 설명서 벡터를 읽고, 질문 바꾸기·임베딩·답변 모델을 끼운다. OpenAI는 모두 가짜(돈이 들지 않음)."""

import pytest

from blender_tutor import engine_setup, manual_vectors
from blender_tutor.answer_engine import Done, Piece, Settings
from blender_tutor.engine_setup import build_engine
from blender_tutor.manual_chunks import Chunk, save_chunks
from blender_tutor.progress import Course, Step
from blender_tutor.work_state import WorkState
from tests.examples import EDITING

BEVEL = Chunk("modeling/bevel", "options", "modeling", "modeling", "Bevel", ("Options",), "Width sets the size.")
ARRAY = Chunk("modeling/array", "intro", "modeling", "modeling", "Array", ("Introduction",), "Array copies the object.")


class QuestionEmbedder:
    """진짜 OpenAI 임베딩 대신: 받은 글을 적어 두고 [1, 0]을 돌려준다(BEVEL 쪽 벡터)."""

    def __init__(self, model, key):
        self.texts = []

    def embed(self, texts, timeout):
        self.texts += texts
        return [[1.0, 0.0] for _ in texts]


class Rewriter:  # luna 질문 바꾸기 대신
    def __init__(self, model, key, effort, timeout):
        self.settings = (model, effort, timeout)

    def stream(self, messages):
        yield '{"query": "bevel width"}'


class AnswerModel:  # 진짜 답변 모델 대신: 만들 때 받은 값과 받은 대화 글을 적어 둔다
    def __init__(self, model, key, effort):
        self.model = model
        self.settings = (model, effort)
        self.sent = []

    def stream(self, messages, timeout):
        self.sent.append(messages)
        yield "답"


class Claude:  # Claude 모델 대신: 만들 때 받은 값을 적고, 질문 바꾸기·분야 고르기·답변을 흉내 낸다
    def __init__(self, model, key, reasoning="none", max_tokens=4096, timeout=10.0, schema=None):
        self.model, self.settings, self.sent = model, (reasoning, max_tokens, timeout, schema is not None), []

    def stream(self, messages, timeout=None):
        self.sent.append(messages)
        yield '{"query": "bevel width", "areas": [], "exclude": []}' if self.settings[3] else "답"

    def ask_json(self, messages, schema, timeout=None):
        self.sent.append(messages)
        return {"분야": ["MO"]}


@pytest.fixture
def fakes(tmp_path, monkeypatch):
    """청크 둘(array는 [0, 1], bevel은 [1, 0] 벡터)과 가짜 OpenAI 부품. 만들어진 부품을 종류별로 모은다."""
    save_chunks([ARRAY, BEVEL], tmp_path / "chunks" / "manual_chunks.jsonl")

    class Stored:  # 미리 만든 벡터 파일
        def embed(self, texts, timeout):
            return [[0.0, 1.0], [1.0, 0.0]]

    manual_vectors.build([ARRAY, BEVEL], Stored(), manual_vectors.path_for("text-embedding-3-large", tmp_path), "fake")
    made = {"embedder": [], "rewriter": [], "model": [], "claude": []}

    def keep(kind, cls):
        return lambda *args: made[kind].append(cls(*args)) or made[kind][-1]

    monkeypatch.setattr(engine_setup, "openai_key", lambda: "가짜 키")
    monkeypatch.setattr(manual_vectors, "OpenAIEmbedder", keep("embedder", QuestionEmbedder))
    monkeypatch.setattr(engine_setup, "OpenAIModel", keep("rewriter", Rewriter))
    monkeypatch.setattr(engine_setup, "OpenAIAnswerModel", keep("model", AnswerModel))
    monkeypatch.setattr(engine_setup, "anthropic_key", lambda: "가짜 Anthropic 키")
    monkeypatch.setattr(engine_setup, "ClaudeModel", keep("claude", Claude))
    return made


def test_만들어_둔_설명서_벡터를_읽고_바꾼_검색어만_임베딩해_진짜_답변_모델로_답한다(tmp_path, fakes):
    engine = build_engine(tmp_path, settings=Settings(reasoning="low"), provider="openai")
    events = list(engine.answer("베벨 너비", WorkState.from_json(EDITING), []))
    assert "".join(event.text for event in events if isinstance(event, Piece)) == "답"
    assert isinstance(events[-1], Done)
    assert events[-1].sources[0].path == "Bevel > Options"  # 낱말이 하나도 안 겹쳐도 벡터로 찾는다
    assert fakes["embedder"][0].texts == ["bevel width"]  # 바꾼 검색어 하나만, 설명서는 다시 임베딩하지 않는다
    assert [rewriter.settings for rewriter in fakes["rewriter"]] == [("gpt-6-luna", "none", 5.0)] * 3
    assert fakes["model"][0].settings == ("gpt-6-luna", "low")  # 생각 수준은 설정 값 그대로
    assert engine.name == "text-embedding-3-large+gpt-6-luna×3+gpt-6-luna"


def test_답변_모델을_넘기면_그것을_쓴다(tmp_path, fakes):
    given = AnswerModel("넘긴 것", "", "none")
    engine = build_engine(tmp_path, model=given)
    list(engine.answer("베벨 너비", WorkState.from_json(EDITING), []))
    assert len(given.sent) == 1 and fakes["model"] == []
    assert engine.name.endswith("+넘긴 것")  # 엔진 이름은 실제로 끼운 답변 모델의 이름


def test_연습_과정은_이름_한_줄_설명_비슷한_말을_합친_글로_엔진을_만들_때_한_번_임베딩한다(tmp_path, fakes):
    sword = Course("sword", "단순한 검", (Step("view", "화면 돌려 보기"),), "정육면체로 검을 만든다.", ("장검", "blade"))
    engine = build_engine(tmp_path, courses=[sword], provider="openai")
    assert fakes["embedder"][0].texts == ["단순한 검 정육면체로 검을 만든다. 장검 blade"]
    list(engine.answer("활을 만들고 싶어요", WorkState.from_json(EDITING), []))
    assert "단순한 검: 정육면체로 검을 만든다." in str(fakes["model"][0].sent[0])  # 연습 과정 밖 질문에 비슷한 연습 과정이 붙는다


def test_설명서_벡터_파일이_없으면_FileNotFoundError(tmp_path):
    save_chunks([BEVEL], tmp_path / "chunks" / "manual_chunks.jsonl")
    with pytest.raises(FileNotFoundError):  # 도우미 창은 이것을 '설명서 자료가 없어요'로 보인다
        build_engine(tmp_path)


def test_모르는_임베딩은_고를_수_없다(tmp_path):
    with pytest.raises(ValueError, match="bge-m3"):
        build_engine(tmp_path, embedding="bge-m3")


def test_기본은_Claude로_질문_바꾸기_3개_분야_고르기_답변과_생각을_올린_예비_답변을_끼운다(tmp_path, fakes):
    from blender_tutor.setting_fields import SettingLines

    engine = build_engine(tmp_path, settings=Settings(reasoning="none", fallback_reasoning="low"))
    lines = SettingLines(("a = 1",), {"MO": ("b = 2",)})
    events = list(engine.answer("베벨 너비", WorkState.from_json(EDITING), [], settings=lines))
    made = [c.settings for c in fakes["claude"]]
    # 질문 바꾸기 3개(스키마 있음, 생각 끔) + 답변(생각 끔) + 분야 고르기(생각 끔, 200토큰) + 예비 답변(생각 low)
    assert made == [("none", 600, 5.0, True)] * 3 + [("none", 4096, 10.0, False), ("none", 200, 5.0, False), ("low", 4096, 10.0, False)]
    assert events[-1].fields == ("MO",) and "b = 2" in str(fakes["claude"][3].sent[0])
    assert engine.name == "text-embedding-3-large+claude-haiku-5-5×3+claude-haiku-5-5"
