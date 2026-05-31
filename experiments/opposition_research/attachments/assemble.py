import glob
import json
import os
import sys
from datetime import date


def _workspace():
    return os.environ.get("ASSEMBLE_WORKSPACE", "/workspace")


def _load_params():
    raw = os.environ.get("PARAMS_JSON", "{}")
    try:
        params = json.loads(raw)
    except (ValueError, TypeError):
        params = {}
    return params if isinstance(params, dict) else {}


def _load_race(scratch_dir):
    # candidate_name + partisan_type, derived by the agent in Step 0 (the input
    # contract nests the race under campaign_strategy_context, so the agent
    # writes the bits the assembler needs here).
    path = os.path.join(scratch_dir, "_race.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_fragments(scratch_dir):
    fragments = []
    for path in sorted(glob.glob(os.path.join(scratch_dir, "opp_*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (ValueError, OSError) as exc:
            sys.stderr.write(f"warning: skipping {path}: {exc}\n")
            continue
        if isinstance(data, dict):
            fragments.append(data)
        else:
            sys.stderr.write(f"warning: skipping {path}: not a JSON object\n")
    return fragments


_INCUMBENT = {"yes": True, "no": False, "unknown": None}


def _party_affiliation(party, partisan_type):
    # Nonpartisan race -> the party labels are registration noise, not the
    # contest, so normalize to "Nonpartisan". Otherwise the opponent's party,
    # or "Unknown".
    if str(partisan_type or "").strip().lower() == "nonpartisan":
        return "Nonpartisan"
    if party:
        return party
    return "Unknown"


def _key_facts(facts):
    out = []
    for f in facts or []:
        if not isinstance(f, dict):
            continue
        text = (f.get("text") or "").strip()
        label = (f.get("source_label") or "").strip()
        url = (f.get("url") or "").strip()
        if not text:
            continue
        out.append(f"{text} ([{label}]({url}))" if label and url else text)
    return out[:3]


def _political_summary(frag):
    summary = frag.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    if frag.get("no_info"):
        return (
            f"No public information found as of {date.today().isoformat()}. "
            "You should conduct local research."
        )
    return ""


def _to_opponent(frag, partisan_type):
    return {
        "full_name": frag.get("full_name"),
        "party_affiliation": _party_affiliation(frag.get("party"), partisan_type),
        "incumbent": _INCUMBENT.get(str(frag.get("incumbent") or "").strip().lower()),
        "political_summary": _political_summary(frag),
        "key_facts": _key_facts(frag.get("facts")),
        "websites": [w for w in (frag.get("websites") or []) if isinstance(w, str)],
    }


def _build_artifact(race, fragments):
    partisan_type = race.get("partisan_type")
    return {"opponents": [_to_opponent(f, partisan_type) for f in fragments]}


def _spot_checks(artifact, race):
    reasons = []
    candidate_name = race.get("candidate_name")
    texts = []
    for opp in artifact["opponents"]:
        texts.append(opp.get("political_summary") or "")
        texts.extend(opp.get("key_facts") or [])
    blob = "\n".join(texts)
    if isinstance(candidate_name, str) and candidate_name.strip():
        if candidate_name.lower() in blob.lower():
            reasons.append(f"candidate name '{candidate_name}' appears in opponent text")
    if "—" in blob:
        reasons.append("em dash (U+2014) present in opponent text")
    return reasons


def _validate_shape(workspace, artifact):
    schema_path = os.path.join(workspace, "contract_schema.json")
    if not os.path.exists(schema_path):
        return []
    try:
        with open(schema_path, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"warning: could not read contract_schema.json: {exc}\n")
        return []
    try:
        import jsonschema

        jsonschema.validate(instance=artifact, schema=schema)
        return []
    except ImportError:
        return [] if "opponents" in artifact else ["artifact missing 'opponents'"]
    except jsonschema.ValidationError as exc:
        return [f"artifact schema violation: {exc.message}"]
    except jsonschema.SchemaError as exc:
        sys.stderr.write(
            f"warning: contract_schema.json is not a valid JSON Schema: {exc}\n"
        )
        return [] if "opponents" in artifact else ["artifact missing 'opponents'"]


def main():
    workspace = _workspace()
    scratch_dir = os.path.join(workspace, "scratch")
    output_dir = os.path.join(workspace, "output")
    os.makedirs(output_dir, exist_ok=True)

    # Prefer the agent's derived race fields (_race.json); fall back to PARAMS
    # for older callers / tests that pass them top-level.
    race = _load_race(scratch_dir) or _load_params()
    fragments = _load_fragments(scratch_dir)

    artifact = _build_artifact(race, fragments)

    output_path = os.path.join(output_dir, "opposition_research.json")
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2, ensure_ascii=False)

    reasons = _spot_checks(artifact, race)
    reasons += _validate_shape(workspace, artifact)

    if reasons:
        print("FAIL: " + "; ".join(reasons))
        sys.exit(1)
    print("PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
