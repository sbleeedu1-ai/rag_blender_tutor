"""검 검수 회귀 테스트(티켓 32): 사용자가 Blender 5.2에서 검을 따라 할 때 실제로 받은 작업 상태를 저장소의 검 연습 과정에 다시 넣는다.

흐름 파일 전체를 다시 돌리면 검수 뒤 바뀐 조작 수만큼 버튼 누름이 엉뚱한 조작을 넘겨 뜻이 없어진다. 그래서 검수에서
문제가 된 조작을 안내하던 동안의 작업 상태만 잘라(tests/fixtures/sword_review_20261102.json) 그 조작의 감지만 본다.
"""

import json
from pathlib import Path

from blender_tutor.progress import Progress, load_steps
from blender_tutor.work_state import WorkState

HERE = Path(__file__).resolve().parent
SEGMENTS = json.loads((HERE / "fixtures" / "sword_review_20261102.json").read_text(encoding="utf-8"))["구간"]
STEPS = load_steps(HERE.parent / "courses" / "sword.yaml")


def at_operation(label: str, description: str) -> tuple[Progress, list[tuple[int, WorkState]]]:
    """그 단계의 그 조작을 안내하기 시작한 진행과, 그 뒤 받은 (흐름 파일 줄 번호, 작업 상태)."""
    index = next(i for i, step in enumerate(STEPS) if step.label == label)
    operation = next(i for i, each in enumerate(STEPS[index].operations) if each.description == description)
    first, *rest = [(entry["줄"], WorkState.from_json(entry["상태"])) for entry in SEGMENTS[label]]
    return Progress(STEPS, start=index, operations_done=operation, latest=first[1]), rest


def done_at(progress: Progress, states: list[tuple[int, WorkState]]) -> int | None:
    """감지로 다음 조작으로 넘어간 흐름 파일 줄 번호(끝까지 안 넘어가면 None)."""
    before = progress.operations_done
    for line, state in states:
        progress.on_state(state)
        if progress.operations_done > before:
            return line
    return None


def test_코등이는_S로_전체를_줄였을_때는_넘어가지_않고_앞뒤_위아래만_줄였을_때_넘어간다():
    # 236번째 줄: S만 눌러 세 방향을 함께 줄임(0.22, 0.22, 0.22). 고치기 전에는 여기서 넘어갔다
    # 289번째 줄: 되돌리고 다시 더한 정육면체를 S Y로 조금, S Z로 많이 줄임(1.0, 0.96, 0.03). 얼마나 줄였는지는 보지 않는다
    progress, states = at_operation("guard-add", "앞뒤·위아래만 줄이기(S 다음 Y, S 다음 Z)")
    assert done_at(progress, states) == 289


def test_손잡이는_칼날을_올려_둔_뒤_위로_옮겨도_넘어간다():
    # 5단계 끝에 칼날·코등이를 함께 위로 올려(코등이 z -1.01 → 0.76), 손잡이도 z 0 → 0.26으로 올림
    progress, states = at_operation("grip-add", "옮기기")
    assert done_at(progress, states) == 376


def test_끝장식도_위로_옮겨도_넘어간다():
    progress, states = at_operation("pommel-add", "옮기기")
    assert done_at(progress, states) == 505
