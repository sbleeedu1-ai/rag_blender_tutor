"""답 모델에 넘길 설정 값 읽기(2026-11-10, HISTORY [270], 명세 "애드온"의 '답 모델에 넘길 설정 값').

Blender 안 파이썬에서 돈다(bpy와 표준 라이브러리만, blender_tutor 패키지는 못 씀). 도우미가 청할 때만 부른다(입력을 시작할 때).
연구 도구에서 옮긴 것(data/eval/state_generic/, git 밖):
- 값 읽기: op_walk_v7_주소만.py의 snapshot()(7판). bpy.data·창 관리자·환경 설정에서 닿는 칸을 '자리|타입.칸'으로 적는다.
  자리 이름은 label()과 같고, 값 글은 repr(값)이다(공장값 표가 같은 모양으로 만들어졌다: h12_view.py가 md5를 글 그대로로 바꿈).
  자국 파일(crash_walk.mark)·키맵(full=False)·md5는 뺐다.
- 범위: h11_patch.py의 rule11()(주인·활성 항목·칠하기 도구), h11_rule.py(is_element·not_sent·ALWAYS 등).
- 공장값과 견주기: h12_rule.py의 Baseline.differs·strip_root·view_norm·strip_items, h12_patch.py의 view_area·norm.
- 고르기: h13_patch.py의 rule13()과 situations(). 1-a·2 갈래는 rule13이 줄 수만 셌으므로 아래 '초안'으로 새로 정했다.
한 줄 = "자리.칸 = 값"(예: Object[Cube].modifiers[Bevel].segments = 3). 값 글이 길면 잘라 총 글자 수를 붙인다.
"""

import heapq
import itertools
import json
import math
import re
from pathlib import Path

import bpy

# ---- 값 읽기(op_walk_v7 snapshot) ----
NEVER = {"rna_type", "bl_rna", "access_token", "session_uid", "original", "id_data", "depsgraph", "view_layer_eval"}
# 읽으면 Blender가 죽는 자리(op_walk SKIP_SITES 시험 7, h11_patch 뼈대일 때의 조작 기록 속성)
SKIP_SITES = {"SpaceView3D.local_view", "OBJECT_OT_vertex_group_set_active.group"}
VALUE_CHARS = 160  # 한 줄 값 글의 위 끝(넘으면 자르고 총 글자 수를 붙임)

# ---- 범위·고르기(h11_rule, h13_patch) ----
ALWAYS = {"WindowManager.operators", "RegionView3D.view_rotation", "RegionView3D.view_distance", "RegionView3D.view_location"}
SCREEN_KINDS = {"Region", "Screen", "Area", "View2D", "IDViewerPathElem", "View3DOverlay", "SpaceProperties"}
SCREEN_SITES = {"RegionView3D.perspective_matrix", "RegionView3D.view_matrix", "WindowManager.reports"}
RECORD_SITES = {"BlendData.is_dirty", "Object.tag"}
RECORD_KINDS = {"Operator", "OperatorOptions", "OperatorProperties", "Report", "Macro"}
COMMON = {"LayerObjects.selected", "LayerObjects.active", "ParticleEdit.object", "Object.select_get()", "BlendData.all_ids", "BlendData.objects", "Collection.all_objects",
          "Collection.collection_objects", "Collection.objects", "Scene.objects", "ViewLayer.objects", "Object.bound_box", "Object.dimensions", "BlendData.meshes", "Mesh.attributes",
          "Object.matrix_local", "Object.matrix_world", "Object.matrix_basis", "Object.mode", "Mesh.normals_domain", "Object.location", "Object.scale", "TextCurve.body",
          "TextCurve.body_format", "TextCurve.texspace_location"}
SELECTED_LIMIT = 10
OBJECT_ROOTS = re.compile(r"^(Object|Mesh|Curve|TextCurve|SurfaceCurve|Armature|Camera|\w*Light|GreasePencil\w*|Lattice|Curves|PointCloud|Volume|MetaBall|Speaker|LightProbe\w*)\[")
ITEM_SEGMENT = re.compile(r"\.(bones|edit_bones|layers|vertex_groups|particle_systems|material_slots)\[([^\]]*)\]")
MODE_PAINT = {"SCULPT": "sculpt", "VERTEX_PAINT": "vertex_paint", "WEIGHT_PAINT": "weight_paint", "TEXTURE_PAINT": "image_paint", "PARTICLE_EDIT": "particle_edit",
              "PAINT_GREASE_PENCIL": "gpencil_paint", "SCULPT_GREASE_PENCIL": "gpencil_sculpt_paint", "WEIGHT_GREASE_PENCIL": "gpencil_weight_paint", "VERTEX_GREASE_PENCIL": "gpencil_vertex_paint"}
