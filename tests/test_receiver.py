"""받는 쪽(도우미 프로그램이 애드온의 작업 상태를 받는 곳).

애드온인 척 내 PC 안 HTTP로 보내고, 창 번호별 최신 상태·건네받은 알림·끝나는 때를 본다.
"Blender가 아직 켜져 있나"는 가짜(프로세스 번호 → 켜진 시각)로 바꿔 끼운다.
"""

import http.client
import json
import threading
import urllib.request

import pytest

from blender_tutor.receiver import TOKEN_HEADER, FileEvent, Message, Receiver
from blender_tutor.work_state import WorkState
from tests.examples import EDITING, TOKEN, send

OBJECT_MODE = {**EDITING, "mode": "OBJECT", "edit_selected": {}}


@pytest.fixture
def alive():
    return {100: 1.0, 200: 2.0}  # 켜져 있는 Blender 프로세스 번호 → 켜진 시각


@pytest.fixture
def received():
    return []


@pytest.fixture
def receiver(alive, received):
    with Receiver(TOKEN, received.append, process_started=alive.get, port=0) as receiver:
        yield receiver


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


def test_F10을_누른_시각을_함께_건넨다(receiver, received):
    send(receiver, 1, 100, summon=True, pressed=1792900000.25)  # 애드온이 F10을 받은 때의 time.time()
    assert received == [Message(1, 100, WorkState.from_json(EDITING), summon=True, pressed=1792900000.25)]


def test_닫힌_Blender의_상태는_버린다(receiver, alive):
    send(receiver, 1, 100)
    send(receiver, 2, 200)
    del alive[100]
    receiver.forget_closed()
    assert receiver.latest(1) is None
    assert receiver.latest(2) is not None


def test_켜진_Blender의_창_번호와_프로세스_번호를_알려_준다(receiver, alive):
    # 창이 "앞 프로그램이 Blender인가"를 가르고, 질문을 어느 Blender 상태로 보낼지 고를 때 쓴다
    send(receiver, 1, 100)
    send(receiver, 2, 200)
    assert receiver.blenders() == {1: 100, 2: 200}
    del alive[100]
    receiver.forget_closed()
    assert receiver.blenders() == {2: 200}


def test_프로세스_번호가_다른_프로그램에_다시_쓰이면_닫힌_것으로_본다(receiver, alive):
    send(receiver, 1, 100)
    alive[100] = 9.0  # Blender가 닫히고 같은 번호를 받은 다른 프로그램(켜진 시각이 다름)
    receiver.forget_closed()
    assert receiver.latest(1) is None


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
        {"window": 1, "pid": 100, "state": {"mode": "OBJECT"}, "summon": False, "event": None, "pressed": None, "settings": None},  # 칸이 빠진 작업 상태
        {"window": "1", "pid": 100, "state": EDITING, "summon": False, "event": None, "pressed": None, "settings": None},  # 창 번호가 글자
        {"window": 1, "pid": 100, "state": EDITING, "summon": False, "event": {"kind": "deleted", "path": ""}, "pressed": None, "settings": None},  # 모르는 사건
        {"window": 1, "pid": 100, "state": EDITING, "summon": True, "event": None, "pressed": "방금", "settings": None},  # 누른 시각이 글자
        {"window": 1, "pid": 100, "state": EDITING, "summon": True, "event": None},  # 누른 시각 칸이 없는 옛 애드온
        {"window": 1, "pid": 100, "state": EDITING, "summon": True, "event": None, "pressed": None},  # 설정 값 칸이 없는 옛 애드온
        {"window": 1, "pid": 100, "state": EDITING, "summon": False, "event": None, "pressed": None, "settings": {"always": "x", "fields": {}}},  # 설정 값 모양이 틀림
    ],
)
def test_모양이_틀린_것은_받지_않는다(receiver, received, body):
    assert send(receiver, 1, 100, body=body) == 400
    assert receiver.latest(1) is None and received == []


def test_모양이_틀린_봉투를_받은_적이_있는지_알려_준다(receiver):
    """설치 명령을 다시 돌리지 않은 옛 애드온의 봉투는 모두 거절된다. 도우미 창이 그때 '다시 설치' 안내를 보이려고 쓴다."""
    send(receiver, 1, 100)
    assert not receiver.rejected
    old_addon = {"window": 1, "pid": 100, "state": EDITING, "summon": True, "event": None}  # 누른 시각 칸이 없음
    assert send(receiver, 1, 100, body=old_addon) == 400
    assert receiver.rejected


