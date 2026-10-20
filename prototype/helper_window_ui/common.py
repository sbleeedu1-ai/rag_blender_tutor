# 시제품(버릴 코드): 두 판(위젯 / QML)이 함께 쓰는 가짜 답, 트레이 아이콘, 창 자리
import itertools
import os
import time

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

START = time.perf_counter()

WIDTH, HEIGHT = 420, 560
FONT = "Malgun Gothic"

# 설명서 문장을 옮기지 않고 우리 말로 쓴 가짜 답
FAKE_ANSWERS = [
    {
        "text": "배열(Array) 모디파이어를 쓰면 같은 물체를 일정한 간격으로 여러 개 늘어놓을 수 있어요. "
                "오른쪽 속성 창의 렌치 모양 탭에서 모디파이어 추가(Add Modifier) > 생성(Generate) > 배열(Array)을 고르세요. "
                "개수(Count)를 바꾸면 몇 개를 만들지 정할 수 있어요.",
        "sources": [
            {"path": "모델링 > 모디파이어 > 생성 > 배열", "url": "https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/array.html", "note": "그림 있음"},
        ],
    },
    {
        "text": "모서리를 둥글게 깎으려면 편집 모드(Tab)에서 모서리를 고른 뒤 Ctrl+B를 누르고 마우스를 움직이세요. "
                "마우스 휠을 굴리면 깎는 면의 수가 늘어나 더 둥글어져요.",
        "sources": [
            {"path": "모델링 > 메시 > 편집 > 모서리 > 베벨", "url": "https://docs.blender.org/manual/en/5.2/modeling/meshes/editing/edge/bevel.html", "note": "그림 있음 · 영상 있음"},
            {"path": "모델링 > 메시 > 선택 모드", "url": "https://docs.blender.org/manual/en/5.2/modeling/meshes/selecting/introduction.html", "note": ""},
        ],
    },
    {
        "text": "긴 답 줄바꿈 확인용이에요. 칼날을 길게 만들려면 먼저 물체 모드에서 정육면체를 고르고 S를 눌러 크기를 바꾼 뒤, "
                "곧바로 Z를 누르면 위아래 방향으로만 늘어나요. 숫자를 직접 치면 정확한 배율로 늘릴 수 있고, Enter로 확정해요. "
                "늘린 다음에는 Ctrl+A > 배율(Scale)로 배율을 적용해 두어야 나중에 베벨이나 모디파이어가 한쪽으로 찌그러지지 않아요. "
                "이 단계에서는 치수보다 비율이 중요하니, 칼날이 손잡이보다 대략 세 배쯤 길어 보이면 다음 단계로 넘어가도 괜찮아요.",
        "sources": [
            {"path": "장면 배치 > 물체 > 변형 > 배율", "url": "https://docs.blender.org/manual/en/5.2/scene_layout/object/editing/transform/scale.html", "note": ""},
        ],
    },
]
_answers = itertools.cycle(FAKE_ANSWERS)

FIRST_QUESTION = "배열 모디파이어 어디 있어요?"


def next_answer():
    return next(_answers)


def log(variant, msg):
    print(f"[{variant} {time.perf_counter() - START:7.3f}s] {msg}", flush=True)


def window_rect(slot):
    """화면 오른쪽 아래 정해진 자리. slot 1은 그 왼쪽(두 판 나란히 비교용)."""
    area = QGuiApplication.primaryScreen().availableGeometry()
    x = area.right() - WIDTH - 24 - slot * (WIDTH + 24)
    y = area.bottom() - HEIGHT - 24
    return QRect(QPoint(x, y), QPoint(x + WIDTH - 1, y + HEIGHT - 1))


def make_icon():
    # 로고 없이 직접 그린 단순한 동그라미 아이콘
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(120, 140, 255))
    p.setPen(Qt.NoPen)
    p.drawEllipse(6, 6, 52, 52)
    p.setBrush(QColor(255, 255, 255, 220))
    p.drawEllipse(24, 24, 16, 16)
    p.end()
    return QIcon(pix)


def make_tray(app, variant, on_show):
    """왼쪽 클릭 = 보이기(숨기지 않음), 오른쪽 메뉴 = 보이기 / 끝내기."""
    tray = QSystemTrayIcon(make_icon(), app)
    tray.setToolTip(f"도우미 시제품 ({variant})")
    menu = QMenu()
    menu.addAction("보이기", on_show)
    menu.addAction("끝내기", app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: on_show() if reason == QSystemTrayIcon.Trigger else None)
    tray.show()
    tray._menu = menu  # 메뉴가 지워지지 않게 붙잡아 둠
    return tray


def auto_shot(app, rect_fn):
    """확인용: PROTO_SHOT=파일.png 이면 4초 뒤 그 자리 화면을 찍고 끝낸다."""
    path = os.environ.get("PROTO_SHOT")
    if not path:
        return
    def shoot():
        r = rect_fn()
        QGuiApplication.primaryScreen().grabWindow(0, r.x() - 20, r.y() - 20, r.width() + 40, r.height() + 40).save(path)
        app.quit()
    QTimer.singleShot(4000, shoot)
