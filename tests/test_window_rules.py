"""도우미 창 규칙(ADR-0001 창 동작, 티켓 26): 화면 모습 → 창을 어디에 둘지, 질문을 어느 Blender 상태로 보낼지, 답 줄바꿈.

Windows를 직접 만지지 않는 판단만 본다. 실제로 창이 그렇게 움직이는지는 강의실 PC 눈 확인으로 본다.
"""

from blender_tutor.window_rules import FrontBlender, Place, Screen, by_sentence, needs_move, place

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


def test_Blender가_모두_최소화되면_앞이_작업_표시줄이나_도우미여도_숨긴다():
    # 작업 표시줄 단추로 Blender를 내리면 앞이 작업 표시줄로 남거나, Windows가 도우미 창을 대신 앞으로 둔다
    assert place(screen(BROWSER, taskbar=True, visible=False), ME, put_away=False) == Place.HIDDEN
    assert place(screen(ME, visible=False), ME, put_away=False) == Place.HIDDEN


def test_앞_창이_없는_순간에는_그대로_둔다():
    # 초점이 넘어가는 사이 Windows가 앞 창 없음(0)을 돌려준다. 0 '뒤로' 보내면 오히려 맨 앞으로 올라온다
    assert place(screen(0), ME, put_away=False) == Place.KEEP


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


def test_번호_목록의_점에서는_줄을_바꾸지_않는다():
    assert by_sentence("순서: 1. Tab 누르기 2. 고르기") == "순서: 1. Tab 누르기 2. 고르기"


def test_같은_자리라도_앞_프로그램이_바뀌면_다시_그_뒤로_보낸다():
    # Alt+Tab: 고르기 화면(늘 맨 위인 창) 뒤로 갔다가 VS Code가 앞이 돼도 '그 뒤로'는 같아 아무것도 안 하던 버그
    last = None
    assert needs_move(Place.BEHIND, 50, last)
    last = (Place.BEHIND, 50)
    assert not needs_move(Place.BEHIND, 50, last)
    assert needs_move(Place.BEHIND, 60, last)  # 다른 프로그램이 앞이 됨
    assert not needs_move(Place.KEEP, 0, last)  # 그대로는 언제나 그대로


def test_맨_위와_숨김은_앞_프로그램이_바뀌어도_다시_하지_않는다():
    assert not needs_move(Place.TOP, 60, (Place.TOP, 50))  # Blender 둘 사이를 오감
    assert not needs_move(Place.HIDDEN, 60, (Place.HIDDEN, 50))
    assert needs_move(Place.TOP, 50, (Place.BEHIND, 50))
