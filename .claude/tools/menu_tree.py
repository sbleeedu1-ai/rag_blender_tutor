"""3D 뷰 머리 메뉴의 나무(메뉴 길 → 조작)를 Blender에서 뽑는다. 기계 지표(answer_facts.py)의 메뉴 길·단축키 대조에 쓴다.

01 조사 2의 첫 판(results/20261118/153213_검색답_다시설계/work/menus.py·paths.py)을 저장소로 옮겨 빈자리를 고친 판이다(HISTORY [469], 04 계획 6절).
고친 것:
- 화면 없는 Blender에서 context.space_data가 비어 View 메뉴가 첫 줄에서 멈췄다. 3D 뷰 영역(Layout 화면)을 문맥으로 주고 그린다
  (공식 문서 bpy.types.Context.temp_override: 키워드로 문맥 칸을 덮음. -b에서 space_data가 잡히는 것은 실행으로 확인).
- operator_enum(그 메뉴에 항목을 펼침)과 operator_menu_enum(하위 메뉴로 펼침)을 조작의 열거 항목으로 펼친다
  (무엇을 펼치는지는 공식 문서에 없고 [469] 화면 확인과 소스 bl_ui/space_view3d.py로 정함). 정적 enum_items를 쓰므로,
  상황에 따라 숨는 항목(Merge의 At First·At Last)도 들어간다(조금 넓게 잡힘).
- prop 줄(View > Sidebar 같은 켜고 끄는 칸)을 칸의 화면 이름(text 또는 RNA 이름)으로 넣는다(종류 "prop").
- 그리다 오류로 멈춘 메뉴는 "덜 그려진 메뉴"로 따로 적는다. answer_facts는 그 아래 길을 "가를 수 없음"으로 낸다.

실행(돈 0, 공장 설정, 읽기만):
  /Volumes/mac_ssd/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python .claude/tools/menu_tree.py -- <출력 .json>
출력: {"모드": {"OBJECT"|"EDIT_MESH": [[길 글, "op"|"menu"|"prop", 조작 이름|메뉴 클래스|칸 이름]]},
       "덜 그려진 길": {모드: [메뉴 길 글]}, "뿌리": [첫 단 글자], "오류": {모드: {메뉴 클래스: 오류}}}
"""

import json
import sys
import types

import bpy


class Props:
    """operator()가 돌려주는 속성 묶음 흉내. 값을 넣어도 무시한다."""

    def __setattr__(self, name, value):
        pass

    def __getattr__(self, name):
        return Props()

    def __call__(self, *args, **kwargs):
        return Props()

    def __setitem__(self, key, value):
        pass


def _prop_name(data, prop, text):
    if text:
        return text
    rna = getattr(data, "bl_rna", None)
    if rna is not None and prop in rna.properties:
        return rna.properties[prop].name
    return prop


class Rec:
    """메뉴 draw가 부르는 layout 흉내. 항목 호출을 log에 (종류, 이름, 글자, 덧붙임)으로 적는다."""

    def __init__(self, log):
        object.__setattr__(self, "log", log)

    def __getattr__(self, name):
        log = self.log
        if name == "operator":
            def operator(operator, text=None, **kwargs):
                log.append(("op", operator, text, None))
                return Props()
            return operator
        if name == "operator_enum":
            def operator_enum(operator, property=None, **kwargs):
                log.append(("enum", operator, None, property))
                return Props()
            return operator_enum
        if name == "operator_menu_enum":
            def operator_menu_enum(operator, property=None, text=None, **kwargs):
                log.append(("menu_enum", operator, text, property))
                return Props()
            return operator_menu_enum
        if name == "operator_menu_hold":
            def operator_menu_hold(operator, text=None, **kwargs):
                log.append(("op", operator, text, None))
                return Props()
            return operator_menu_hold
        if name == "menu":
            def menu(menu, text=None, **kwargs):
                log.append(("menu", menu, text, None))
            return menu
        if name == "menu_contents":
            def menu_contents(menu):
                log.append(("contents", menu, None, None))
            return menu_contents
        if name in ("prop", "prop_menu_enum", "prop_with_popover", "prop_enum", "props_enum"):
            def prop(data, prop=None, *args, text=None, **kwargs):
                if isinstance(prop, str):
                    log.append(("prop", prop, _prop_name(data, prop, text), None))
            return prop
        if name in ("label", "separator", "separator_spacer", "template_ID", "template_search", "popover"):
            return lambda *args, **kwargs: None
        return lambda *args, **kwargs: Rec(log)  # column·row·box 등: 같은 log에 적는 새 layout

    def __setattr__(self, name, value):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Fake:
    """메뉴 클래스의 draw를 부를 self 흉내(layout만 기록용)."""

    def __init__(self, cls, layout):
        object.__setattr__(self, "_cls", cls)
        object.__setattr__(self, "layout", layout)

    def __getattr__(self, name):
        value = getattr(self._cls, name)
        return types.MethodType(value, self) if isinstance(value, types.FunctionType) else value


