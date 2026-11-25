"""설명서 바로잡기 줄(manual_errata): 바로잡을 청크에만 줄이 붙는지."""

from blender_tutor.manual_chunks import Chunk
from blender_tutor.manual_errata import ERRATA, with_errata

# 설명서 FBX (Legacy) 내보내기 Transform 소제목을 줄인 청크(지어낸 본문, 원문 일부만 실제 설명서 글)
FBX = Chunk(
    "files/import_export/fbx_legacy", "id15", "files", "files/import_export", "FBX (Legacy)", ("Export", "Transform"),
    "Scale\n\nScale the exported data by this value. 10 is the default because this fits best.",
)


def test_line_goes_right_below_the_chunk_text():
    assert with_errata(FBX) == FBX.text + "\n\n위 글의 Scale 기본값 10은 1.0이다."


def test_same_address_without_the_original_text_is_left_alone():
    other = Chunk(FBX.page_path, FBX.anchor, FBX.field, FBX.group, FBX.page_title, FBX.headings, "Forward / Up")
    assert with_errata(other) == other.text


def test_other_address_with_the_original_text_is_left_alone():
    other = Chunk("files/import_export/obj", "id15", "files", "files/import_export", "OBJ", (), FBX.body)
    assert with_errata(other) == other.text


def test_every_line_is_a_plain_sentence_about_the_text_above():
    # 담백한 꼴(HISTORY [687]): "위 글"을 가리키고 마침표로 끝나는 한 줄. 판 번호나 머리표를 붙이지 않는다.
    for number, _, original, line in ERRATA:
        assert line.startswith("위 글") and line.endswith("다.") and "\n" not in line, number
        assert "5.2" not in line and "[" not in line, number
        assert original, number