ELEMENT_KINDS = {"ReadOnlyInteger", "VertexGroupElement", "Particle", "ChildParticle", "ParticleHairKey", "ParticleKey"}
ELEMENT_MESH = re.compile(r"^Mesh(Vertex|Edge|Polygon|Loop|UVLoop|NormalValue|Skin|PaintMask|VertColor|FaceMap|Select)\w*$")
NODE_PROPS = {"default_value", "is_linked", "mute", "nodes", "links", "image"}
ID_LABEL = re.compile(r"^(\w+)\[[^\]]*\]")
# 세 덩어리 1번(h13_patch G1)과 1번_나누기의 '1 늘'(NEW1)
G1 = {"BlendData.all_ids", "BlendData.objects", "BlendData.meshes", "Scene.objects", "ViewLayer.objects", "Collection.objects", "Collection.all_objects", "Collection.collection_objects",
      "LayerObjects.selected", "LayerObjects.active", "Object.select_get()", "Object.mode", "Object.location", "Object.matrix_basis", "Object.matrix_local", "Object.matrix_world",
      "Object.dimensions", "Object.bound_box"}
NEW1 = {"BlendData.actions", "BlendData.armatures", "BlendData.collections", "BlendData.curves", "BlendData.hair_curves", "BlendData.libraries", "BlendData.materials", "BlendData.node_groups",
        "Object.modifiers", "Object.rotation_euler", "Object.vertex_groups", "ObjectModifiers.active", "Scene.frame_current", "Scene.frame_float", "VertexGroups.active", "WindowManager.reports",
        "WorkSpace.tools", "WorkSpaceTool.idname", "WorkSpaceTool.index", "WorkSpaceTool.mode", "WorkSpaceTool.use_brushes"}
COMPARED = ("1", "3", "5", "6", "표에 없음")  # rule13: 4·뺌·2·1-a·문맥이 아니면 공장값과 견준다

# ---- 초안(사용자 검토 전, 2026-11-10 Claude가 정함) ----
# 1-a 갈래(그 상황일 때 늘): h13은 상황별 요약 줄 수(SUMMARY)만 셌다. 여기서는 그 상황의 1-a 칸을 활성 물체·그 데이터에서
#   점·면 같은 요소 칸을 빼고 지금 값 그대로 보내고, 상황마다 SITUATION_CAP줄에서 자른다.
# 2 갈래(계산 값): h13은 상수 109줄로만 셌다. 여기서는 Blender가 계산해 둔 칸(갈래 2)을 활성 물체·그 데이터·장면에서만,
#   요소 칸을 빼고 지금 값 그대로 보내고, 모두 합쳐 COMPUTED_CAP줄에서 자른다.
# 분야 묶음·2 초안에서 뺀다: 동영상 편집기의 채널은 장면마다 128개가 늘 있어(공장 장면 읽기에서 Channel 1-128, 실행으로 확인)
# 묶음 OT 줄의 절반 이상을 채웠다. 이 도우미는 동영상 편집을 다루지 않는다
FIXED_LISTS = (".sequence_editor.channels[",)
SITUATION_CAP = 30
COMPUTED_CAP = 120
SITUATION_GROUPS = {"메시 편집": ("1-a 메시 편집",), "뼈": ("1-a 뼈",), "곡선 편집": ("1-a 곡선",), "격자·메타볼": ("1-a 격자", "1-a 메타볼"),
                    "그리스 펜슬": ("1-a 그리스 펜슬",), "애니메이션": ("1-a 애니메이션",), "캐시": ("1-a 캐시",), "조각·칠하기": ("1-a 조각·칠하기",),
                    "노드 편집기": ("1-a 노드 편집기",)}


