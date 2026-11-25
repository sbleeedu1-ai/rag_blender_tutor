"""화면 확인 표(TSV)에서 화면을 안 보고 화면 판정을 적은 줄을 찾는다(돈 0). HISTORY [444], docs/agents/rules-enforced.md.

사용자 "그럼 또 확인 안하고 얘기했다는거잖아"(11-18): 소스만 읽고 "일반 화면에 없음"이라고 적고 말한 일이 되풀이돼 만든 검사다.
규칙: '판정' 칸이 소스·실행만으로 정했다는 말(SOURCE_ONLY)로 시작하지 않으면 화면에서 본 판정으로 본다.
그런 줄은 '그림' 칸에 표 폴더 안에 실제로 있는 화면 그림이 하나 이상 있어야 하고, '화면 증거' 칸이 있으면 "봄"이나 "없음을 봄"이어야 한다.
또 '설정' 칸에 찍을 때 환경 설정 '새로운 데이터' 번역 상태를 "새 데이터 켬"으로 적거나, 끈 채 찍었으면 "새 데이터 끔(까닭)"으로 적어야 한다.
11-18 오전 장면 스크립트가 이 번역을 꺼 둔 채 찍었는데 표에 칸이 없어 아무도 몰랐고, 켜면 "Attribute"가 "속성"으로 뜬다(HISTORY [455]·[456]).
공장 설정과 이 Mac 사용자 설정은 모두 켬이다([452]).
쓰는 법: .venv/bin/python .claude/tools/screen_table_check.py 표.tsv [...]. 걸린 줄이 있으면 종료 코드 1.
"""
import csv
import re
import sys
from pathlib import Path

SOURCE_ONLY = ("소스로만", "못 띄움", "실행으로만")
SEEN = ("봄", "없음을 봄")
PICTURE = re.compile(r"화면/[^\s,]+")
SETTING_ON = "새 데이터 켬"
SETTING_OFF = re.compile(r"새 데이터 끔\(.+\)")


def setting_problem(value):
    """'설정' 칸 값이 안 되면 까닭, 되면 None."""
    if value.startswith(SETTING_ON) or SETTING_OFF.match(value):
        return None
    if value.startswith("새 데이터 끔"):
        return "새 데이터 끔인데 까닭이 없음('새 데이터 끔(까닭)'으로 적음)"
    return f"설정 칸이 '{value}'(찍을 때 '새 데이터 켬'인지 적음)" if value else "설정 칸이 없거나 비었음(찍을 때 '새 데이터 켬'인지 적음)"


def check_rows(rows, folder):
    """표 줄(첫 줄은 머리)을 받아 걸린 줄의 (영어, 까닭) 목록을 돌려준다."""
    head = rows[0]
    verdict, picture = head.index("판정"), head.index("그림")
    evidence = head.index("화면 증거") if "화면 증거" in head else None
    setting = head.index("설정") if "설정" in head else None
    bad = []
    for r in rows[1:]:
        if r[verdict].startswith(SOURCE_ONLY):
            continue
        if evidence is not None and r[evidence] not in SEEN:
            bad.append((r[0], f"화면 판정인데 증거가 '{r[evidence]}'"))
            continue
        pics = PICTURE.findall(r[picture])
        if not pics:
            bad.append((r[0], "화면 판정인데 그림이 없음"))
        elif not all((folder / p).exists() for p in pics):
            bad.append((r[0], "그림 파일이 없음: " + ", ".join(p for p in pics if not (folder / p).exists())))
        elif why := setting_problem(r[setting].strip() if setting is not None else ""):
            bad.append((r[0], why))
    return bad


def main(paths):
    total = 0
    for p in map(Path, paths):
        rows = list(csv.reader(p.open(encoding="utf-8"), delimiter="\t"))
        bad = check_rows(rows, p.parent)
        total += len(bad)
        print(f"{p}: {len(rows) - 1}줄 중 걸림 {len(bad)}")
        for name, why in bad:
            print(f"  {name}: {why}")
    if total:
        print("소스·실행만으로 정한 줄은 판정을 '소스로만'·'못 띄움'·'실행으로만'으로 시작하고, 화면 판정은 찍은 그림을 단다.")
        print("화면 판정은 '설정' 칸에 '새 데이터 켬', 끈 채 찍었으면 '새 데이터 끔(까닭)'을 적는다.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
