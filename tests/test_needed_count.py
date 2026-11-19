"""필요 내용 세기 도구(.claude/tools/needed_count.py, 04 지표 2). 조각·목록·보낸 글은 모두 지어낸 작은 것이다."""

import importlib.util
import json
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / ".claude" / "tools" / "needed_count.py"
spec = importlib.util.spec_from_file_location("needed_count", TOOL)
count = importlib.util.module_from_spec(spec)
spec.loader.exec_module(count)

TEXTS = {"a.html#x": ["A 조각 글"], "b.html#y": ["B 앞 조각", "B 뒤 조각"], "c.html#z": ["C 조각 글"]}


def test_조각_글이_보낸_글에_그대로_있으면_넘어간_주소다():
    sent = "# 설명서 내용\n\nA 조각 글\n\n---\n\nB 뒤 조각\n\n# 질문\n\n어떻게?"
    assert count.present(sent, set(TEXTS), TEXTS) == {"a.html#x", "b.html#y"}  # 나눈 조각은 하나만 와도 됨


def test_묶음은_대안_하나만_와도_채우고_묶음이_모두_차야_다_넘어감이다():
    assert count.passed([["a.html#x", "c.html#z"], ["b.html#y"]], {"c.html#z", "b.html#y"}) == (True, 2)
    assert count.passed([["a.html#x"], ["b.html#y"]], {"a.html#x"}) == (False, 1)


def test_판_폴더는_필요_목록이_빈_차례를_세지_않고_보낸_글_없는_차례를_표시한다(tmp_path):
    rows = [{"번호": "Q01", "보낸 글": [{"role": "user", "content": "A 조각 글"}]},
            {"번호": "Q02", "보낸 글": [{"role": "user", "content": "아무것도"}]},
            {"번호": "Q03", "보낸 글": None}]
    (tmp_path / "호출.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
    needed = {"Q01": [["a.html#x"]], "Q02": [], "Q03": [["c.html#z"]]}
    assert count.run_count(needed, TEXTS, tmp_path) == [
        {"번호": "Q01", "다 넘어감": True, "채운 묶음": 1, "묶음": 1, "넘어간 주소": ["a.html#x"]},
        {"번호": "Q03", "보낸 글 없음": True},
    ]