LAST_COUNTS = {}  # 마지막 읽기에서 갈래·까닭별로 센 칸 수(자체 시험이 줄 수를 설명하려고 본다)


def load_tables(folder: Path) -> dict:
    """state_tables/의 표 넷: 갈래(rules), 공장값(factory), 분야 묶음(bundles), 분야 목록(fields). 한 번 읽어 들고 쓴다."""
    def read(name):
        return json.loads((folder / name).read_text(encoding="utf-8"))

    factory = read("factory.json")
    bundles = read("bundles.json")
    return {
        "rules": read("rules.json"),
        "exact": {k: set(v) for k, v in factory["exact"].items()},
        "loose": {k: set(v) for k, v in factory["loose"].items()},
        "shaky": set(factory["shaky"]),
        "bundles": {code: set(sites) for code, sites in bundles.items()},
    }


def read_settings(context, tables: dict, *, situations: bool = True, computed: bool = True) -> dict:
    """{"always": [줄…], "situation": [1-a 초안 줄…], "computed": [2 초안 줄…], "fields": {분야 코드: [줄…]}}.
    32분야 모두 칸이 있다(줄이 없으면 빈 목록). blender_tutor/setting_fields.py의 SettingLines와 같은 모양.
    situations·computed는 1-a·2 갈래 초안을 넣을지(개발셋에서 끄고 켜 효과를 가르려고)."""
    values = snapshot()
    layer = context.view_layer
    target = layer.objects.active
    scope = _Scope(context, values, target, layer)
    rules = tables["rules"]
    always, extra = {}, {}
    counts = LAST_COUNTS
    counts.clear()
    counts["읽은 값"] = len(values)

    def count(name):
        counts[name] = counts.get(name, 0) + 1

    for key, text in values.items():
        path, site = key.rsplit("|", 1)
        if _is_element(site) or (_not_sent(site) and site not in ALWAYS):
            continue
        group = rules.get(site, "표에 없음")
        if site in G1 or site in NEW1:
            if _object_owned(path) and not _under(path, scope.object_roots):
                continue
            count("1(세 덩어리 1번)")
        elif site in ALWAYS:
            count("1(항상)")
        elif scope.modifier_cell(path) and group in ("3", "5", "6", "표에 없음"):
            count("모디파이어·제약")  # 그 물체에 있는 모디파이어·제약은 공장값이어도 늘(가설 16의 늘 보냄)
        elif not scope.in_scope(key, path):
            continue
        elif group == "4":
            count("4")
        elif group in COMPARED:
            if not _differs(tables, scope.norm(key), text):
                count("공장값과 같아 안 보냄")
                continue
            count(f"공장값과 다름({group})")
        else:  # 뺌·문맥은 안 보내고, 1-a·2는 아래 초안이 따로 고른다
            if group.startswith("1-a") or group == "2":
                extra[key] = group
            continue
        always[key] = text
    lines = [_line(key, values[key]) for key in sorted(always)]
    # 1-a·2 초안은 따로 담는다: 도우미가 설정(Settings.situation_lines·computed_lines)으로 넣고 빼며 효과를 가른다(HISTORY [270])
    situation = _situation_lines(values, extra, scope, target, always) if situations else []
    calculated = _computed_lines(values, extra, scope, always) if computed else []
    counts["1-a 초안 줄"], counts["2 초안 줄"] = len(situation), len(calculated)
    return {"always": lines, "situation": situation, "computed": calculated, "fields": _field_lines(values, tables, scope)}


# ---- 범위 ----