def test_내용_길이가_음수면_기다리지_않고_돌려보낸다(receiver):
    connection = http.client.HTTPConnection("127.0.0.1", receiver.port, timeout=2)
    connection.putrequest("POST", "/state")
    connection.putheader(TOKEN_HEADER, TOKEN)
    connection.putheader("Content-Length", "-1")
    connection.endheaders()
    assert connection.getresponse().status == 400  # 2초 안에 대답하지 않으면 TimeoutError로 실패


def test_애드온이_이미_켜진_도우미인지_물어볼_수_있다(receiver):
    request = urllib.request.Request(f"http://127.0.0.1:{receiver.port}/ping", headers={TOKEN_HEADER: TOKEN})
    with urllib.request.urlopen(request, timeout=5) as response:
        assert json.loads(response.read()) == {"app": "blender_tutor"}


# 설정 값(HISTORY [270]): 도우미가 청하면 애드온은 다음 답장을 보고 작업 상태와 한 봉투로 보낸다

SETTINGS = {"always": ["bpy.context.object.location = (0, 0, 0)"], "situation": [], "computed": [], "fields": {"MO": ["bpy.context.object.modifiers['Bevel'].segments = 1"]}}


def wants(receiver, window):
    """애드온처럼 0.5초마다 묻는 것: 설정 값을 읽어 보낼까."""
    request = urllib.request.Request(f"http://127.0.0.1:{receiver.port}/wants?window={window}", headers={TOKEN_HEADER: TOKEN})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())["read_settings"]


def test_청한_뒤_애드온이_물으면_한_번만_읽어_달라고_답한다(receiver):
    send(receiver, 1, 100)
    assert wants(receiver, 1) is False
    receiver.want_settings()
    assert [wants(receiver, 1), wants(receiver, 1)] == [True, False]  # 한 번 알렸으면 다시 싣지 않는다(읽어 오는 중)


def test_지금_작업_상태에서_읽은_설정_값만_낸다(receiver):
    from blender_tutor.setting_fields import SettingLines

    send(receiver, 1, 100, EDITING, settings=SETTINGS)
    assert receiver.settings_for(1) == (WorkState.from_json(EDITING), SettingLines.from_json(SETTINGS))
    send(receiver, 1, 100, {**EDITING, "view": {**EDITING["view"], "distance": 3.0}})  # 화면만 돌렸으면 그대로 쓴다
    assert receiver.settings_for(1) is not None
    send(receiver, 1, 100, OBJECT_MODE)  # 상태가 바뀌면 오래된 값이라 내지 않고 새로 청한다
    assert receiver.settings_for(1) is None
    assert wants(receiver, 1) is True


def test_오는_중인_설정_값은_한도까지_기다린다(receiver):
    send(receiver, 1, 100)
    receiver.want_settings(1)
    assert wants(receiver, 1)  # 애드온에 알렸다(오는 중)
    later = threading.Timer(0.1, lambda: send(receiver, 1, 100, settings=SETTINGS))
    later.start()
    assert receiver.settings_for(1, wait=3.0) is not None
    later.join()


def test_안_오는_설정_값은_한도만큼만_기다리고_없이_간다(receiver):
    send(receiver, 1, 100)
    assert receiver.settings_for(1, wait=0.05) is None


def test_알린_설정_값이_한도_안에_안_오면_다시_청한다(receiver, monkeypatch):
    # 애드온이 읽다 실패해 설정 값 없이 보내도 그 창이 영영 못 청하는 일이 없게(PR #42 검토 K1)
    import blender_tutor.receiver as module

    send(receiver, 1, 100)
    receiver.want_settings(1)
    assert wants(receiver, 1)  # 알림(오는 중)
    send(receiver, 1, 100)  # 설정 값 없는 봉투만 옴
    assert receiver.settings_for(1) is None and wants(receiver, 1) is False  # 한도 안: 다시 청하지 않음
    monkeypatch.setattr(module, "PENDING_LIMIT", 0.0)
    assert receiver.settings_for(1) is None and wants(receiver, 1) is True  # 한도 지남: 다시 청함


def test_프로세스_켜진_시각은_켜진_동안_같고_없는_번호는_None():
    import os

    from blender_tutor.receiver import process_started

    mine = process_started(os.getpid())
    assert mine and mine == process_started(os.getpid())
    assert process_started(2**22 + 12345) is None  # 쓰이지 않는 번호
