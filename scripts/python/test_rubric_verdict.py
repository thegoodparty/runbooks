"""Tests for rubric_verdict.load() — the TSV parser must tolerate a header row.

Regression: two cold-judge runs wrote `scores.tsv` with an uncommented header
(`uuid\tbatch\tjudgeA\tjudgeB`), and the verdict crashed with
`ValueError: invalid literal for int() with base 10: 'judgeA'` because load()
only skipped `#`-prefixed lines. A header (or any non-data row) must be skipped.
"""
from pathlib import Path

import rubric_verdict


def test_load_skips_uncommented_header(tmp_path: Path):
    tsv = tmp_path / "scores.tsv"
    tsv.write_text(
        "uuid\tbatch\tjudgeA\tjudgeB\n"   # uncommented header — must be skipped
        "aaa\tb1\t28\t29\n"
        "bbb\tb1\tDQ\tDQ\n"
        "ccc\tb1\t30\t30\n"
    )
    rows = rubric_verdict.load(str(tsv))
    # the header row must not survive
    assert all(uuid != "uuid" for uuid, _b, _a, _bb in rows)
    assert len(rows) == 3
    # every judge value must be DQ or an integer, so main() never hits int('judgeA')
    for _uuid, _batch, a, b in rows:
        for v in (a, b):
            assert v == "DQ" or v.lstrip("-").isdigit(), f"non-data token leaked: {v!r}"


def test_load_still_skips_hash_comments(tmp_path: Path):
    tsv = tmp_path / "scores.tsv"
    tsv.write_text(
        "# uuid\tbatch\tjudgeA\tjudgeB\n"   # commented header
        "# a note line\n"
        "aaa\tb1\t25\t26\n"
    )
    rows = rubric_verdict.load(str(tsv))
    assert rows == [("aaa", "b1", "25", "26")]
