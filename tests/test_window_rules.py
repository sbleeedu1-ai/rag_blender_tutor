"""도우미 창 규칙(ADR-0001 창 동작, 티켓 26): 화면 모습 → 창을 어디에 둘지, 질문을 어느 Blender 상태로 보낼지, 답 줄바꿈.

Windows를 직접 만지지 않는 판단만 본다. 실제로 창이 그렇게 움직이는지는 강의실 PC 눈 확인으로 본다.
"""

from blender_tutor.window_rules import FrontBlender, Place, Screen, by_sentence, place

ME = 900  # 도우미 프로그램의 프로세스 번호
BLENDER_A, BLENDER_B, BROWSER = 111, 222, 333


def screen(foreground: int, taskbar: bool = False, visible: bool = True) -> Screen:
    return Screen(foreground_pid=foreground, foreground_is_taskbar=taskbar, blender_pids=frozenset({BLENDER_A, BLENDER_B}), blender_visible=visible)


def test_Blender나_도우미_자신이_앞이면_맨_위():
    assert place(screen(BLENDER_A), ME, put_away=False) == Place.TOP
    assert place(screen(BLENDER_B), ME, put_away=False) == Place.TOP
    assert place(screen(ME), ME, put_away=False) == Place.TOP


def test_다른_프로그램이_앞이면_그_뒤로():
    assert place(screen(BROWSER), ME, put_away=False) == Place.BEHIND


def test_Blender가_모두_최소화되면_숨긴다():
    assert place(screen(BROWSER, visible=False), ME, put_away=False) == Place.HIDDEN


def test_작업_표시줄이나_트레이가_앞이면_그대로_둔다():
    # 트레이를 누르는 순간 앞 프로그램이 탐색기가 되어 창이 내려갔다 올라오는 깜빡임을 막는다
    assert place(screen(BROWSER, taskbar=True), ME, put_away=False) == Place.KEEP
    assert place(screen(BROWSER, taskbar=True, visible=False), ME, put_away=False) == Place.KEEP


def test_사용자가_직접_내리면_Blender가_앞이어도_숨긴_채():
    assert place(screen(BLENDER_A), ME, put_away=True) == Place.HIDDEN
    assert place(screen(ME), ME, put_away=True) == Place.HIDDEN


def test_질문은_마지막으로_앞에_있던_Blender로_보낸다():
    blenders = {10: BLENDER_A, 20: BLENDER_B}  # 창 번호 → 프로세스 번호
    front = FrontBlender()
    front.saw_foreground(BLENDER_B, blenders)
    assert front.window(blenders) == 20
    front.saw_foreground(BROWSER, blenders)  # 다른 프로그램을 거쳐도 마지막 Blender를 기억한다
    front.saw_foreground(ME, blenders)
    assert front.window(blenders) == 20
    front.summoned(10)  # F10을 누른 Blender
    assert front.window(blenders) == 10


def test_마지막_Blender가_닫히면_남은_Blender로_보낸다():
    front = FrontBlender()
    front.summoned(10)
    assert front.window({20: BLENDER_B}) == 20
    assert front.window({}) is None


def test_답은_문장_끝마다_줄을_바꾸고_숫자_속_점은_그대로_둔다():
    assert by_sentence("Blender 5.2에서는 Tab을 눌러요. 그다음 Ctrl+B! 됐나요? 네") == "Blender 5.2에서는 Tab을 눌러요.\n그다음 Ctrl+B!\n됐나요?\n네"
    assert by_sentence("끝.") == "끝."
