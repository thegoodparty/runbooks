Run any PMF engine experiment locally via Claude Code agent — voter targeting, walking plan, district intel, peer city benchmarking, or meeting briefing.

## Prerequisites

**Tools**: Claude Code CLI, Databricks access (for win-mode experiments), internet access
**Optional**: pandoc + xelatex (for meeting briefing PDF generation — `bash scripts/shell/setup-macos.sh`)

## Experiments

| ID | Mode | Needs Databricks | Needs S3 Artifact | Description |
|----|------|------------------|-------------------|-------------|
| `voter_targeting` | win | Yes | No | Segment voters by independent appeal score |
| `walking_plan` | win | Yes | No | Generate canvassing routes grouped by street clusters |
| `district_intel` | serve | Yes | No | Research governing body issues + cross-reference demographics |
| `peer_city_benchmarking` | serve | Yes | Yes (district_intel) | Compare peer city approaches to local issues |
| `meeting_briefing` | serve | No | Optional (district_intel) | Full governance briefing for next city council meeting |

## Quick Start

```
Run a walking plan for Tecumseh, MI
Run voter targeting for Hendersonville, NC
Run a district intel for Palestine, TX city council
Run a meeting briefing for Westerville, OH city council
```

## Steps

### 1. Create run directory and params

```bash
EXPERIMENT="walking_plan"  # or voter_targeting, district_intel, etc.
RUN_DIR="outputs/$(date +%Y%m%d-%H%M)-${EXPERIMENT}-{city-slug}"
mkdir -p "$RUN_DIR/output"
```

Write `$RUN_DIR/params.json` with the appropriate params for the experiment mode:

**Win mode** (voter_targeting, walking_plan):
```json
{
    "state": "MI",
    "city": "Tecumseh",
    "county": "Lenawee",
    "zip": "49286",
    "office": "Mayor",
    "party": "Independent",
    "l2DistrictType": "City_Mayoral_District",
    "l2DistrictName": "Tecumseh",
    "topIssues": ["Infrastructure", "Public Safety"],
    "winNumber": 1800,
    "voterContactGoal": 5000,
    "projectedTurnout": 3500
}
```

**Serve mode** (district_intel, peer_city_benchmarking, meeting_briefing):
```json
{
    "officeName": "City Council",
    "state": "TX",
    "city": "Palestine",
    "county": "Anderson",
    "zip": "75801"
}
```

Notes:
- **Do NOT fabricate `officialName`** for serve experiments — the agent discovers a real official through research
- **peer_city_benchmarking** requires a prior district_intel run. Add `districtIntelArtifactBucket` and `districtIntelArtifactKey` to params pointing to the district intel JSON, or place it at `$RUN_DIR/district_intel.json`
- Win mode params come from the candidate's campaign data (Path to Victory). Use real values from gp-api or estimate.

### 2. Copy contract schema and validator

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cp "$REPO_ROOT/books/pmf-engine/contracts/${EXPERIMENT}.json" "$RUN_DIR/contract_schema.json"

# Constraints sidecar is optional — only present for experiments with enum/range/cross-field rules
if [ -f "$REPO_ROOT/books/pmf-engine/contracts/${EXPERIMENT}.constraints.json" ]; then
  cp "$REPO_ROOT/books/pmf-engine/contracts/${EXPERIMENT}.constraints.json" "$RUN_DIR/contract_constraints.json"
fi
```

The agent instruction tells the agent to run `python3 $RUN_DIR/validate_output.py` — we write this for it. It checks the shape schema and (when present) the constraints sidecar:

```bash
cat > "$RUN_DIR/validate_output.py" << 'VALIDATOR'
#!/usr/bin/env python3
import json, os, sys, glob

TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}

def validate(data, schema, path=""):
    errors = []
    for key, expected in schema.items():
        full_path = f"{path}.{key}" if path else key
        if key not in data:
            errors.append(f"Missing: {full_path}")
            continue
        value = data[key]
        if isinstance(expected, str):
            checker = TYPE_CHECKS.get(expected)
            if checker and not checker(value):
                errors.append(f"Wrong type for {full_path}: expected {expected}, got {type(value).__name__} (value: {repr(value)[:80]})")
        elif isinstance(expected, dict):
            if not isinstance(value, dict):
                errors.append(f"Wrong type for {full_path}: expected object, got {type(value).__name__}")
            else:
                errors.extend(validate(value, expected, full_path))
        elif isinstance(expected, list) and len(expected) == 1:
            if not isinstance(value, list):
                errors.append(f"Wrong type for {full_path}: expected array, got {type(value).__name__}")
            elif len(value) == 0:
                errors.append(f"Empty array: {full_path}")
            else:
                item_schema = expected[0]
                for i, item in enumerate(value):
                    item_path = f"{full_path}[{i}]"
                    if isinstance(item_schema, dict):
                        if not isinstance(item, dict):
                            errors.append(f"Wrong type for {item_path}: expected object, got {type(item).__name__}")
                        else:
                            errors.extend(validate(item, item_schema, item_path))
                    elif isinstance(item_schema, str):
                        checker = TYPE_CHECKS.get(item_schema)
                        if checker and not checker(item):
                            errors.append(f"Wrong type for {item_path}: expected {item_schema}, got {type(item).__name__}")
    return errors

