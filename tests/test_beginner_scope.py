"""초보자 범위 분류(티켓 30): 쪽 목록, 바로 넣는 쪽, 분류하기, 비용 추정.

모델은 늘 가짜를 끼운다(돈이 드는 실제 호출은 시험하지 않는다). 청크·쪽·연습 과정은 모두 지어낸 것이다(설명서 원문 아님).
"""

import json

import pytest

from blender_tutor.beginner_scope import (
    OUTPUT_TOKENS_PER_PAGE,
    ClassifyError,
    Estimate,
    Label,
    Page,
    classify,
    estimate,
    fixed_labels,
    pages_of,
)
from blender_tutor.manual_chunks import Chunk
from blender_tutor.progress import Course, Step


def chunk(page_path: str, title: str, headings: tuple[str, ...], body: str) -> Chunk:
    return Chunk(page_path, "a", page_path.split("/")[0], page_path.rsplit("/", 1)[0], title, headings, body)


def test_청크를_쪽마다_묶고_첫_소제목_이름과_첫머리_40단어를_둔다():
    words = " ".join(f"w{i}" for i in range(50))
    chunks = [
        chunk("modeling/bevel", "Bevel", (), words),
        chunk("modeling/bevel", "Bevel", ("Options",), "x"),
        chunk("modeling/bevel", "Bevel", ("Options", "Width"), "y"),
        chunk("modeling/bevel", "Bevel", ("Example",), "z"),
        chunk("render/eevee", "EEVEE", ("Intro",), "Fast renderer."),
    ]
    bevel, eevee = pages_of(chunks)
    assert (bevel.path, bevel.field, bevel.title) == ("modeling/bevel", "modeling", "Bevel")
    assert bevel.headings == ("Options", "Example")
    assert bevel.intro == " ".join(f"w{i}" for i in range(40))
    assert (eevee.path, eevee.headings, eevee.intro) == ("render/eevee", ("Intro",), "Fast renderer.")


def page(path: str) -> Page:
    return Page(path, path.split("/")[0], path.rsplit("/", 1)[-1], (), "")


def test_연습_과정이_가리키는_쪽과_시작하기_쪽은_이유와_함께_바로_넣는다():
    pages = [page(p) for p in ("getting_started/help", "modeling/bevel", "modeling/array", "render/eevee", "editors/view")]
    sword = Course("sword", "단순한 검", (
        Step("view", "화면 돌려 보기", manual=("editors/view.html#orbit", "editors/view.html#zoom")),
        Step("bevel", "모서리 다듬기", manual=("modeling/bevel.html#bevel-modifier",)),
    ))
    assert fixed_labels(pages, [sword]) == [
        Label("getting_started/help", True, "시작하기 쪽"),
        Label("modeling/bevel", True, "연습 과정 '단순한 검'의 단계 '모서리 다듬기'가 가리킴"),
        Label("editors/view", True, "연습 과정 '단순한 검'의 단계 '화면 돌려 보기'가 가리킴"),
    ]


class FakeModel:
    """물음에 든 쪽 경로를 찾아, answers[경로](넣음, 이유)대로 JSON 답을 짓는다. 받은 물음을 모두 적어 둔다."""

    def __init__(self, answers: dict[str, tuple[bool, str]]):
        self.answers = answers
        self.asked: list[list[str]] = []  # 물음마다 거기 든 쪽 경로

    def ask(self, messages: list[dict[str, str]]) -> str:
        content = messages[-1]["content"]
        paths = [path for path in self.answers if f'"{path}"' in content]
        self.asked.append(paths)
        return json.dumps({"pages": [{"path": p, "include": self.answers[p][0], "reason": self.answers[p][1]} for p in paths]})


PATHS = ("modeling/array", "render/eevee", "physics/fluid", "modeling/uv")
ANSWERS = {"modeling/array": (True, "반복 모양에 자주 씀"), "render/eevee": (True, "미리 보기 렌더"),
           "physics/fluid": (False, "물리 시뮬레이션"), "modeling/uv": (False, "텍스처 단계")}


