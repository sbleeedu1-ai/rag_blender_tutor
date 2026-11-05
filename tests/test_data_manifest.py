"""data/ 목록: 파일 크기까지 적고, 홀드아웃 이름은 드러내지 않으며, 다른 쪽 목록과 차이를 찾는다."""

from blender_tutor.data_manifest import LIST_NAME, SUMMARY_NAME, compare, main, read_list


def _tree(tmp_path):
    data = tmp_path / "data"
    (data / "eval").mkdir(parents=True)
    (data / "eval" / "a.json").write_text("12345", encoding="utf-8")
    (data / "holdout").mkdir()
    (data / "holdout" / "비밀문항.json").write_text("123", encoding="utf-8")
    (data / "holdout" / "둘째.json").write_text("1", encoding="utf-8")
    (tmp_path / "results" / "20261105" / "x").mkdir(parents=True)
    (tmp_path / "results" / "20261105" / "x" / "r.txt").write_text("12", encoding="utf-8")
    return data


def test_list_has_file_sizes_and_hides_holdout_names(tmp_path):
    data = _tree(tmp_path)
    assert main([], tmp_path) == 0
    listed = (data / LIST_NAME).read_text(encoding="utf-8")
    assert "eval/a.json\t1\t5\t" in listed
    assert "holdout/*\t2\t4\t" in listed
    assert "비밀문항" not in listed
    summary = (data / SUMMARY_NAME).read_text(encoding="utf-8")
    assert "| holdout | 2 |" in summary
    assert "| 20261105 | 1 |" in summary
    assert "비밀문항" not in summary


def test_rewriting_does_not_list_itself(tmp_path):
    data = _tree(tmp_path)
    main([], tmp_path)
    main([], tmp_path)
    assert set(read_list(data / LIST_NAME)) == {"eval/a.json", "holdout/*"}


def test_compare_finds_changed_and_missing_but_skips_not_uploaded(tmp_path, capsys):
    data = _tree(tmp_path)
    main([], tmp_path)
    other = tmp_path / "other.tsv"
    other.write_bytes((data / LIST_NAME).read_bytes())
    (data / "eval" / "a.json").write_text("1234567", encoding="utf-8")
    (data / "eval" / "새것.json").write_text("1", encoding="utf-8")
    (data / "models").mkdir()
    (data / "models" / "큰것.bin").write_text("1", encoding="utf-8")
    assert main(["--compare", str(other)], tmp_path) == 0
    out = capsys.readouterr().out
    assert "[여기에만] 1개" in out and "eval/새것.json" in out
    assert "[다름] 1개" in out and "eval/a.json: 여기 1개 7" in out
    assert "큰것.bin" not in out


def test_compare_reports_holdout_as_count_and_size():
    from blender_tutor.data_manifest import Entry

    found = compare({"holdout/*": Entry("holdout/*", 2, 4, "2026-11-05 10:00")}, {"holdout/*": Entry("holdout/*", 3, 9, "2026-11-04 10:00")})
    assert found["다름"] == ["holdout/*: 여기 2개 4 (2026-11-05 10:00) / 다른 쪽 3개 9 (2026-11-04 10:00) → 여기가 새것"]