class _Scope:
    """이번 읽기의 주인·활성 항목·화면 자리(h11_patch.rule11, h12_patch.view_area). 열쇠가 범위 안인지 답한다."""

    def __init__(self, context, values, target, layer):
        scene = context.scene
        picked = sorted(layer.objects.selected, key=lambda item: item.name)[:SELECTED_LIMIT]
        self.object_roots = set()
        for item in picked + ([target] if target else []):
            self.object_roots.add(_id_label(item))
            if item.data:
                self.object_roots.add(_id_label(item.data))
        self.owners, self.actives = set(), {}
        self.target_roots = set()
        if target:
            self.target_roots = {_id_label(target)} | ({_id_label(target.data)} if target.data else set())
            self.owners |= self.target_roots
            if target.active_material:
                self.owners.add(_id_label(target.active_material))
            anim = target.animation_data
            if anim and anim.action:
                self.owners.add(_id_label(anim.action))
            if target.particle_systems.active:
                self.actives["particle_systems"] = target.particle_systems.active.name
                self.owners.add(_id_label(target.particle_systems.active.settings))
            shape_keys = getattr(target.data, "shape_keys", None)
            if shape_keys:
                self.owners.add(_id_label(shape_keys))
            for modifier in target.modifiers:
                if modifier.type == "NODES" and modifier.node_group:
                    self.owners.add(_id_label(modifier.node_group))
            material = target.active_material
            if material and material.node_tree:
                self.owners.update(_id_label(node.image) for node in material.node_tree.nodes if getattr(node, "image", None))
            if target.vertex_groups.active:
                self.actives["vertex_groups"] = target.vertex_groups.active.name
            slots = target.material_slots
            if 0 <= target.active_material_index < len(slots):
                self.actives["material_slots"] = slots[target.active_material_index].name or str(target.active_material_index)
            if target.type == "ARMATURE":
                bone = target.data.bones.active
                self.actives["bones"] = bone.name if bone else None
                edit = target.data.edit_bones.active if target.mode == "EDIT" else None
                self.actives["edit_bones"] = edit.name if edit else None
            if target.type == "GREASEPENCIL" and target.data.layers.active:
                self.actives["layers"] = target.data.layers.active.name
        self.paint_roots = set()
        if target and target.mode in MODE_PAINT:
            attr = MODE_PAINT[target.mode]
            self.paint_roots.add(f"{_id_label(scene)}.tool_settings.{attr}")
            brush = getattr(getattr(scene.tool_settings, attr, None), "brush", None)
            if isinstance(brush, bpy.types.ID):
                self.paint_roots.add(_id_label(brush))
        self.scene_root = _id_label(scene)
        self.world_root = _id_label(scene.world) if scene.world else None
        windows = context.window_manager.windows
        self.workspace_root = _id_label(windows[0].workspace) if len(windows) else None
        self.screen_root = _id_label(windows[0].screen) if len(windows) else None
        self.tool_root = f"{self.scene_root}.tool_settings"
        self.area_prefix = _view_area(windows)
        self.modifier_roots = tuple(f"{_id_label(target)}.{name}[" for name in ("modifiers", "constraints")) if target else ()

    def owned11(self, path, site):
        """rule11이 보내는 범위인가(요소·화면 칸은 부르는 쪽에서 이미 뺐다)."""
        kind = site.split(".")[0]
        if not _node_kept(path, site):
            return False
        if site in ALWAYS or (site in COMMON and (not _object_owned(path) or _under(path, self.object_roots))) or (path == self.scene_root and kind == "Scene"):
            return True
        if self.screen_root and kind == "View3DShading" and _under(path, {self.screen_root}):
            return True
        if self.workspace_root and _under(path, {self.workspace_root}) and kind in ("WorkSpace", "WorkSpaceTool"):
            return True
        if path == self.tool_root and kind == "ToolSettings":
            return True
        if _under(path, self.owners) and _items_active(path, self.actives):
            return True
        return bool(self.paint_roots) and _under(path, self.paint_roots)

    def in_scope(self, key, path):
        """rule13의 범위: rule11 범위, 활성 3D 화면, 장면, 월드."""
        site = key.rsplit("|", 1)[1]
        if self.owned11(path, site):
            return True
        if self.area_prefix and path.startswith(self.area_prefix):
            return True
        if path == self.scene_root or path.startswith(self.scene_root + "."):
            return True
        return bool(self.world_root) and (path == self.world_root or path.startswith(self.world_root + "."))

    def field_scope(self, path):
        """분야 묶음 칸을 읽는 주인: 활성 물체·그 데이터·주인 자료(활성 항목만), 장면·월드, 활성 3D 화면, 환경 설정."""
        if _under(path, self.owners):
            return _items_active(path, self.actives)
        if path == self.scene_root or path.startswith(self.scene_root + "."):
            return True
        if self.world_root and (path == self.world_root or path.startswith(self.world_root + ".")):
            return True
        if self.area_prefix and path.startswith(self.area_prefix):
            return True
        return path == "Preferences" or path.startswith("Preferences.")

    def modifier_cell(self, path):
        return bool(self.modifier_roots) and path.startswith(self.modifier_roots)

    def norm(self, key):
        """공장값 표의 열쇠 모양(h12_patch.norm)."""
        if self.area_prefix and key.startswith(self.area_prefix):
            rest = key[len(self.area_prefix):]
            return "<VIEW3D>" + re.sub(r"\.regions\[[^\]]*\]", ".regions[]", rest)
        return ID_LABEL.sub(r"\1", key, count=1)


