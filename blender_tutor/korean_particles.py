"""한국어 조사 고르기(korean particles): 받침에 따라 바뀌는 말('으로/로', '이에요/예요')을 고른다.

도우미가 이름을 넣어 만드는 문장(바꾸기 물음, 단계 시작 말 등)이 함께 쓴다.
"""


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
