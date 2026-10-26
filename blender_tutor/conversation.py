"""대화: 도우미 창이 든 최근 대화와 답 엔진 부르기(명세 "도우미 창", 티켓 09·26).

최근 대화는 질문과 답 글만 최근 3쌍(근거 목록 뺌). Blender가 여럿이어도 하나이고, 도우미 프로그램이 꺼지면 사라진다.
답 엔진은 바깥 서비스 오류만 짧은 문구로 바꾸고 우리 코드의 버그는 그대로 올려 보낸다(티켓 21).
그런 버그는 여기서 한 번 받아 창이 꺼지지 않게 하고, 내용은 기록 파일에 남긴다.
"""

import dataclasses
import logging
from collections import deque
from collections.abc import Iterator

from blender_tutor.answer_engine import AnswerEngine, Done, Event, Failure, Piece, Settings
from blender_tutor.progress import Step
from blender_tutor.work_state import WorkState

RECENT_PAIRS = 3  # 명세 "최근 대화". 평가에서 바꿔 볼 수 있는 설정값(User Story 72)
PROGRAM_ERROR = "도우미 프로그램에 문제가 생겼어요. 다시 물어봐도 같으면 도우미를 끝냈다가 F10으로 다시 켜 주세요."
NOT_READY = "도우미가 설명서를 읽는 중이에요. 몇 초 뒤 다시 물어봐 주세요."

log = logging.getLogger(__name__)


def settings_record(settings: Settings, recent_pairs: int) -> dict:
    """기록에 남기는 설정: 답 엔진 설정 + 최근 대화 쌍 수. 시간 기록 줄(helper)과 평가 결과의 설정.json(evaluate)이
    이 모양 하나를 함께 써서 "같은 설정으로 잰 것"을 맞대 볼 수 있다(티켓 29). 설정이 늘면 여기만 고친다."""
    return {**dataclasses.asdict(settings), "recent_pairs": recent_pairs}


class Conversation:
    """최근 대화를 들고 질문마다 답 엔진을 부른다. engine이 없으면(준비 중·자료 없음) waiting_message를 낸다."""

    def __init__(self, keep: int = RECENT_PAIRS):
        self.engine: AnswerEngine | None = None
        self.waiting_message = NOT_READY
        self._recent: deque[tuple[str, str]] = deque(maxlen=keep)

    @property
    def recent_pairs(self) -> int:
        """답 엔진에 넘기는 최근 대화 쌍 수(시간 기록에 설정으로 남긴다)."""
        return self._recent.maxlen

    def ask(self, question: str, state: WorkState, step: Step | None = None) -> Iterator[Event]:
        """질문을 엔진에 넘기고 나온 사건을 그대로 낸다. 끝까지 나온 답만 최근 대화에 넣는다.

        step은 질문한 Blender의 지금 단계(연습 과정 밖이면 None). 진행은 바꾸지 않아 답 뒤에도 같은 단계다.
        """
        if self.engine is None:
            yield Failure(self.waiting_message)
            return
        answer = []
        try:
            for event in self.engine.answer(question, state, list(self._recent), step):
                if isinstance(event, Piece):
                    answer.append(event.text)
                elif isinstance(event, Done):
                    self._recent.append((question, "".join(answer)))
                yield event
        except Exception:
            log.exception("답을 만들다 도우미 프로그램 버그: %s", question)
            yield Failure(PROGRAM_ERROR)
