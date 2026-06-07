"""Red/green tests for non-clobbering (merge) publish.

Default publish writes an index built only from local dirs, which silently unpublishes
anyone else's experiments in a shared env. `merge_index` overlays the local entries onto
the live remote index: update existing by id, add new, PRESERVE everyone else's.
"""
from publish_experiments import merge_index


def _idx(experiments, git_sha="local"):
    return {"published_at": "2026-06-07T00:00:00Z", "git_sha": git_sha, "experiments": experiments}


def _e(eid, version=1):
    return {
        "id": eid, "version": version,
        "manifest_key": f"{eid}/manifest.json",
        "instruction_key": f"{eid}/instruction.md",
        "attachment_keys": [], "hash": f"sha256:{eid}",
    }


def test_merge_updates_own_adds_new_preserves_others():
    local = _idx([_e("alpha", 2), _e("charlie", 1)], git_sha="newsha")
    remote = _idx([_e("alpha", 1), _e("bravo", 1)], git_sha="oldsha")
    m = merge_index(local, remote)
    versions = {e["id"]: e["version"] for e in m["experiments"]}
    assert versions == {"alpha": 2, "bravo": 1, "charlie": 1}  # updated / preserved / added
    assert m["git_sha"] == "newsha"  # this publish stamps the top-level provenance


def test_merge_is_deterministic_sorted_by_id():
    local = _idx([_e("zeta"), _e("alpha")])
    remote = _idx([_e("mike")])
    ids = [e["id"] for e in merge_index(local, remote)["experiments"]]
    assert ids == sorted(ids)


def test_merge_with_no_remote_returns_local():
    local = _idx([_e("alpha")])
    assert merge_index(local, None)["experiments"] == local["experiments"]


def test_merge_with_remote_missing_experiments_key_returns_local():
    local = _idx([_e("alpha")])
    assert merge_index(local, {"published_at": "x"})["experiments"] == local["experiments"]


def test_merge_does_not_mutate_inputs():
    local = _idx([_e("alpha", 2)])
    remote = _idx([_e("bravo", 1)])
    merge_index(local, remote)
    assert [e["id"] for e in local["experiments"]] == ["alpha"]
    assert [e["id"] for e in remote["experiments"]] == ["bravo"]