def test_쪽을_묶음으로_물어_받은_분류를_쪽_차례로_돌려주고_파일에도_남긴다(tmp_path):
    model, out = FakeModel(ANSWERS), tmp_path / "labels.jsonl"
    labels = classify([page(p) for p in PATHS], model, out, batch=3)
    assert model.asked == [list(PATHS[:3]), [PATHS[3]]]
    assert labels == [Label(p, *ANSWERS[p]) for p in PATHS]
    saved = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert saved == [{"path": p, "include": ANSWERS[p][0], "reason": ANSWERS[p][1]} for p in PATHS]


def test_파일에_이미_받은_쪽은_다시_묻지_않는다(tmp_path):
    out = tmp_path / "labels.jsonl"
    classify([page(p) for p in PATHS[:2]], FakeModel(ANSWERS), out, batch=3)
    model = FakeModel(ANSWERS)
    labels = classify([page(p) for p in PATHS], model, out, batch=3)
    assert model.asked == [list(PATHS[2:])]
    assert labels == [Label(p, *ANSWERS[p]) for p in PATHS]
    assert len(out.read_text(encoding="utf-8").splitlines()) == 4


class ScriptedModel(FakeModel):
    """물음마다 replies의 다음 글을 그대로 돌려준다(차례가 다하면 FakeModel처럼 바르게 답한다)."""

    def __init__(self, replies: list[str]):
        super().__init__(ANSWERS)
        self.replies = replies

    def ask(self, messages: list[dict[str, str]]) -> str:
        right = super().ask(messages)
        return self.replies.pop(0) if self.replies else right


def reply(*rows: tuple[str, object, object]) -> str:
    return json.dumps({"pages": [{"path": p, "include": i, "reason": r} for p, i, r in rows]})


def test_빠지거나_이유가_비거나_모르는_쪽은_버리고_그_쪽만_한_번_다시_묻는다(tmp_path):
    model = ScriptedModel([reply(("modeling/array", True, "반복"), ("render/eevee", True, " "), ("other/page", True, "모름"))])
    labels = classify([page(p) for p in PATHS[:3]], model, tmp_path / "labels.jsonl", batch=3)
    assert model.asked == [list(PATHS[:3]), list(PATHS[1:3])]
    assert labels == [Label("modeling/array", True, "반복"), Label("render/eevee", *ANSWERS["render/eevee"]),
                      Label("physics/fluid", *ANSWERS["physics/fluid"])]


def test_다시_물어도_안_되면_받은_것은_남기고_못_받은_쪽을_알리며_멈춘다(tmp_path):
    out = tmp_path / "labels.jsonl"
    model = ScriptedModel(["깨진 답", "깨진 답"])
    with pytest.raises(ClassifyError) as error:
        classify([page(p) for p in PATHS], model, out, batch=2)
    assert error.value.paths == list(PATHS[:2])
    assert model.asked == [list(PATHS[:2]), list(PATHS[:2])]
    assert out.is_file() is False or out.read_text(encoding="utf-8") == ""


def test_한_답에_같은_쪽이_두_번_나오면_그_쪽은_믿지_않고_다시_묻는다(tmp_path):
    model = ScriptedModel([reply(("modeling/array", True, "반복"), ("modeling/array", False, "아님"), ("render/eevee", True, "미리 보기"))])
    labels = classify([page(p) for p in PATHS[:2]], model, tmp_path / "labels.jsonl", batch=2)
    assert model.asked == [list(PATHS[:2]), [PATHS[0]]]
    assert labels == [Label("modeling/array", *ANSWERS["modeling/array"]), Label("render/eevee", True, "미리 보기")]


def test_비용_추정은_실제로_보낼_물음_수와_글_양을_센다():
    small = estimate([page(p) for p in PATHS], batch=3)
    assert small.requests == 2
    assert small.output_tokens == 4 * OUTPUT_TOKENS_PER_PAGE
    long_intro = Page("modeling/array", "modeling", "Array", (), "word " * 4000)  # 2만 글자
    assert estimate([long_intro], batch=3).input_tokens > small.input_tokens + 4000


def test_금액은_백만_토큰당_값으로_셈한다():
    assert Estimate(requests=2, input_tokens=1_000_000, output_tokens=500_000).dollars(0.2, 1.0) == pytest.approx(0.7)
