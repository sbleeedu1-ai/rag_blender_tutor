"""기계 지표 도구(.claude/tools/answer_facts.py, docs/plan/01 C). 메뉴 나무·키맵·답은 모두 지어낸 작은 것이다."""

import importlib.util
import json
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / ".claude" / "tools" / "answer_facts.py"
spec = importlib.util.spec_from_file_location("answer_facts", TOOL)
facts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(facts)

PATHS = {"OBJECT": [["Object", "menu", "VIEW3D_MT_object"], ["Object > Shade Auto Smooth", "op", "object.shade_auto_smooth"],
                    ["Object > Snap", "menu", "VIEW3D_MT_snap"], ["Object > Snap > Selection to Cursor", "op", "view3d.snap_selected_to_cursor"]],
         "EDIT_MESH": [["Edge > Loop Cut and Slide", "op", "mesh.loopcut_slide"], ["Mesh > Normals", "menu", "VIEW3D_MT_edit_mesh_normals"],
                       ["Mesh > Normals > Recalculate Outside", "op", "mesh.normals_make_consistent"]]}


def item(idname, key, ctrl=0, alt=0, shift=0, oskey=0, props=None):
    return {"km": "Mesh", "idname": idname, "type": key, "ctrl": ctrl, "alt": alt, "shift": shift, "oskey": oskey, "any": False, "props": props or {}}


KEYMAP = {"linux": [item("mesh.loopcut_slide", "R", ctrl=1), item("mesh.normals_make_consistent", "N", shift=1),
                    item("wm.call_menu", "N", alt=1, props={"name": "VIEW3D_MT_edit_mesh_normals"})],
          "darwin": [item("mesh.loopcut_slide", "R", oskey=1)]}
TREE, KEYS = facts.Tree(PATHS), facts.Keymap(KEYMAP)


def test_메뉴_길은_나무에_있는_길과_없는_길을_가른다():
    raw = "[[Object > Shade Auto Smooth]]을 누르고, [[Object > Shading > Shade Auto Smooth]]도 보세요. [[Snap > Selection to Cursor]], [[Modifier Properties > Add]], [[Bevel]]"
    assert [(item["길"], item["판정"]) for item in facts.menu_paths(raw, TREE)] == [
        ("Object > Shade Auto Smooth", "있음"), ("Object > Shading > Shade Auto Smooth", "나무와 다름"),
        ("Snap > Selection to Cursor", "있음(앞 생략)"), ("Modifier Properties > Add", "나무에 없음"),
    ]  # 단이 하나인 [[Bevel]]은 길이 아니라 세지 않는다


def test_단축키는_괄호로_바로_붙은_이름의_조작의_기본_키맵과_맞댄다():
    raw = ("[[Loop Cut and Slide]](Alt-C)로 자릅니다. [[Edge > Loop Cut and Slide]]는 Ctrl+R이에요. Ctrl + R([[Edge > Loop Cut and Slide]])도 같아요.\n"
           "Cmd+R(또는 [[Loop Cut and Slide]]). [[Normals]] 메뉴(단축키는 Alt+N)를 여세요. [[Recalculate Outside]](Alt-N). Ctrl+Z로 되돌려요. Ctrl+Click으로 [[Bevel]]")
    assert [(item["키"], item["판정"]) for item in facts.shortcuts(raw, TREE, KEYS)] == [
        ("Alt-C", "기본 키맵과 다름"), ("Ctrl+R", "가를 수 없음(괄호로 붙은 이름 없음)"), ("Ctrl + R", "맞음"),
        ("Cmd+R", "맞음"), ("Alt+N", "맞음"), ("Alt-N", "기본 키맵과 다름"),
        ("Ctrl+Z", "가를 수 없음(괄호로 붙은 이름 없음)"), ("Ctrl+Click", "가를 수 없음(키 이름 모름)"),
    ]