def _view_area(windows):
    """활성 3D 화면: 첫 창 화면에서 가장 큰 VIEW_3D 칸의 자리 이름(h12_patch.view_area)."""
    if not len(windows):
        return None
    screen = windows[0].screen
    areas = [(index, area) for index, area in enumerate(screen.areas) if area.type == "VIEW_3D"]
    if not areas:
        return None
    index, _ = max(areas, key=lambda pair: pair[1].width * pair[1].height)
    return f"{_id_label(screen)}.areas[{index}]"


def _differs(tables, norm, text):
    """공장값과 다르면 참. 공장값을 모르는 칸과 흔들리는 칸은 참(h12_rule.Baseline.differs)."""
    loose = _strip_items(norm)
    if norm in tables["shaky"] or loose in tables["shaky"]:
        return True
    if norm in tables["exact"]:
        return text not in tables["exact"][norm]
    if loose in tables["loose"]:
        return text not in tables["loose"][loose]
    return True


def _strip_items(key):
    path, site = key.rsplit("|", 1)
    return re.sub(r"\[[^\]]*\]", "[]", path) + "|" + site


def _is_element(site):
    kind = site.split(".")[0]
    return bool(ELEMENT_MESH.match(kind)) or kind in ELEMENT_KINDS or kind.endswith("AttributeValue") or kind.endswith("Attribute") and kind != "Attribute"


def _not_sent(site):
    kind = site.split(".")[0].split("[")[0]
    return kind in SCREEN_KINDS or kind.startswith("Space") or kind in RECORD_KINDS or site in SCREEN_SITES or site in RECORD_SITES or "_OT_" in kind


def _node_kept(path, site):
    inside = ".node_tree" in path or re.match(r"^\w*NodeTree\[", path)
    return not inside or site.split(".")[-1] in NODE_PROPS


def _under(path, roots):
    return any(path == root or path.startswith(root + ".") for root in roots)


def _items_active(path, actives):
    return all(actives.get(segment) == name for segment, name in ITEM_SEGMENT.findall(path))


def _object_owned(path):
    return bool(OBJECT_ROOTS.match(path))


def _id_label(item):
    return f"{item.bl_rna.identifier}[{item.name_full}]"


# ---- 줄 만들기 ----


def _line(key, text):
    path, site = key.rsplit("|", 1)
    prop = site.split(".", 1)[1] if "." in site else site
    if site.startswith(path.split(".")[0].split("[")[0] + "["):  # 커스텀 속성 'Object["x"]'
        prop = site[site.index("["):]
        joined = f"{path}{prop}"
    else:
        joined = f"{path}.{prop}"
    shown = text if len(text) <= VALUE_CHARS else f"{text[:VALUE_CHARS]}…(총 {len(text)}자)"
    return f"{joined} = {shown}"


def _situations(context, target):
    """1-a 상황(h13_patch.situations와 같은 판정)."""
    found = []
    mode = target.mode if target else "OBJECT"
    kind = target.type if target else None
    if mode == "EDIT" and kind == "MESH":
        found.append("메시 편집")
    if kind == "ARMATURE" and mode in ("EDIT", "POSE"):
        found.append("뼈")
    if mode == "EDIT" and kind in ("CURVE", "SURFACE", "CURVES"):
        found.append("곡선 편집")
    if mode == "EDIT" and kind in ("LATTICE", "META"):
        found.append("격자·메타볼")
    if kind == "GREASEPENCIL":
        found.append("그리스 펜슬")
    if target and target.animation_data and target.animation_data.action:
        found.append("애니메이션")
    if target and (len(target.particle_systems) or any(m.type in ("CLOTH", "SOFT_BODY", "FLUID", "DYNAMIC_PAINT") for m in target.modifiers) or target.rigid_body):
        found.append("캐시")
    if mode.startswith(("SCULPT", "PAINT", "WEIGHT", "VERTEX", "TEXTURE")):
        found.append("조각·칠하기")
    windows = context.window_manager.windows
    if len(windows) and any(area.type == "NODE_EDITOR" for area in windows[0].screen.areas):
        found.append("노드 편집기")
    return found


