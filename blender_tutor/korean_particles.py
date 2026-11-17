"""한국어 조사 고르기(korean particles): 받침에 따라 바뀌는 말('으로/로', '이에요/예요')을 고른다.

도우미가 이름을 넣어 만드는 문장(바꾸기 물음, 단계 시작 말 등)이 함께 쓴다.
"""

import re


def _final(word: str) -> int:
    """마지막 글자의 받침 번호(0이면 받침 없음, 8이면 ㄹ). 한글 음절이 아니면 받침 없음으로 본다."""
    last = ord(word[-1]) - 0xAC00
    return last % 28 if 0 <= last < 11172 else 0


def has_final(word: str) -> bool:
    """마지막 글자에 받침이 있나. '이에요/예요'처럼 받침에 따라 바뀌는 말을 고를 때 쓴다."""
    return _final(word) != 0


def with_euro(name: str) -> str:
    """이름 뒤에 '(으)로'를 붙인다: 마지막 글자에 받침이 있으면 '으로'(검으로), 없거나 ㄹ 받침이면 '로'(방패로·칼날로)."""
    return f"{name}으로" if _final(name) not in (0, 8) else f"{name}로"


# 받침이 있을 때 / 없을 때 쓰는 조사 짝('으로/로'는 ㄹ 받침 뒤에도 '로')
_PAIRS = {"을": ("을", "를"), "를": ("을", "를"), "이": ("이", "가"), "가": ("이", "가"),
          "은": ("은", "는"), "는": ("은", "는"), "과": ("과", "와"), "와": ("과", "와"),
          "으로": ("으로", "로"), "로": ("으로", "로"), "이나": ("이나", "나"), "나": ("이나", "나"),
          "이면": ("이면", "면"), "면": ("이면", "면")}  # fmt: skip
PARTICLE = re.compile(r"(으로|로|이나|이면|을|를|이|가|은|는|과|와|나|면)(?![가-힣])")


def fit_particle(word: str, text: str) -> str:
    """text 맨 앞의 조사를 word의 마지막 글자 받침에 맞춘다('추가' + '을 누르세요' → '를 누르세요').

    word가 한글로 끝나지 않거나, 조사 뒤가 한글이라 조사인지 모르는 꼴('이라는'·'이에요')은 그대로 둔다(틀리면 안 바꾸는 쪽으로).
    """
    match = PARTICLE.match(text)
    if not match or not re.search(r"[가-힣]$", word):
        return text
    with_final, without = _PAIRS[match[1]]
    final = _final(word)
    right = with_final if (final not in (0, 8) if with_final == "으로" else final != 0) else without
    return right + text[match.end() :]
