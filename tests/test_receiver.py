"""받는 쪽(도우미 프로그램이 애드온의 작업 상태를 받는 곳).

애드온인 척 내 PC 안 HTTP로 보내고, 창 번호별 최신 상태·건네받은 알림·끝나는 때를 본다.
"Blender가 아직 켜져 있나"는 가짜(살아 있는 프로세스 번호 집합)로 바꿔 끼운다.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from blender_tutor.receiver import FileEvent, Message, Receiver
from blender_tutor.work_state import WorkState
from tests.test_work_state import EDITING

TOKEN = "test-token"
OBJECT_MODE = {**EDITING, "mode": "OBJECT", "edit_selected": {}}


@pytest.fixture
def alive():
    return {100, 200}  # 켜져 있는 Blender 프로세스 번호


@pytest.fixture
def received():
    return []


@pytest.fixture
def receiver(alive, received):
    with Receiver(TOKEN, received.append, is_alive=lambda pid: pid in alive, port=0) as receiver:
        yield receiver


def send(receiver, window, pid, state=EDITING, *, summon=False, event=None, token=TOKEN, path="/state", body=None) -> int:
    """애드온처럼 보내고 응답 번호를 돌려준다."""
    if body is None:
        body = {"window": window, "pid": pid, "state": state, "summon": summon, "event": event}
    request = urllib.request.Request(
        f"http://127.0.0.1:{receiver.port}{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Tutor-Token": token},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def test_창_번호마다_최신_상태_하나를_든다(receiver):
    send(receiver, 1, 100, EDITING)
    send(receiver, 2, 200, OBJECT_MODE)
    send(receiver, 1, 100, OBJECT_MODE)
    assert receiver.latest(1) == WorkState.from_json(OBJECT_MODE)
    assert receiver.latest(2) == WorkState.from_json(OBJECT_MODE)
    assert receiver.latest(3) is None


def test_받은_것을_부르기와_파일_사건과_함께_건넨다(receiver, received):
    send(receiver, 1, 100, summon=True)
    send(receiver, 1, 100, event={"kind": "saved", "path": "C:/work/sword.blend"})
    state = WorkState.from_json(EDITING)
    assert received == [
        Message(1, 100, state, summon=True),
        Message(1, 100, state, event=FileEvent("saved", "C:/work/sword.blend")),
    ]


def test_닫힌_Blender의_상태는_버린다(receiver, alive):
    send(receiver, 1, 100)
    send(receiver, 2, 200)
    alive.discard(100)
    receiver.forget_closed()
    assert receiver.latest(1) is None
    assert receiver.latest(2) is not None


def test_마지막_Blender가_닫히면_끝난다(receiver, alive):
    send(receiver, 1, 100)
    done = threading.Thread(target=receiver.run_until_no_blender, kwargs={"check_every": 0.01, "grace": 60})
    done.start()
    done.join(0.2)
    assert done.is_alive()  # Blender가 켜져 있는 동안은 계속 돈다
    alive.clear()
    done.join(5)
    assert not done.is_alive()


def test_Blender가_한_번도_보내지_않으면_기다린_뒤_끝난다(receiver):
    done = threading.Thread(target=receiver.run_until_no_blender, kwargs={"check_every": 0.01, "grace": 0.1})
    done.start()
    done.join(5)
    assert not done.is_alive()


def test_비밀_글자가_틀리면_받지_않는다(receiver, received):
    assert send(receiver, 1, 100, token="wrong") == 403
    assert receiver.latest(1) is None and received == []


@pytest.mark.parametrize(
    "body",
    [
        {"window": 1, "pid": 100, "state": {"mode": "OBJECT"}, "summon": False, "event": None},  # 칸이 빠진 작업 상태
        {"window": "1", "pid": 100, "state": EDITING, "summon": False, "event": None},  # 창 번호가 글자
        {"window": 1, "pid": 100, "state": EDITING, "summon": False, "event": {"kind": "deleted", "path": ""}},  # 모르는 사건
    ],
)
def test_모양이_틀린_것은_받지_않는다(receiver, received, body):
    assert send(receiver, 1, 100, body=body) == 400
    assert receiver.latest(1) is None and received == []


def test_애드온이_이미_켜진_도우미인지_물어볼_수_있다(receiver):
    request = urllib.request.Request(f"http://127.0.0.1:{receiver.port}/ping", headers={"X-Tutor-Token": TOKEN})
    with urllib.request.urlopen(request, timeout=5) as response:
        assert json.loads(response.read()) == {"app": "blender_tutor"}