def _walk(cur, segs, idx, concrete, out):
    if idx == len(segs):
        out.append((concrete, cur))
        return
    seg = segs[idx]
    if seg.endswith("[]"):
        key = seg[:-2]
        if key:
            if not isinstance(cur, dict) or key not in cur:
                return
            cur = cur[key]
        if not isinstance(cur, list):
            return
        base = f"{concrete}.{key}" if concrete and key else (key if not concrete else concrete)
        for i, item in enumerate(cur):
            item_concrete = f"{base}[{i}]" if key or concrete else f"[{i}]"
            _walk(item, segs, idx + 1, item_concrete, out)
    else:
        if not isinstance(cur, dict) or seg not in cur:
            return
        nxt = f"{concrete}.{seg}" if concrete else seg
        _walk(cur[seg], segs, idx + 1, nxt, out)

def resolve_path(data, path):
    out = []
    _walk(data, path.split("."), 0, "", out)
    return out

def resolve_single(data, path):
    m = resolve_path(data, path)
    return (m[0][1], True) if m else (None, False)

def evaluate_right(data, right, errors, left_path):
    if isinstance(right, (int, float, str, bool)):
        return right
    if isinstance(right, dict):
        if "count" in right:
            v, f = resolve_single(data, right["count"])
            if not f or not isinstance(v, list):
                errors.append(f"Equals right count path not a list: {right['count']}")
                return None
            return len(v)
        if "sum" in right:
            m = resolve_path(data, right["sum"])
            if not m:
                errors.append(f"Equals right sum path not found: {right['sum']}")
                return None
            t = 0
            for c, v in m:
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    errors.append(f"Equals right sum non-numeric at {c}: {v!r}")
                    return None
                t += v
            return t
    errors.append(f"Equals right expression not understood for {left_path}: {right!r}")
    return None

def check_constraints(data, constraints):
    errors = []
    for rule in constraints.get("enums", []):
        path = rule["path"]
        allowed = set(rule["values"])
        m = resolve_path(data, path)
        if not m:
            errors.append(f"Enum path not found: {path}")
            continue
        for c, v in m:
            if v not in allowed:
                errors.append(f"Enum violation at {c}: got {v!r}, expected one of {sorted(allowed)}")
    for rule in constraints.get("ranges", []):
        path = rule["path"]
        lo, hi = rule.get("min"), rule.get("max")
        m = resolve_path(data, path)
        if not m:
            errors.append(f"Range path not found: {path}")
            continue
        for c, v in m:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                errors.append(f"Range target at {c} is not numeric: {v!r}")
                continue
            if lo is not None and v < lo:
                errors.append(f"Range violation at {c}: {v} < min {lo}")
            if hi is not None and v > hi:
                errors.append(f"Range violation at {c}: {v} > max {hi}")
    for rule in constraints.get("array_length", []):
        path = rule["path"]
        m = resolve_path(data, path)
        if not m:
            errors.append(f"Array length path not found: {path}")
            continue
        for c, v in m:
            if not isinstance(v, list):
                errors.append(f"Array length target at {c} is not a list: {type(v).__name__}")
                continue
            length = len(v)
            if "exact" in rule and length != rule["exact"]:
                errors.append(f"Array length violation at {c}: got {length}, expected exactly {rule['exact']}")
            if "min" in rule and length < rule["min"]:
                errors.append(f"Array length violation at {c}: got {length}, expected min {rule['min']}")
            if "max" in rule and length > rule["max"]:
                errors.append(f"Array length violation at {c}: got {length}, expected max {rule['max']}")
    for rule in constraints.get("exact_ids", []):
        path = rule["path"]
        expected = list(rule["values"])
        m = resolve_path(data, path)
        if not m:
            errors.append(f"Exact-ids path not found: {path}")
            continue
        actual = [v for _, v in m]
        if sorted(actual) != sorted(expected):
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            parts = []
            if missing:
                parts.append(f"missing {missing}")
            if extra:
                parts.append(f"unexpected {extra}")
            if len(actual) != len(expected):
                parts.append(f"got {len(actual)}, expected {len(expected)}")
            errors.append(f"Exact-ids violation at {path}: " + "; ".join(parts))
    for rule in constraints.get("equals", []):
        left_path = rule["left"]
        left_value, f = resolve_single(data, left_path)
        if not f:
            errors.append(f"Equals left path not found: {left_path}")
            continue
        right_value = evaluate_right(data, rule["right"], errors, left_path)
        if right_value is None:
            continue
        if left_value != right_value:
            errors.append(f"Equals violation at {left_path}: left={left_value}, right={right_value} (right expression: {rule['right']})")
    return errors