def test_코드_이름과_마크다운_기호와_보낸_줄에_없는_설정_이름을_센다():
    shown = "**주의**\n# 원인\n지금 use_proportional_edit가 켜져 있고 show_wireframe도 켜져 있어요. `x` 를 보세요."
    assert facts.code_marks(shown) == {"코드 이름": 2, "**": 2, "줄 머리 #": 1, "백틱": 2}
    assert facts.unsent_names(shown, ["Scene.tool_settings.use_proportional_edit = True"]) == ["show_wireframe"]


def test_명령은_답별_줄과_표를_쓰고_채점_이유의_같은_까닭과_맞음에서_잡은_수를_낸다(tmp_path):
    answers = tmp_path / "답.jsonl"
    rows = [{"열쇠": "1/Q01", "원문": "[[Loop Cut and Slide]](Alt-C)", "답": "루프 컷(Alt-C)", "판정": "틀림", "채점 이유": "단축키 Alt-C가 다름", "보낸 설정 줄": []},
            {"열쇠": "1/Q02", "원문": "[[Object > Shading > Shade Auto Smooth]]", "답": "가", "판정": "맞음", "채점 이유": "", "보낸 설정 줄": []}]
    answers.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
    (tmp_path / "paths.json").write_text(json.dumps(PATHS), encoding="utf-8")
    (tmp_path / "keymap.json").write_text(json.dumps(KEYMAP), encoding="utf-8")
    facts.main(tmp_path / "out", tmp_path / "paths.json", tmp_path / "keymap.json", answers)
    report = (tmp_path / "out" / "표.md").read_text(encoding="utf-8")
    assert "| 단축키(기본 키맵과 다름) | 1 | 1 | 0 |" in report
    assert "| 메뉴 길(나무와 다름) | 1 | 0 | 1 |" in report
    assert len((tmp_path / "out" / "답별.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_연습_과정_메뉴_칸은_없음을_건너뛰고_줄_번호와_판정을_낸다(tmp_path):
    (tmp_path / "sword.yaml").write_text("조작:\n  - 메뉴: View > Viewport Shading > Material Preview\n  - 메뉴: 없음\n  - 메뉴: Object > Shade Auto Smooth\n", encoding="utf-8")
    assert facts.course_menus(tmp_path, TREE) == [("sword.yaml", 2, "View > Viewport Shading > Material Preview", "나무에 없음"),
                                                  ("sword.yaml", 4, "Object > Shade Auto Smooth", "있음")]


def test_단축키는_괄호_밖의_가까운_이름에_붙이지_않는다():
    # 첫 판은 같은 문장의 가장 가까운 이름에 붙여 "Shift + A로 [[Cylinder]]"·"Alt-G로 [[Object]] 메뉴"를 다름으로 잡았다(HISTORY [486])
    assert [item["판정"] for item in facts.shortcuts("Ctrl+R로 [[Edge > Loop Cut and Slide]]", TREE, KEYS)] == ["가를 수 없음(괄호로 붙은 이름 없음)"]
    assert [item["판정"] for item in facts.shortcuts("[[Alt-C]]로 [[Loop Cut and Slide]]를 쓰세요", TREE, KEYS)] == ["가를 수 없음(괄호로 붙은 이름 없음)"]


def test_새_나무는_뿌리_메뉴로만_다름을_가르고_덜_그려진_메뉴_아래는_가를_수_없다():
    tree = facts.Tree({"모드": PATHS, "뿌리": ["Object", "Edge", "Mesh"], "덜 그려진 길": {"OBJECT": ["Object > Snap"]}})
    assert [tree.judge(mark) for mark in ("Object > Snap > Cursor to Selected", "Object > Shading > Shade Auto Smooth",
                                          "Snap > Image", "Mesh > Normals > Recalculate Outside")] == [
        "가를 수 없음(덜 그려진 메뉴)", "나무와 다름", "나무에 없음", "있음"]  # Snap은 나무의 단 글자지만 뿌리가 아님