def _situation_lines(values, extra, scope, target, taken):
    """초안: 지금 상황의 1-a 칸(활성 물체·데이터·도구 설정·주인 자료에서), 상황마다 SITUATION_CAP줄까지."""
    lines = []
    for name in _situations(bpy.context, target):
        groups = SITUATION_GROUPS[name]
        keys = [k for k, g in extra.items() if g in groups and k not in taken
                and (_under(k.rsplit("|", 1)[0], scope.owners | scope.paint_roots) or k.startswith(scope.tool_root) or k.startswith("BlendData|"))]
        lines += [_line(k, values[k]) for k in sorted(keys)[:SITUATION_CAP]]
    return lines


def _computed_lines(values, extra, scope, taken):
    """초안: 갈래 2(계산 값)를 활성 물체·그 데이터·장면에서, 모음 항목 안은 빼고(항목마다 늘어서), 모두 합쳐 COMPUTED_CAP줄까지."""
    roots = scope.target_roots | {scope.scene_root}

    def direct(path):
        return any(path == root or (path.startswith(root + ".") and "[" not in path[len(root):]) for root in roots)

    keys = [k for k, g in extra.items() if g == "2" and k not in taken and direct(k.rsplit("|", 1)[0])]
    return [_line(k, values[k]) for k in sorted(keys)[:COMPUTED_CAP]]


def _field_lines(values, tables, scope):
    """분야마다 그 묶음 칸의 지금 값 줄(공장값이어도). 요소 칸은 뺀다."""
    out = {code: [] for code in tables["bundles"]}
    by_site = {}
    for key in values:
        path, site = key.rsplit("|", 1)
        if _is_element(site) or not scope.field_scope(path) or any(part in path for part in FIXED_LISTS):
            continue
        by_site.setdefault(site, []).append(key)
    for code, sites in tables["bundles"].items():
        keys = sorted(key for site in sites for key in by_site.get(site, ()))
        out[code] = [_line(key, values[key]) for key in keys]
    return out


# ---- 값 읽기(op_walk_v7_주소만.snapshot에서 옮김) ----


def _number(value):
    if isinstance(value, float):
        return round(value, 6) if math.isfinite(value) else str(value)
    return value


