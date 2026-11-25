"""설명서 바로잡기 줄: 설명서 글이 Blender 5.2 화면·동작과 다른 곳을 확인한 사실만 담백하게 고친 한 줄(HISTORY [687]·[690]).

답 모델에 보내는 설명서 글에서 바로잡을 청크 글 바로 아래에 붙인다. 청크 파일·임베딩·리랭킹 글은 그대로 둔다.
줄마다 근거는 results/20261123/115637_설명서대조_후보확인/바로잡기목록.jsonl의 같은 번호 줄(확인한 판·방법)이다.
목록 47줄에서 구두점·대소문자·"Import/Export" 줄임만 다른 줄(C001·C046·C171-C174)은 뺐다(실험 기록 "개정 차례 8번").
"""

from blender_tutor.manual_chunks import Chunk

# (번호, 소제목 주소, 청크에서 찾을 설명서 원문 일부, 붙일 줄)
ERRATA: tuple[tuple[str, str, str, str], ...] = (
    ("C002", "animation/armatures/bones/editing/delete.html#dissolve", "Armature ‣ Delete ‣ Dissolve",
     "위 글의 메뉴 Armature > Delete > Dissolve는 Armature > Delete > Dissolve Bones이다."),
    ("C012", "animation/armatures/posing/editing/flip_quats.html#flip-quats", "Pose ‣ Flip Quats",
     "위 글의 메뉴 Pose > Flip Quats는 Pose > Flip Quaternions이다."),
    ("C031", "editors/graph_editor/channels/editing.html#move", "Channel ‣ Move…",
     "위 글의 메뉴 Channel > Move…는 Channel > Move Channels이다."),
    ("C050", "grease_pencil/modes/edit/grease_pencil_menu.html#split", "Shortcut: V",
     "위 글의 Split 단축키 V는 Shift-V이다."),
    ("C051", "grease_pencil/modes/edit/grease_pencil_menu.html#clean-loose-points", "Grease Pencil ‣ Clean Up ‣ Delete Loose Points",
     "위 글의 메뉴 Grease Pencil > Clean Up > Delete Loose Points는 Grease Pencil > Clean Up > Clean Loose Points이다."),
    ("C052", "grease_pencil/modes/edit/grease_pencil_menu.html#reproject-strokes", "Grease Pencil ‣ Clean Up ‣ Reproject",
     "위 글의 메뉴 Grease Pencil > Clean Up > Reproject는 Grease Pencil > Clean Up > Reproject Strokes이다."),
    ("C054", "grease_pencil/modes/edit/selecting.html#select-alternated", "Select ‣ Select Alternated",
     "위 글의 메뉴 Select > Select Alternated는 Select > Select Alternate이다."),
    ("C056", "grease_pencil/modes/edit/stroke_menu.html#simplify", "Stroke ‣ Simplify",
     "위 글의 메뉴 Stroke > Simplify는 Stroke > Simplify Stroke이다."),
    ("C057", "grease_pencil/modes/edit/stroke_menu.html#bpy-ops-grease-pencil-join-selection", "Stroke ‣ Join ‣ Join,",
     "위 글의 메뉴 Stroke > Join > Join은 Stroke > Join > Join Strokes이다."),
    # C059는 C058과 같은 청크·같은 원문이라 한 줄로 합쳤다.
    ("C058", "grease_pencil/modes/edit/stroke_menu.html#join-and-copy", "Stroke ‣ Join ‣ Join and Copy",
     "위 글의 메뉴 Stroke > Join > Join and Copy는 Stroke > Join > Split and Copy이다."),
    ("C060", "grease_pencil/modes/edit/stroke_menu.html#set-as-active-material", "Stroke ‣ Set as Active Material",
     "위 글의 메뉴 Stroke > Set as Active Material은 Stroke > Set Active Material이다."),
    # C061(Set Curve Type → Convert Type)은 목록에 "추정 짝짓기"로 적혀 확인한 사실이 아니라 넣지 않는다.
    ("C062", "interface/controls/nodes/editing.html#delete-with-reconnect", "Menu: Node ‣ Delete",
     "위 글의 메뉴 Node > Delete는 Node > Delete with Reconnect이다."),
    ("C063", "interface/controls/nodes/editing.html#collapse", "Node ‣ Show/Hide ‣ Unconnected Sockets",
     "위 글의 메뉴 Node > Show/Hide > Unconnected Sockets는 Node > Show/Hide > Collapse이다."),
    ("C064", "interface/controls/nodes/editing.html#collapse-and-hide-unused-sockets", "Node ‣ Show/Hide ‣ Unconnected Sockets",
     "위 글의 메뉴 Node > Show/Hide > Unconnected Sockets는 Node > Show/Hide > Collapse and Hide Unused Sockets이고, 기본 단축키는 없다."),
    ("C065", "interface/window_system/areas.html#maximize-area", "View ‣ Area ‣ Toggle Maximize Area",
     "위 글의 메뉴 View > Area > Toggle Maximize Area는 View > Area > Maximize Area이다."),
    ("C072", "modeling/curves_new/selecting.html#select-endpoints", "Select ‣ Select Endpoints",
     "위 글의 메뉴 Select > Select Endpoints는 Select > Endpoints이다."),
    ("C082", "modeling/meshes/selecting/loops.html#select-loop-inner-region", "Select ‣ Select Loops ‣ Select Loop Inner-Region",
     "위 글의 메뉴 Select > Select Loops > Select Loop Inner-Region은 Select > Select Loops > Loop Inner-Region이다."),
    ("C083", "modeling/meshes/selecting/loops.html#boundary-of-selection", "Select ‣ Select Loops ‣ Boundary of Selection",
     "위 글의 메뉴 Select > Select Loops > Boundary of Selection은 Select > Select Loops > Boundary of Selected이다."),
    ("C084", "modeling/meshes/selecting/more_less.html#select-more", "Select ‣ Select More/Less ‣ More",
     "위 글의 하위 메뉴 이름 Select More/Less는 More/Less이다."),
    ("C085", "modeling/meshes/selecting/more_less.html#select-less", "Select ‣ Select More/Less ‣ Less",
     "위 글의 하위 메뉴 이름 Select More/Less는 More/Less이다."),
    ("C086", "modeling/meshes/selecting/more_less.html#select-next-active", "Select ‣ Select More/Less ‣ Next Active",
     "위 글의 하위 메뉴 이름 Select More/Less는 More/Less이다."),
    ("C087", "modeling/meshes/selecting/more_less.html#select-previous-active", "Select ‣ Select More/Less ‣ Previous Active",
     "위 글의 하위 메뉴 이름 Select More/Less는 More/Less이다."),
    ("C088", "modeling/meshes/selecting/sharp_edges.html#select-sharp-edges", "Select ‣ Select Sharp Edges",
     "위 글의 메뉴 Select > Select Sharp Edges는 Select > Sharp Edges이다."),
    ("C089", "modeling/meshes/selecting/similar.html#select-similar", "Menu: Select ‣ Similar",
     "위 글의 메뉴 Select > Similar는 Select > Select Similar이다."),
    ("C090", "modeling/meshes/selecting/similar.html#face-regions", "Select ‣ Similar ‣ Face Regions",
     "위 글의 메뉴 Select > Similar > Face Regions는 Select > Select Similar > Face Regions이다."),
    ("C102", "movie_clip/tracking/clip/editing/clip.html#open-clip", "Clip ‣ Open Clip",
     "위 글의 메뉴 Clip > Open Clip은 Clip > Open...이다."),
    ("C103", "movie_clip/tracking/clip/editing/clip.html#reload-clip", "Clip ‣ Open Clip",
     "위 글의 메뉴 Clip > Open Clip은 Clip > Reload Clip이다."),
    ("C159", "scene_layout/object/editing/constraints.html#add-constraint-with-targets", "Object ‣ Constraint ‣ Add Constraint (with Targets)",
     "위 글의 메뉴 Object > Constraint는 Object > Constraints이다."),
    ("C160", "scene_layout/object/editing/constraints.html#copy-constraints-to-selected-objects", "Object ‣ Constraint ‣ Copy Constraints to Selected Objects",
     "위 글의 메뉴 Object > Constraint는 Object > Constraints이다."),
    ("C162", "scene_layout/object/editing/delete.html#delete-globally", "Object ‣ Delete Globally",
     "위 글의 메뉴 Object > Delete Globally는 Object > Delete Global이다."),
    ("C175", "video_editing/edit/montage/editing.html#toggle-retiming-keys", "Strip ‣ Retiming ‣ Toggle Retiming Keys",
     "위 글의 메뉴 Strip > Retiming > Toggle Retiming Keys는 Strip > Retiming > Show Retiming Keys이다."),
    ("C180", "editors/preferences/save_load.html#blend-files", "with the default setting of 2",
     "위 글의 Save Versions 기본값 2는 1이다."),
    ("C181", "files/import_export/fbx_legacy.html#id15", "10 is the default",
     "위 글의 Scale 기본값 10은 1.0이다."),
    ("R009", "render/cycles/light_settings.html#settings", "By default lights use only direct light sampling.",
     "위 글과 달리 Multiple Importance Sample은 기본으로 켜져 있다."),
    ("R045", "render/shader_nodes/shader/metallic.html#id2", "2.757, 2.512, 2.231",
     "위 글의 Titanium IOR 2.757, 2.512, 2.231은 2.757, 2.513, 2.231이다."),
    ("R051", "interface/controls/templates/color_picker.html#notes", "The color picker displays the color as it appears in the current view transform",
     "위 글과 달리 색 고르기의 색은 View Transform을 반영하지 않는다."),
    ("R048", "render/shader_nodes/textures/environment.html#properties", "For most color textures the default of Color should be used",
     "위 글의 Color Space 기본값 Color는 sRGB이고, 목록에 Color는 없다."),
    ("R019", "render/eevee/limitations/nodes_support.html#input-nodes", "Ray Length: Not supported. Defaults to 1.0.",
     "위 글과 달리 EEVEE의 Ray Length는 1.0으로 고정되지 않고 카메라 거리에 따라 달라진다."),
    ("R044", "render/shader_nodes/shader/metallic.html#id1", "0.617, 0.576, 0.540",
     "위 글의 Titanium Base Color 0.617, 0.576, 0.540은 0.617, 0.577, 0.540이다."),
)


def with_errata(chunk: Chunk) -> str:
    """답 모델에 보낼 청크 글: 바로잡을 곳이 있으면 글 바로 아래에 그 줄을 붙인다."""
    lines = [line for _, address, original, line in ERRATA if address == chunk.address and original in chunk.text]
    return "\n\n".join([chunk.text, *lines])