def menu_classes():
    found = {}

    def walk(cls):
        for sub in cls.__subclasses__():
            found[sub.__name__] = sub
            walk(sub)

    walk(bpy.types.Menu)
    return found


def draw_all(classes):
    """메뉴 클래스마다 (오류 또는 None, 기록)."""
    drawn = {}
    for name, cls in classes.items():
        log = []
        try:
            cls.draw(Fake(cls, Rec(log)), bpy.context)
            drawn[name] = (None, log)
        except Exception as error:  # 그리다 멈춘 메뉴를 '덜 그려짐'으로 남기려고 잡는다
            drawn[name] = (f"{type(error).__name__}: {str(error)[:120]}", log)
    return drawn


def op_name(idname):
    module, op = idname.split(".")
    return getattr(getattr(bpy.ops, module), op).get_rna_type().name


def enum_items(idname, prop):
    module, op = idname.split(".")
    rna = getattr(getattr(bpy.ops, module), op).get_rna_type()
    return [(item.identifier, item.name) for item in rna.properties[prop].enum_items]


def paths(drawn, labels):
    """뿌리 메뉴부터 내려가며 [길 글, 종류, 이름]과 덜 그려진 메뉴의 길."""
    rows, partial = [], []

    def walk(menu, prefix, seen):
        error, log = drawn.get(menu, ("없는 메뉴", []))
        if error:
            partial.append(" > ".join(prefix))
        for kind, name, text, extra in log:
            if kind == "op":
                rows.append((prefix + [text or op_name(name)], "op", name))
            elif kind == "enum":
                rows.extend((prefix + [label], "op", name) for _, label in enum_items(name, extra))
            elif kind == "menu_enum":
                label = text or op_name(name)
                rows.append((prefix + [label], "op", name))
                rows.extend((prefix + [label, item], "op", name) for _, item in enum_items(name, extra))
            elif kind == "prop":
                rows.append((prefix + [text], "prop", name))
            elif kind == "menu":
                label = text or labels.get(name) or name
                rows.append((prefix + [label], "menu", name))
                if name not in seen:
                    walk(name, prefix + [label], seen | {name})
            elif kind == "contents" and name not in seen:
                walk(name, prefix, seen | {name})

    walk("VIEW3D_MT_editor_menus", [], {"VIEW3D_MT_editor_menus"})
    walk("TOPBAR_MT_editor_menus", [], {"TOPBAR_MT_editor_menus"})
    walk("VIEW3D_MT_add", ["Add"], {"VIEW3D_MT_add"})
    return [[" > ".join(path), kind, name] for path, kind, name in rows], [p for p in partial if p]


def main(out):
    classes = menu_classes()
    labels = {name: getattr(cls, "bl_label", None) for name, cls in classes.items()}
    screen = bpy.data.screens["Layout"]
    area = next(area for area in screen.areas if area.type == "VIEW_3D")
    region = next(region for region in area.regions if region.type == "WINDOW")
    cube = bpy.data.objects["Cube"]
    bpy.context.view_layer.objects.active = cube
    cube.select_set(True)
    result = {"모드": {}, "덜 그려진 길": {}, "오류": {}}
    with bpy.context.temp_override(screen=screen, area=area, region=region, space_data=area.spaces.active):
        for mode in ("OBJECT", "EDIT"):
            if mode == "EDIT":
                bpy.ops.object.mode_set(mode="EDIT")
            key = bpy.context.mode if mode == "EDIT" else "OBJECT"
            drawn = draw_all(classes)
            rows, partial = paths(drawn, labels)
            result["모드"][key] = rows
            result["덜 그려진 길"][key] = partial
            result["오류"][key] = {name: error for name, (error, _) in drawn.items() if error}
            print(key, "길", len(rows), "덜 그려진 길", partial, "오류 메뉴", len(result["오류"][key]))
    result["뿌리"] = sorted({row[0].split(" > ")[0] for rows in result["모드"].values() for row in rows})
    with open(out, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1])