def _plain(value):
    if isinstance(value, (bool, int, float, str)) or value is None:
        return _number(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    try:
        return [_plain(v) for v in value]
    except TypeError:
        return str(type(value).__name__)


def _label(struct, parent, via, index):
    if isinstance(struct, bpy.types.ID) and not struct.is_embedded_data:
        return f"{struct.bl_rna.identifier}[{struct.name_full}]"
    if index is None:
        return f"{parent}.{via}"
    name = getattr(struct, "name", None)
    return f"{parent}.{via}[{name if isinstance(name, str) and name else index}]"


def snapshot():
    """원본 자료·창·설정에서 닿는 값을 '자리|타입.칸' → repr(값 글)로(7판, 키맵 뺌). 공장값 표와 같은 모양이다."""
    seen, heap, order, values = set(), [], itertools.count(), {}
    in_mode = getattr(bpy.context, "objects_in_mode", None)
    if in_mode is None:
        in_mode = [o for o in bpy.data.objects if o.mode not in ("OBJECT", "POSE")]
    for obj in in_mode:  # 편집 모드 값은 이렇게 내보내야 obj.data에 보인다(연구 도구와 같음)
        try:
            obj.update_from_editmode()
        except (RuntimeError, ReferenceError):
            pass
    viewports = [area.spaces.active for window in bpy.context.window_manager.windows for area in window.screen.areas if area.type == "VIEW_3D"]

    def call_state(struct, type_name, path, fn, *args, label_=None):
        site = f"{type_name}.{label_ or fn}()"
        try:
            values[f"{path}|{site}"] = repr(getattr(struct, fn)(*args))
        except RuntimeError:
            if fn == "local_view_get":
                values[f"{path}|{site}"] = "로컬 뷰 아님"
        except (ReferenceError, TypeError):
            pass

    def read_custom(struct, type_name, path):
        try:
            keys = struct.keys()
        except TypeError:
            return
        for key in keys:
            value = struct[key]
            if hasattr(value, "to_dict"):
                value = value.to_dict()
            elif hasattr(value, "to_list"):
                value = value.to_list()
            elif isinstance(value, bpy.types.bpy_struct):
                value = (value.bl_rna.identifier, getattr(value, "name", ""))
            values[f'{path}|{type_name}["{key}"]'] = repr(value)

    def push(struct, path, hops):
        try:
            key = (struct.as_pointer(), struct.bl_rna.identifier)
        except (AttributeError, ReferenceError, TypeError):
            return
        if key not in seen:
            heapq.heappush(heap, (hops, path, next(order), struct, key))

    def read(owner, prop, owner_type, path, follow, hops):
        name = prop.identifier
        site = f"{owner_type}.{name}"
        if name in NEVER or site in SKIP_SITES or site == "WindowManager.keyconfigs":
            return
        try:
            value = getattr(owner, name)
            kind = prop.type
            if kind == "POINTER":
                if value is None:
                    text = "없음"
                elif isinstance(value, bpy.types.ID) and not value.is_embedded_data:
                    text = value.name_full
                else:
                    text = f"{value.bl_rna.identifier}:{getattr(value, 'name', '')}"
                if value is not None and follow and not name.startswith("active"):
                    push(value, _label(value, path, name, None), hops + 1)
            elif kind == "COLLECTION" and _is_element(f"{getattr(prop.fixed_type, 'identifier', '')}.x"):
                # 점·면·속성 값 같은 요소 모음은 항목을 따라가지 않고 개수만 적는다. 요소 칸은 어차피 보내지 않고(_is_element),
                # 따라가면 점 100만 개 메시에서 1분 넘게 멈췄다(2026-11-10 자체 시험에서 실행으로 확인)
                text = len(value)
            elif kind == "COLLECTION":
                items = list(value)
                if follow:
                    text = len(items)
                    used = set()
                    for index, item in enumerate(items):
                        if isinstance(item, bpy.types.bpy_struct):
                            where = _label(item, path, name, index)
                            if where in used:
                                where = f"{where}#{index}"
                            used.add(where)
                            push(item, where, hops)
                    wrapper = prop.srna
                    if wrapper is not None:
                        for sub in wrapper.properties:
                            if sub.identifier != "rna_type":
                                read(value, sub, wrapper.identifier, f"{path}.{name}", False, hops)
                else:
                    text = sorted(getattr(item, "name", "") for item in items)
            else:
                text = _plain(value)
        except (AttributeError, RuntimeError, TypeError, ReferenceError, ValueError, KeyError, IndexError):
            return
        values[f"{path}|{site}"] = repr(text)

    push(bpy.data, "BlendData", 0)
    push(bpy.context.window_manager, _label(bpy.context.window_manager, "", "", 0), 0)
    push(bpy.context.preferences, "Preferences", 0)
    while heap:
        hops, path, _, struct, key = heapq.heappop(heap)
        if key in seen:
            continue
        seen.add(key)
        try:
            type_name = struct.bl_rna.identifier
        except ReferenceError:
            continue
        if isinstance(struct, bpy.types.Object):
            for fn in ("select_get", "hide_get", "visible_get", "holdout_get", "indirect_only_get"):
                call_state(struct, "Object", path, fn)
            for index, space in enumerate(viewports):
                call_state(struct, "Object", path, "local_view_get", space, label_=f"local_view_get[{index}]")
                call_state(struct, "Object", path, "visible_in_viewport_get", space, label_=f"visible_in_viewport_get[{index}]")
        elif isinstance(struct, bpy.types.LayerCollection):
            call_state(struct, "LayerCollection", path, "visible_get")
            call_state(struct, "LayerCollection", path, "has_objects")
            call_state(struct, "LayerCollection", path, "has_selected_objects", bpy.context.view_layer)
        read_custom(struct, type_name, path)
        for prop in struct.bl_rna.properties:
            read(struct, prop, type_name, path, True, hops)
    return values
