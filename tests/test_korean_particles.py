"""한국어 조사·어미 고르기: 받침에 따라 '으로/로', '이에요/예요'를 고르는 데 쓰는 받침 판단."""

from blender_tutor.korean_particles import fit_particle, has_final, with_euro


def test_받침이_있으면_으로_없거나_ㄹ_받침이면_로():
    assert with_euro("검") == "검으로"
    assert with_euro("방패") == "방패로"
    assert with_euro("칼날") == "칼날로"  # ㄹ 받침은 '로'


def test_받침이_있는지_본다():
    assert has_final("모으기") is False  # 모으기예요
    assert has_final("손잡이 붙이기") is False
    assert has_final("코등이 붙이기 단계") is False
    assert has_final("검") is True  # 검이에요
    assert has_final("칼날") is True


def test_한글_음절이_아니면_받침_없음으로_본다():
    assert has_final("glTF") is False
    assert with_euro("Cube") == "Cube로"


def test_이나_나도_받침에_맞춘다():
    # 티켓 50 가: "칼(Knife)이나" → "나이프(Knife)나", "크기(Scale)나" → "스케일(Scale)이나"(2026-11-16 저장된 답으로 확인)
    assert fit_particle("나이프", "이나 에지") == "나 에지"
    assert fit_particle("스케일", "나 색") == "이나 색"
    assert fit_particle("나이프", "나이가") == "나이가"  # 뒤가 한글이면 조사인지 몰라 둔다
