"""주석만 지웠는지 확인한다(코드 정리 10의 주석 줄이기, HISTORY [472]). 돈 0.

바뀐 .py 파일마다 기준 판(git)과 작업 폴더의 파이썬 구문 나무(ast)를 견준다. 주석과 빈 줄만 바뀌었으면 나무가 같다.
독스트링은 나무에 들어 있어 독스트링을 고치면 다르다고 나온다(독스트링은 남기기로 했다).
`# noqa`·`# type: ignore` 주석의 수가 줄어도 실패로 친다(검사를 끄는 주석이라 지우면 동작이 바뀐다).

쓰는 법(저장소 맨 위에서):
    .venv/bin/python .claude/tools/same_ast.py              # 기준 = HEAD, 대상 = HEAD와 다른 모든 .py
    .venv/bin/python .claude/tools/same_ast.py --기준 main
다른 파일이 하나라도 있으면 종료 코드 1.
"""

import argparse
import ast
import io
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEEP = ("noqa", "type: ignore")


def _keep_count(source: str) -> int:
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    return sum(any(word in token.string for word in KEEP) for token in tokens if token.type == tokenize.COMMENT)


def compare(base: str) -> list[str]:
    """기준 판과 나무가 다르거나 검사 끄는 주석이 줄어든 파일 목록. 기준 판에 없던 새 파일은 견주지 않는다."""
    changed = subprocess.run(["git", "diff", "--name-only", base, "--", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True)
    problems = []
    for name in changed.stdout.split():
        path = ROOT / name
        before = subprocess.run(["git", "show", f"{base}:{name}"], cwd=ROOT, capture_output=True, text=True)
        if before.returncode or not path.exists():
            continue
        after = path.read_text(encoding="utf-8")
        if ast.dump(ast.parse(before.stdout)) != ast.dump(ast.parse(after)):
            problems.append(f"{name}: 코드가 바뀜(구문 나무가 다름)")
        elif _keep_count(after) < _keep_count(before.stdout):
            problems.append(f"{name}: noqa·type: ignore 주석이 줄어듦")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--기준", dest="base", default="HEAD")
    args = parser.parse_args(argv)
    problems = compare(args.base)
    print("\n".join(problems) or "모든 바뀐 .py 파일: 구문 나무 같음")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
