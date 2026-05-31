import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_SRC = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "opposition_research"
    / "attachments"
    / "assemble.py"
)


def _fragment_with_facts():
    return {
        "full_name": "Jane Doe",
        "party": "Nonpartisan",
        "incumbent": "Yes",
        "summary": "Jane Doe is the two-term incumbent on the commission. She has focused on zoning reform.",
        "facts": [
            {
                "text": "Won her last race with 5,000 votes.",
                "source_label": "Local Times",
                "url": "https://example.com/jane-results",
            }
        ],
        "websites": ["https://janedoe.example.com"],
        "no_info": False,
    }


def _fragment_no_info():
    return {
        "full_name": "John Roe",
        "party": None,
        "incumbent": "Unknown",
        "summary": None,
        "facts": [],
        "websites": [],
        "no_info": True,
    }


def _setup_workspace(tmp_path, fragments, race):
    ws = tmp_path / "workspace"
    scratch = ws / "scratch"
    scratch.mkdir(parents=True)
    (ws / "output").mkdir(parents=True)
    shutil.copy(SCRIPT_SRC, ws / "assemble.py")
    for idx, frag in enumerate(fragments, start=1):
        (scratch / f"opp_{idx:02d}.json").write_text(
            json.dumps(frag), encoding="utf-8"
        )
    # production path: the agent writes derived race fields to _race.json
    (scratch / "_race.json").write_text(json.dumps(race), encoding="utf-8")
    return ws


def _run(ws):
    env = dict(os.environ)
    env["ASSEMBLE_WORKSPACE"] = str(ws)
    return subprocess.run(
        [sys.executable, str(ws / "assemble.py")],
        env=env,
        capture_output=True,
        text=True,
    )


def _artifact(ws):
    return json.loads((ws / "output" / "opposition_research.json").read_text())


def _race(**overrides):
    r = {"candidate_name": "Maria Sanchez", "partisanType": "nonpartisan"}
    r.update(overrides)
    return r


def test_two_fragments_structured(tmp_path):
    ws = _setup_workspace(
        tmp_path, [_fragment_with_facts(), _fragment_no_info()], _race()
    )
    proc = _run(ws)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "PASS"

    art = _artifact(ws)
    # top-level shape: only opponents, no markdown/race/generated_at
    assert set(art.keys()) == {"opponents"}
    assert len(art["opponents"]) == 2

    jane, john = art["opponents"]
    assert jane["full_name"] == "Jane Doe"
    assert jane["party_affiliation"] == "Nonpartisan"
    assert jane["incumbent"] is True
    assert jane["political_summary"].startswith("Jane Doe is the two-term incumbent")
    assert jane["key_facts"] == [
        "Won her last race with 5,000 votes. ([Local Times](https://example.com/jane-results))"
    ]
    assert jane["websites"] == ["https://janedoe.example.com"]

    assert john["full_name"] == "John Roe"
    assert john["incumbent"] is None
    assert john["key_facts"] == []
    assert "No public information found" in john["political_summary"]


def test_zero_fragments_empty_opponents(tmp_path):
    ws = _setup_workspace(tmp_path, [], _race())
    proc = _run(ws)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _artifact(ws) == {"opponents": []}


def test_nonpartisan_normalizes_party(tmp_path):
    # Even if a roster row carries a partisan registration label, a nonpartisan
    # race normalizes it to "Nonpartisan".
    frag = _fragment_with_facts()
    frag["party"] = "Democratic"
    ws = _setup_workspace(tmp_path, [frag], _race(partisanType="nonpartisan"))
    proc = _run(ws)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _artifact(ws)["opponents"][0]["party_affiliation"] == "Nonpartisan"


def test_partisan_uses_party_or_unknown(tmp_path):
    dem = _fragment_with_facts()
    dem["party"] = "Democratic"
    unknown = _fragment_with_facts()
    unknown["full_name"] = "No Party Person"
    unknown["party"] = None
    ws = _setup_workspace(tmp_path, [dem, unknown], _race(partisanType="partisan"))
    proc = _run(ws)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    opps = _artifact(ws)["opponents"]
    assert opps[0]["party_affiliation"] == "Democratic"
    assert opps[1]["party_affiliation"] == "Unknown"


def test_incumbent_mapping(tmp_path):
    no = _fragment_with_facts()
    no["full_name"] = "Not Incumbent"
    no["incumbent"] = "No"
    ws = _setup_workspace(tmp_path, [no], _race())
    proc = _run(ws)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _artifact(ws)["opponents"][0]["incumbent"] is False


def test_candidate_name_present_fails(tmp_path):
    bad = _fragment_with_facts()
    # lower-case spelling exercises the case-insensitive check specifically
    bad["summary"] = bad["summary"] + " maria sanchez is the favorite."
    ws = _setup_workspace(tmp_path, [bad], _race())
    proc = _run(ws)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert proc.stdout.strip().startswith("FAIL:")
    assert "candidate name 'Maria Sanchez' appears" in proc.stdout


def test_em_dash_fails(tmp_path):
    bad = _fragment_with_facts()
    bad["summary"] = bad["summary"] + " Strong record — well known."
    ws = _setup_workspace(tmp_path, [bad], _race())
    proc = _run(ws)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert proc.stdout.strip().startswith("FAIL:")


def test_skips_non_dict_fragment(tmp_path):
    ws = _setup_workspace(tmp_path, [_fragment_with_facts()], _race())
    (ws / "scratch" / "opp_99.json").write_text("not json at all", encoding="utf-8")
    (ws / "scratch" / "opp_98.json").write_text("[1, 2, 3]", encoding="utf-8")
    proc = _run(ws)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(_artifact(ws)["opponents"]) == 1