workspace = os.path.dirname(os.path.abspath(__file__))
schema_path = os.path.join(workspace, "contract_schema.json")
constraints_path = os.path.join(workspace, "contract_constraints.json")
files = glob.glob(os.path.join(workspace, "output", "*.json"))
if not files:
    print(f"FAIL: No JSON files in {workspace}/output/")
    sys.exit(1)
schema = json.load(open(schema_path))
constraints = json.load(open(constraints_path)) if os.path.exists(constraints_path) else None
for f in files:
    data = json.load(open(f))
    errors = validate(data, schema)
    if constraints:
        errors.extend(check_constraints(data, constraints))
    if errors:
        print(f"FAIL: {f}")
        for e in errors[:30]:
            print(f"  {e}")
        if len(errors) > 30:
            print(f"  ... and {len(errors) - 30} more errors")
        sys.exit(1)
    else:
        suffix = " (+constraints)" if constraints else ""
        print(f"PASS: {f} — all fields valid{suffix}")
VALIDATOR
```

### 3. Spawn the agent

Source Databricks credentials (needed for win-mode experiments and district demographics):

```bash
set -a && source "$REPO_ROOT/scripts/.env" && set +a
```

```bash
INSTRUCTION=$(cat "$REPO_ROOT/books/pmf-engine/instructions/${EXPERIMENT}.md")

cat <<PROMPT | claude -p \
  --output-format stream-json \
  --allowedTools "Bash Read Write Edit Glob Grep WebFetch WebSearch" \
  --model sonnet \
  2>"$RUN_DIR/agent-stderr.log" \
  | tee "$RUN_DIR/conversation.jsonl" \
  | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        if d.get('type') == 'assistant':
            for c in d.get('message',{}).get('content',[]):
                if c.get('type') == 'tool_use':
                    print(f'  TOOL: {c[\"name\"]}')
                elif c.get('type') == 'text' and len(c.get('text','').strip()) > 20:
                    print(f'  >>> {c[\"text\"][:120]}')
        elif d.get('type') == 'result':
            cost = d.get('total_cost_usd', 0)
            turns = d.get('num_turns', 0)
            print(f'  === DONE: {turns} turns, \${cost:.2f} ===')
    except: pass
"
You are running a ${EXPERIMENT} experiment.

## Setup

1. Your instruction is below (also save it to \$RUN_DIR/instruction.md for mid-run reference).
2. Read your params from: \$RUN_DIR/params.json
3. Your workspace is \$RUN_DIR/. Wherever the instruction says /workspace/, use \$RUN_DIR/ instead.
4. Write final output to \$RUN_DIR/output/${EXPERIMENT}.json
5. The contract schema is at \$RUN_DIR/contract_schema.json
6. The validator script is at \$RUN_DIR/validate_output.py

## Important

- Follow the instruction's TODO checklist. Create it in your first message.
- Make REAL API calls and web searches. Do not fabricate any data.
- Run \`python3 \$RUN_DIR/validate_output.py\` before finishing to check your output.
- Push hard on data collection. When one source fails, try alternatives before marking a step done.

## Instruction

$INSTRUCTION
PROMPT
```

For multiple experiments or cities in parallel, run each in background with `&` and `wait`.

### 4. Validate output

After the agent finishes:

```bash
cd "$REPO_ROOT/scripts" && uv run python/validate_contract.py "$RUN_DIR/output/${EXPERIMENT}.json" "$REPO_ROOT/books/pmf-engine/contracts/${EXPERIMENT}.json"
```

### 5. Review agent logs

Parse the conversation trace into a readable summary:

```bash
cd "$REPO_ROOT/scripts" && uv run python/parse_conversation.py "$RUN_DIR/conversation.jsonl"
```

Add `--verbose` to include tool results (useful for debugging failures):

```bash
cd "$REPO_ROOT/scripts" && uv run python/parse_conversation.py "$RUN_DIR/conversation.jsonl" --verbose
```

### 6. Review results

```bash
python3 -c "
import json
d = json.load(open('$RUN_DIR/output/${EXPERIMENT}.json'))
print(json.dumps({k: v for k, v in d.items() if k in ('summary', 'methodology', 'generated_at')}, indent=2))
"
```

For meeting briefings, generate a PDF:

```bash
cd "$REPO_ROOT/scripts" && uv run python/briefing_to_pdf.py "$RUN_DIR/output/meeting_briefing.json" "$RUN_DIR/briefing.pdf"
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 0 voters from Databricks | District column may be NULL — agent should fall back to city filter. If not, check `l2DistrictType`/`l2DistrictName` params. |
| Contract violation after agent finishes | Agent should have caught this with validate_output.py. Re-run or manually fix the JSON. |
| Agent rewrites template from scratch | The instruction says not to. If it still does, the contract schema will catch missing fields. |
| Agent stuck / looping | Check conversation.jsonl for repeated tool calls. May need to increase max turns or simplify the task. |
| 403 on city websites | Expected for some municipalities. Agent should fall back to news/web search. |
| Databricks connection error | Check `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_API_KEY` env vars. |
