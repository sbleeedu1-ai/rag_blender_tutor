"""Blender 안에서 돈다: 화면 글자(영어)와 번역 문맥을 모두 뽑아 JSON으로 쓴다(티켓 31 메뉴 이름 검수).

실행: blender -b --factory-startup --python blender_ui_labels.py -- <출력.json>
보통은 python -m blender_tutor.menu_review가 띄운다.

뽑는 것: 조작(bpy.ops)·자료 종류(bpy.types)의 이름, 그 속성 이름과 고르는 값 이름, 메뉴·패널 제목,
화면 파이썬 코드(bl_ui·bl_operators)의 text="..."와 text_ctxt=. Blender 안쪽 C 코드가 그리는 글자는 뽑지 못한다.
출력 모양: 영어 → 문맥 → {"count": 쓰는 곳 수, "where": 쓰는 곳 모두}
"""

import json
import os
import re
import sys

import bpy

labels: dict = {}


def add(label: str, context: str, where: str) -> None:
    if not label:
        return
    use = labels.setdefault(label, {}).setdefault(context or "*", {"count": 0, "where": []})
    use["count"] += 1
    use["where"].append(where)


def add_rna(rna, where: str) -> None:
    add(rna.name, rna.translation_context, where)
    for prop in rna.properties:
        add(prop.name, prop.translation_context, f"{where}.{prop.identifier}")
        if prop.type == "ENUM":
            for item in prop.enum_items:
                add(item.name, prop.translation_context, f"{where}.{prop.identifier}={item.identifier}")


seen = set()
for name in dir(bpy.types):
    cls = getattr(bpy.types, name)
    rna = getattr(cls, "bl_rna", None)
    if rna is None or rna.identifier in seen:
        continue
    seen.add(rna.identifier)
    add_rna(rna, f"type:{name}")
    label = getattr(cls, "bl_label", None)
    if label and label != rna.name:
        add(label, getattr(cls, "bl_translation_context", "*"), f"label:{name}")

for module in dir(bpy.ops):  # 조작은 bpy.types에 다 보이지 않는다
    for op in dir(getattr(bpy.ops, module)):
        try:
            rna = getattr(getattr(bpy.ops, module), op).get_rna_type()
        except Exception:
            continue
        add_rna(rna, f"op:{module}.{op}")

# C 코드가 만든 메뉴는 bpy.types에 없어 제목을 못 뽑는다. 화면 코드가 부르는 15개 가운데 초보자가 볼 만한 것만 손으로 적는다.
# 문맥은 기본(*): 오브젝트 메뉴의 "컬렉션 링크"를 사용자 화면에서 확인함(2026-10-27). 나머지 셋은 같은 방식이라 보고 적음(확인 안 함)
C_MENUS = {
    "OBJECT_MT_link_to_collection": "Link to Collection",
    "OBJECT_MT_move_to_collection": "Move to Collection",
    "TOPBAR_MT_file_open_recent": "Open Recent",
    "TOPBAR_MT_undo_history": "Undo History",
}
for menu, label in C_MENUS.items():
    add(label, "*", f"cmenu:{menu}")

def enclosing_call(source: str, at: int) -> tuple[str, str]:
    """at 자리를 감싼 함수 호출의 (함수 이름, 첫 글자 인자). layout.operator("uv.select_overlap", text=…) → ("operator", "uv.select_overlap")"""
    depth = 0
    for i in range(at - 1, -1, -1):
        if source[i] == ")":
            depth += 1
        elif source[i] == "(":
            if depth == 0:
                name = re.search(r"(\w+)\s*$", source[:i])
                first = re.match(r'\s*"([^"]*)"', source[i + 1 :])
                return (name[1] if name else "", first[1] if first else "")
            depth -= 1
    return "", ""


def operator_context(idname: str) -> str:
    try:
        module, op = idname.split(".")
        return getattr(getattr(bpy.ops, module), op).get_rna_type().translation_context
    except Exception:
        return "*"


contexts = {key: getattr(bpy.app.translations.contexts, key) for key in dir(bpy.app.translations.contexts) if not key.startswith("_")}
text_pattern = re.compile(r'text=(?:iface_\()?"([^"]+)"\)?(?:[^\n)]*?text_ctxt=([\w.]+|"[^"]*"))?')
# 조작 단추에 붙인 글자는 text_ctxt가 없으면 그 조작의 문맥(보통 Operator)으로 번역된다.
# UV 메뉴의 layout.operator("uv.select_overlap", text="Overlap")가 화면에 영어로 보이는 것으로 확인함(2026-10-27, Operator 문맥은 번역 없음)
OPERATOR_CALLS = {"operator", "operator_menu_enum", "operator_enum", "operator_menu_hold"}
scripts = bpy.utils.system_resource("SCRIPTS")
for folder in ("startup/bl_ui", "startup/bl_operators"):
    for root, _, files in os.walk(os.path.join(scripts, folder)):
        for file in files:
            if not file.endswith(".py"):
                continue
            source = open(os.path.join(root, file), encoding="utf-8").read()
            for match in text_pattern.finditer(source):
                given = match[2]
                if given is None:
                    call, first = enclosing_call(source, match.start())
                    context = operator_context(first) if call in OPERATOR_CALLS else "*"
                elif given.startswith('"'):
                    context = given.strip('"')
                else:
                    context = contexts.get(given.split(".")[-1], given)
                add(match[1], context, f"py:{file}")

with open(sys.argv[-1], "w", encoding="utf-8") as out:
    json.dump(labels, out, ensure_ascii=False, indent=0)
print(f"화면 글자 {len(labels)}개 → {sys.argv[-1]}")
