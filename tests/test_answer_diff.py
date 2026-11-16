"""바꾸기 전후 문장 도구(.claude/tools/answer_diff.py, HISTORY [370]·[371]). 저장된 답 없이 돈다."""

import importlib.util
import random
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / ".claude" / "tools" / "answer_diff.py"
spec = importlib.util.spec_from_file_location("answer_diff", TOOL)
answer_diff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(answer_diff)


def test_조각으로_나누면_원래_글이_되고_조각은_1에서_12자():
    text = "옆면 개수(Vertices) 값을 바꿉니다. " * 20
    for seed in (1, 2, 3):
        parts = answer_diff.pieces(text, seed)
        assert "".join(parts) == text
        assert all(1 <= len(p) <= 12 for p in parts)


def test_같은_씨앗은_같게_나눈다():
    assert answer_diff.pieces("가나다라마바사아자차카타파하" * 5, 7) == answer_diff.pieces("가나다라마바사아자차카타파하" * 5, 7)


def test_바뀐_자리만_앞뒤_글과_함께_뽑는다():
    before = "먼저 Scale을 누르고 그다음 확인합니다."
    after = "먼저 크기(Scale)를 누르고 그다음 확인합니다."
    got = answer_diff.spots(before, after, around=5)
    assert len(got) == 1
    assert "Scale을" in got[0]["전"] and "크기(Scale)를" in got[0]["후"]


def test_같은_글이면_바뀐_자리가_없다():
    assert answer_diff.spots("그대로입니다.", "그대로입니다.") == []


def test_떨어진_두_자리는_따로_뽑는다():
    before = "Scale을 누릅니다. " + "가" * 60 + " Rotation을 누릅니다."
    after = "크기(Scale)를 누릅니다. " + "가" * 60 + " 회전(Rotation)을 누릅니다."
    assert len(answer_diff.spots(before, after, around=5)) == 2


def test_같은_전후는_하나로_묶고_수와_문항을_센다():
    rows = [
        {"번호": "Q01", "전": "a", "후": "b"},
        {"번호": "Q02", "전": "a", "후": "b"},
        {"번호": "Q03", "전": "c", "후": "d"},
    ]
    got = answer_diff.group(rows)
    assert got[0] == {"전": "a", "후": "b", "수": 2, "번호": ["Q01", "Q02"]}
    assert got[1]["수"] == 1


def test_흐름_대조는_조각마다_다르게_나온_것을_센다():
    # 가짜 바꾸기: 한 번에 넣으면 같지만 조각으로 넣으면 "AB"를 못 잡는다
    def whole(parts):
        return "".join(parts).replace("AB", "X") if len(parts) == 1 else "".join(parts)

    def same(parts):
        return "".join(parts).replace("AB", "X")

    text = "가나AB다라" * 10
    assert answer_diff.stream_mismatch(text, same) == 0
    assert answer_diff.stream_mismatch(text, whole) == 3


def test_없는_자료_폴더는_조용히_넘기지_않고_알린다(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        list(answer_diff.read_sources(tmp_path, [("원문", "없는/폴더/원문.jsonl", "원문")]))


def test_자료_줄을_출처와_번호와_글로_읽는다(tmp_path):
    folder = tmp_path / "가"
    folder.mkdir()
    (folder / "답.jsonl").write_text('{"번호": "Q01", "답": "글"}\n\n{"번호": "Q02", "답": null}\n', encoding="utf-8")
    got = list(answer_diff.read_sources(tmp_path, [("저장:가", "가/답.jsonl", "답")]))
    assert got == [("저장:가", "Q01", "글"), ("저장:가", "Q02", "")]
