"""답 글에서 기계로 셀 수 있는 지표(docs/plan/01 C, HISTORY [459]). 돈 안 듦, 모델 호출 없음.

채점 없이 무엇이 효과였는지 가르려고, Blender 자체 자료(메뉴 나무·기본 키맵)와 답 글만 보고 센다. 개발 문항의 질문·정답은 규칙에 넣지 않는다.

지표(답 하나마다):
1. 메뉴 길: 원문의 [[ ]] 가운데 '>'(또는 '‣')로 단이 나뉜 것을 메뉴 나무와 맞댄다.
   있음 / 있음(앞 생략: 나무의 어느 길 끝부분과 같음) / 나무와 다름(첫 단 글자가 나무의 어느 단으로든 나오는데 이 길은 없음) / 나무에 없음(첫 단이 나무에 없음.
   메뉴 나무는 3D 뷰 머리 메뉴의 물체·메시 편집 두 모드뿐이라 다른 편집기·속성 창 길은 여기로 간다. 틀린 길이라고 단정하지 않는다).
2. 단축키: 원문의 보조 키 조합(Ctrl·Shift·Alt·Cmd + 키)을, 같은 문장에서 가장 가까운 [[ ]] 이름이 가리키는 조작의 기본 키맵과 맞댄다.
   맞음 / 기본 키맵과 다름 / 가를 수 없음(이름이 없거나 메뉴 나무에서 조작을 못 찾음, 마우스 등 키 이름을 모름).
   이름 → 조작은 메뉴 나무의 끝 단 글자로만 찾는다(메뉴면 그 메뉴를 여는 wm.call_menu 항목). linux·darwin 두 표 가운데 하나에 있으면 맞음.
4. 코드 이름(snake_case 낱말, bpy.)과 마크다운 기호(**, 줄 머리 #, 백틱)가 화면 답에 드러난 수.
5. 설정 이름 말하기(좁은 정의): 화면 답에서 상태를 말하는 문장(지금·현재·켜져·꺼져·되어 있·상태)에 든 코드 이름 가운데,
   모델이 받은 설정 줄과 작업 상태 어디에도 없는 것. 한국어로 풀어 말한 설정은 못 센다(한계).
6. 답 길이(화면 답 글자 수).
지표 3(영어로만 남은 이름)은 data/eval/dev50/english_names_count.py가 따로 센다.

연습 과정 파일의 `메뉴:` 칸도 같은 나무로 맞댄다(docs/plan/01 D, '메뉴: 없음'은 건너뜀): 
  .venv/bin/python -I .claude/tools/answer_facts.py courses <출력 파일 .md> <paths.json> <courses 폴더>

실행: .venv/bin/python -I .claude/tools/answer_facts.py <출력 폴더> <paths.json> <keymap.json> <답 묶음 JSONL>
답 묶음 한 줄: {"열쇠", "원문"([[ ]]가 든 모델 원문), "답"(화면 답), "판정", "채점 이유", "보낸 설정 줄"(목록, 없으면 빈 목록)}.
쓰는 것: <출력 폴더>/답별.jsonl, 표.md. 출력 폴더가 이미 있으면 멈춘다.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

MOD = r"(?:Ctrl|Control|Shift|Alt|Option|Opt|Cmd|Command)"
COMBO = re.compile(rf"(?<![A-Za-z]){MOD}(?:\s*[-+]\s*{MOD})*\s*[-+]\s*(?P<key>F\d{{1,2}}|[A-Za-z0-9]+)(?![A-Za-z0-9])")
MARK = re.compile(r"\[\[(.+?)\]\]")
MODS = {"ctrl": "ctrl", "control": "ctrl", "shift": "shift", "alt": "alt", "option": "alt", "opt": "alt", "cmd": "oskey", "command": "oskey"}
NAMED = {"tab": "TAB", "enter": "RET", "return": "RET", "esc": "ESC", "space": "SPACE", "delete": "DEL", "del": "DEL",
         "backspace": "BACK_SPACE", "home": "HOME", "end": "END"}
DIGITS = ["ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"]
SENTENCE = re.compile(r"(?<=[.?!])\s+|\n")
# 한글도 \w라 \b를 쓰지 않는다("use_x가"에서 끝을 못 찾음)
CODE = re.compile(r"(?<![A-Za-z0-9_.])(?:bpy\.[A-Za-z0-9_.]+|[a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?![A-Za-z0-9_])")
STATE_WORDS = re.compile(r"지금|현재|켜져|꺼져|되어 있|돼 있|상태")


def _plain(segment: str) -> str:
    return " ".join(segment.replace("…", "").replace("...", "").split()).lower()


def _segments(path: str) -> tuple[str, ...]:
    return tuple(_plain(part) for part in re.split(r"[>‣]", path))


class Tree:
    """메뉴 나무(paths.json: 모드 → [경로 글, "op"|"menu", 조작 이름|메뉴 클래스])."""

    def __init__(self, paths: dict):
        rows = [row for mode in paths.values() for row in mode]
        self.paths = {_segments(path) for path, _, _ in rows}
        self.words = {segment for path in self.paths for segment in path}
        self.targets: dict[str, set[tuple[str, str]]] = {}  # 끝 단 글자 → {(종류, 이름)}
        for path, kind, name in rows:
            self.targets.setdefault(_segments(path)[-1], set()).add((kind, name))

    def judge(self, mark: str) -> str:
        path = _segments(mark)
        if path in self.paths:
            return "있음"
        if any(len(known) > len(path) and known[-len(path):] == path for known in self.paths):
            return "있음(앞 생략)"
        return "나무와 다름" if path[0] in self.words else "나무에 없음"


def _key(text: str) -> tuple[frozenset[str], str] | None:
    """'Ctrl+Shift+N' → ({ctrl, shift}, 'N'). 키 이름을 모르면 None."""
    match = COMBO.fullmatch(text.strip())
    key = match.group("key")
    mods = frozenset(MODS[word.lower()] for word in re.findall(MOD, text[: match.start("key")]))
    if len(key) == 1:
        return mods, DIGITS[int(key)] if key.isdigit() else key.upper()
    if re.fullmatch(r"F\d{1,2}", key):
        return mods, key.upper()
    return (mods, NAMED[key.lower()]) if key.lower() in NAMED else None


def _pressed(item: dict, mods: frozenset[str], key: str) -> bool:
    if item["type"] != key:
        return False
    if item.get("any"):
        return True
    return all(item[name] == -1 or bool(item[name]) == (name in mods) for name in ("ctrl", "alt", "shift", "oskey"))


class Keymap:
    """기본 키맵(keymap.json: "linux"·"darwin" → 항목 목록)."""

    def __init__(self, keymap: dict):
        self.items = [item for platform in keymap.values() for item in platform]

    def matches(self, targets: set[tuple[str, str]], mods: frozenset[str], key: str) -> bool:
        for item in self.items:
            if not _pressed(item, mods, key):
                continue
            for kind, name in targets:
                if kind == "op" and item["idname"] == name:
                    return True
                if kind == "menu" and item["idname"] in ("wm.call_menu", "wm.call_menu_pie") and item.get("props", {}).get("name") == name:
                    return True
        return False


def menu_paths(raw: str, tree: Tree) -> list[dict]:
    return [{"길": mark, "판정": tree.judge(mark)} for mark in MARK.findall(raw) if re.search(r"[>‣]", mark)]


def shortcuts(raw: str, tree: Tree, keymap: Keymap) -> list[dict]:
    found = []
    for sentence in SENTENCE.split(raw):
        marks = [(m.start(), m.end(), m.group(1)) for m in MARK.finditer(sentence)]
        for combo in COMBO.finditer(sentence):
            parsed = _key(combo.group())
            # 키 앞뒤로 글자 거리가 가장 가까운 표시(같으면 앞)
            gap = lambda mark: combo.start() - mark[1] if mark[1] <= combo.start() else max(0, mark[0] - combo.end())
            names = [mark for mark in marks if mark[1] <= combo.start() or mark[0] >= combo.end()]  # 키를 감싼 표시([[Alt-C]])는 이름이 아니다
            near = min(names, key=lambda mark: (gap(mark), mark[0] > combo.start()), default=None)
            name = near[2] if near else None
            targets = tree.targets.get(_segments(name)[-1], set()) if name else set()
            if parsed is None:
                verdict = "가를 수 없음(키 이름 모름)"
            elif not targets:
                verdict = "가를 수 없음(조작 못 찾음)"
            else:
                verdict = "맞음" if keymap.matches(targets, *parsed) else "기본 키맵과 다름"
            found.append({"키": combo.group(), "이름": name, "판정": verdict})
    return found


def code_marks(shown: str) -> dict[str, int]:
    return {"코드 이름": len(CODE.findall(shown)), "**": shown.count("**"), "줄 머리 #": len(re.findall(r"(?m)^\s*#", shown)),
            "백틱": shown.count("`")}


def unsent_names(shown: str, sent: list[str]) -> list[str]:
    """상태를 말하는 문장의 코드 이름 가운데 보낸 설정 줄에 없는 것(좁은 정의, 한국어로 풀어 말한 설정은 못 셈)."""
    known = "\n".join(sent)
    found = []
    for sentence in SENTENCE.split(shown):
        if STATE_WORDS.search(sentence):
            found += [name for name in CODE.findall(sentence) if name.split(".")[-1] not in known]
    return found


def measure(row: dict, tree: Tree, keymap: Keymap) -> dict:
    shown = row["답"] or ""
    return {
        "열쇠": row["열쇠"], "판정": row["판정"],
        "메뉴 길": menu_paths(row["원문"] or "", tree), "단축키": shortcuts(row["원문"] or "", tree, keymap),
        "코드·기호": code_marks(shown), "보낸 줄에 없는 설정 이름": unsent_names(shown, row.get("보낸 설정 줄") or []),
        "길이": len(shown),
    }


# 채점 이유에서 "같은 까닭으로 깎았나"를 보는 낱말(도구 규칙을 고정할 때 정함, 채점 이유를 읽기 전)
REASON = {"메뉴 길": re.compile(r"메뉴|경로"), "단축키": re.compile(rf"단축키|{MOD}\s*[-+]")}
CAUGHT = {"메뉴 길": ("나무와 다름",), "단축키": ("기본 키맵과 다름",)}


def table(rows: list[dict], reasons: dict[str, str]) -> list[str]:
    """지표마다 잡은 답 수, 그중 틀림·부분이면서 채점 이유에 같은 까닭 낱말이 있는 답, 맞음 답에서 잡은 수."""
    verdicts = Counter(row["판정"] for row in rows)
    lines = [f"- 답 {len(rows)}개(판정 {dict(verdicts)})", "",
             "| 지표 | 잡은 답 | 그중 틀림·부분이고 채점 이유에 같은 까닭 낱말 | 맞음 답에서 잡은 수 | 잡은 것(건) |", "|---|---|---|---|---|"]
    for name in ("메뉴 길", "단축키"):
        caught = [row for row in rows if any(item["판정"] in CAUGHT[name] for item in row[name])]
        same = [row for row in caught if row["판정"] != "맞음" and REASON[name].search(reasons[row["열쇠"]])]
        counts = Counter(item["판정"] for row in rows for item in row[name])
        lines.append(f"| {name}({CAUGHT[name][0]}) | {len(caught)} | {len(same)} | {sum(row['판정'] == '맞음' for row in caught)} | {dict(counts)} |")
    for name, test in (("코드 이름", lambda r: r["코드·기호"]["코드 이름"]), ("마크다운 기호", lambda r: r["코드·기호"]["**"] + r["코드·기호"]["줄 머리 #"] + r["코드·기호"]["백틱"]),
                       ("보낸 줄에 없는 설정 이름", lambda r: len(r["보낸 줄에 없는 설정 이름"]))):
        caught = [row for row in rows if test(row)]
        lines.append(f"| {name} | {len(caught)} | - | {sum(row['판정'] == '맞음' for row in caught)} | {sum(test(row) for row in rows)} |")
    lengths = sorted(row["길이"] for row in rows)
    by = {verdict: sorted(row["길이"] for row in rows if row["판정"] == verdict) for verdict in verdicts}
    lines += ["", f"- 답 길이(글자): 중앙 {lengths[len(lengths) // 2]}, 판정별 중앙 "
              + ", ".join(f"{v} {ls[len(ls) // 2]}" for v, ls in by.items())]
    return lines


def main(out: Path, paths: Path, keymap: Path, answers: Path) -> None:
    tree, keys = Tree(json.loads(paths.read_text(encoding="utf-8"))), Keymap(json.loads(keymap.read_text(encoding="utf-8")))
    data = [json.loads(line) for line in answers.read_text(encoding="utf-8").splitlines() if line.strip()]
    out.mkdir(parents=True)
    rows = [measure(row, tree, keys) for row in data]
    with (out / "답별.jsonl").open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    reasons = {row["열쇠"]: row.get("채점 이유") or "" for row in data}
    (out / "표.md").write_text("\n".join(["# 기계 지표", "", f"- 자료: `{answers}`, 메뉴 나무 `{paths}`, 기본 키맵 `{keymap}`",
                                          *table(rows, reasons)]) + "\n", encoding="utf-8")


def course_menus(folder: Path, tree: Tree) -> list[tuple[str, int, str, str]]:
    """연습 과정 파일(*.yaml)의 `메뉴:` 칸마다 (파일, 줄, 길, 판정). '메뉴: 없음'은 건너뛴다. 단이 하나인 칸도 길로 맞댄다."""
    found = []
    for path in sorted(folder.glob("*.yaml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = re.match(r"\s*(?:-\s*)?메뉴:\s*(.+?)\s*$", line)
            if match and match.group(1) != "없음":
                found.append((path.name, number, match.group(1), tree.judge(match.group(1))))
    return found


def courses_main(out: Path, paths: Path, folder: Path) -> None:
    rows = course_menus(folder, Tree(json.loads(paths.read_text(encoding="utf-8"))))
    if out.exists():
        raise SystemExit(f"{out}가 이미 있어 멈춥니다")
    counts = Counter(verdict for *_, verdict in rows)
    lines = ["# 연습 과정 메뉴 칸 대조", "", f"- 메뉴 나무 `{paths}`, 연습 과정 `{folder}`. 칸 {len(rows)}개: {dict(counts)}",
             "- 나무는 3D 뷰 머리 메뉴의 물체·메시 편집 모드뿐이라 '나무에 없음'은 틀렸다는 뜻이 아니다(속성 창 등)", "",
             "| 파일:줄 | 메뉴 칸 | 판정 |", "|---|---|---|"]
    lines += [f"| {name}:{number} | {menu} | {verdict} |" for name, number, menu, verdict in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "courses":
        courses_main(*(Path(arg) for arg in sys.argv[2:5]))
    else:
        main(*(Path(arg) for arg in sys.argv[1:5]))
