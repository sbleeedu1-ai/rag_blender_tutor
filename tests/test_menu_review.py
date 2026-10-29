"""메뉴 이름 검수 초안(티켓 31): Blender가 화면 곳곳에서 쓰는 문맥으로 고정 짝을 미리 고른다.

이름·문맥·번역은 손으로 지은 것이다(Blender 번역 원문 아님). 쓰는 곳 모양은 Blender에서 뽑은 파일과 같다:
영어 → 문맥 → {"count": 쓰는 곳 수, "where": 쓰는 곳 몇 개}.
"""

from blender_tutor.menu_names import MenuName, Source, Translation
from blender_tutor.menu_review import Kind, draft_choices, draft_titles


def _name(english, *translations, sources=(Source.UI,)):
    return MenuName(english, tuple(Translation(k, tuple(c)) for k, c in translations), 3, "https://x", sources)


def _used(**contexts):
    return {context.replace("_", "*"): {"count": count, "where": [f"prop:{context}.{i}" for i in range(count)]}
            for context, count in contexts.items()}


APPLY = _name("Apply", ("적용", ["*", "Operator"]), ("신청하기", ["WindowManager"]))


def test_화면이_한_가지_한국어로만_쓰면_그_문맥을_자동으로_고른다():
    [item] = draft_choices([APPLY], {"Apply": _used(_=5, Operator=2)})
    assert item.kind == Kind.AUTO
    assert item.context == "*"  # 쓰는 곳이 가장 많은 문맥
    assert item.screen == {"적용": 7}


def test_쓰는_곳마다_한국어가_갈리면_판단에_넘기고_자동으로_고르지_않는다():
    edit = _name("Edit Mode", ("에디트 모드", ["*"]), ("편집 모드", ["Operator"]))
    [item] = draft_choices([edit], {"Edit Mode": _used(_=6, Operator=1)})
    assert item.kind == Kind.SPLIT
    assert item.context is None
    assert item.screen == {"에디트 모드": 6, "편집 모드": 1}


def test_번역이_없는_문맥은_영어_그대로_보이는_것으로_센다():
    at_center = _name("At Center", ("센터에서", ["Operator"]), ("At Center", ["Mesh"]))
    [item] = draft_choices([at_center], {"At Center": _used(Mesh=2)})
    assert item.kind == Kind.AUTO
    assert item.context == "Mesh"
    assert item.screen == {"At Center": 2}


def test_사전_후보에_없는_문맥을_쓰면_판단에_넘긴다():
    [item] = draft_choices([APPLY], {"Apply": _used(_=5, Image=1)})
    assert item.kind == Kind.SPLIT
    assert item.screen == {"적용": 5, "?(Image)": 1}


def test_Blender에서_못_찾은_이름은_따로_가른다():
    [item] = draft_choices([APPLY], {})
    assert item.kind == Kind.UNSEEN
    assert item.context is None


def test_설명서의_말줄임표는_Blender_글자와_맞춰_찾는다():
    save = _name("Save As…", ("다른 이름으로 저장", ["*"]), ("다른 이름 저장", ["Operator"]))
    [item] = draft_choices([save], {"Save As...": _used(Operator=3)})
    assert item.context == "Operator"


def test_제목에서만_뽑은_이름은_Blender가_화면에_쓰는지만_적는다():
    solidify = _name("Solidify", ("솔리디파이", ["*"]), sources=(Source.TITLE,))
    regions = _name("Regions", ("영역", ["*"]), sources=(Source.TITLE,))
    items = draft_titles([solidify, regions], {"Solidify": _used(_=4)})
    assert [(item.english, item.in_blender) for item in items] == [("Solidify", 4), ("Regions", 0)]
