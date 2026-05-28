Dispatch a live smoke run of each PMF experiment in dev and verify it produces a valid artifact.

## Prerequisites

**books/.env variables**: none
**scripts/.env variables**: none
**Tools**: `aws` CLI authenticated as the `work` profile, `uuidgen`, `python3`. WireGuard VPN only if you need to resolve a *fresh* district from election-api RDS (see "Getting valid params"); reusing params from a prior run needs no VPN.

## What a smoke run actually tests

A smoke is a real dispatch onto Fargate with a throwaway `smoke-*` org slug. It exercises the full spine: dispatch Lambda → param validation → ECS task → broker (manifest fetch, Databricks, artifact publish) → Claude agent → output schema validation → S3.

**It runs the IMAGE CURRENTLY DEPLOYED to dev — not your local branch.** Dispatching via SQS will not pick up uncommitted/unmerged code or a bumped dependency in your working tree. To smoke a code or dependency change (e.g. an SDK upgrade), that change must first be built into the dev image (push to the `dev` branch → CI build → ECR → ECS) before the dispatch reflects it. Confirm what's deployed before trusting a smoke as validation of a change.

## Steps

### 1. See what experiments exist and what's been run

```bash
# Registry of dispatchable experiments in dev (id, version, manifest/instruction keys)
AWS_PROFILE=work aws s3 cp s3://agent-experiment-metadata-dev/index.json - | python3 -m json.tool

# Prior runs per experiment (org-slug or run-id prefixes; smoke-* are prior smokes)
AWS_PROFILE=work aws s3 ls s3://gp-agent-artifacts-dev/<experiment_id>/
```

### 2. Get valid params

The dispatch Lambda validates `params` against the manifest's `input_schema` before launching ECS, so params must be complete and well-formed. Two ways to get them:

- **Reuse a known-good run (fastest).** Copy the identifying fields out of a prior successful artifact. The published artifact filename is **`artifact.json`** on current builds (older runs published `latest.json`), so list the prefix first rather than assuming:
  ```bash
  AWS_PROFILE=work aws s3 ls s3://gp-agent-artifacts-dev/<experiment_id>/<prior_run>/
  AWS_PROFILE=work aws s3 cp s3://gp-agent-artifacts-dev/<experiment_id>/<prior_run>/artifact.json - \
    | python3 -m json.tool | head -40
  ```
- **Resolve a fresh district** (when you need a district the agent has L2 data for): follow `books/convert-runbook-to-experiment.md` § "Resolve the test district from election-api RDS" (needs VPN). Never guess L2 `l2DistrictName` values — a zero-row WHERE filter silently measures the whole city.

Required params per experiment (check the manifest's `input_schema.required` for the authoritative list — it changes with `version`):

| Experiment | Model | Timeout | Required params |
|---|---|---|---|
| `compliance_setup` | sonnet | 1200s | `campaign_id`, `clerk_user_id`, `election_date`, `trigger`, `candidate_first_name`, `candidate_last_name` (write-action: purchases a domain, publishes a site, submits TCR — only smoke with intent) |
| `district_issue_pulse` | sonnet | 1200s | none (derives from org context; gp-api injects district params at real dispatch — supply `state`/`city`/`l2DistrictType`/`l2DistrictName` to pin a district for a smoke) |
| `district_issue_snapshot` | sonnet | 1200s | `state`, `city`, `l2DistrictType`, `l2DistrictName`, `issueKeyword` |
| `meeting_briefing` | opus | 3000s | `officialName`, `state` (optional: `positionName`, `l2DistrictType`, `l2DistrictName`) |
| `meeting_schedule` | sonnet | 600s | `state`, `office` |

Known-good example params (Fayetteville, NC — has L2 + Legistar data):
```jsonc
// meeting_briefing
{ "officialName": "Stephon Ferguson", "state": "NC", "positionName": "City Council District 1" }
// district_issue_snapshot
{ "state": "NC", "city": "Fayetteville", "l2DistrictType": "City_Ward", "l2DistrictName": "FAYETTEVILLE CITY WARD 2", "issueKeyword": "housing" }
// meeting_schedule
{ "state": "NC", "office": "City Council" }
```

### 3. Dispatch one smoke per experiment

```bash
RUN_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
ORG="smoke-$(whoami)-$(date +%s)"
EXP=meeting_briefing

BODY=$(cat <<EOF
{
  "experiment_type": "$EXP",
  "run_id": "$RUN_ID",
  "organization_slug": "$ORG",
  "params": { "officialName": "Stephon Ferguson", "state": "NC", "positionName": "City Council District 1" }
}
EOF
)

AWS_PROFILE=work aws sqs send-message \
  --queue-url https://sqs.us-west-2.amazonaws.com/333022194791/agent-dispatch-dev.fifo \
  --message-body "$BODY" \
  --message-group-id "agent-dispatch-$ORG" \
  --message-deduplication-id "$RUN_ID"

echo "artifact will land at: s3://gp-agent-artifacts-dev/$EXP/$RUN_ID/artifact.json"
```

The wire field is **`experiment_type`**, NOT `experiment_id` — the dispatch Lambda's parser rejects `experiment_id`. To smoke all experiments, loop this with each `EXP` + its params, using a distinct `ORG`/`RUN_ID` each time (FIFO dedup is keyed on `RUN_ID`).

### 4. Confirm the dispatch was accepted and launched a task

```bash
AWS_PROFILE=work aws logs tail /aws/lambda/pmf-engine-dispatch-dev --since 5m --format short \
  | grep -iE "$RUN_ID|Dispatching|Started Fargate task|reject|error"
```

Expect `Dispatching experiment '<exp>' for organization '<org>' (run: <RUN_ID>)` then `Started Fargate task: arn:aws:ecs:...:task/pmf-engine-dev/<task-id>`. A validation rejection logs here instead of launching a task — fix the params and re-dispatch with a new `RUN_ID`.

### 5. Tail the run

```bash
# Runner (agent reasoning, turn-by-turn, completion/errors)
AWS_PROFILE=work aws logs tail /ecs/pmf-engine-dev --since 5m --follow --format short \
  | grep -E "Experiment:|tool:|Agent completed|ERROR|error"

# Broker (manifest fetch, Databricks queries, artifact publish)
AWS_PROFILE=work aws logs tail /ecs/broker-dev --since 5m --format short | grep -v health | grep -v anthropic
```

### 6. Read and validate the artifact

```bash
# Wait for the artifact (filename is artifact.json on current builds), then pretty-print
while ! AWS_PROFILE=work aws s3api head-object \
  --bucket gp-agent-artifacts-dev --key "$EXP/$RUN_ID/artifact.json" 2>/dev/null; do sleep 30; done

AWS_PROFILE=work aws s3 cp s3://gp-agent-artifacts-dev/$EXP/$RUN_ID/artifact.json - | python3 -m json.tool
```

A published artifact is already schema-valid — the agent runs `validate_output.py` before publish and the broker rejects contract violations, so reaching S3 means it passed the platform's own gate. To re-validate independently, pull the **deployed** schema from the metadata bucket, NOT the local `experiments/<id>/manifest.json` working-tree copy — the two can drift (same `version` number, different bytes) and a stale local schema will produce false failures (`oneOf`-keyed schemas dump the whole instance as one root error):

```bash
cd scripts/python   # has jsonschema via uv
AWS_PROFILE=work aws s3 cp s3://agent-experiment-metadata-dev/$EXP/manifest.json /tmp/dep_manifest.json --quiet
AWS_PROFILE=work aws s3 cp s3://gp-agent-artifacts-dev/$EXP/$RUN_ID/artifact.json /tmp/art.json --quiet
AWS_PROFILE=work uv run python -c "
import json
from jsonschema import Draft7Validator
from jsonschema.exceptions import best_match
schema=json.load(open('/tmp/dep_manifest.json'))['output_schema']
art=json.load(open('/tmp/art.json'))
errs=list(Draft7Validator(schema).iter_errors(art))
print('PASS' if not errs else f'FAIL: {best_match(errs).message[:200]}')
"
```

Beyond schema, confirm the content is real — `data_quality`/`score` not in a failed state, and fields populated from live sources, not skeleton defaults. Compare against a prior known-good run for the same experiment to catch silent regressions.

## Troubleshooting

- **No `Started Fargate task` line** → dispatch rejected the params. Check the Lambda log for the validation error; the params didn't match `input_schema`.
- **Task starts but no artifact** → tail `/ecs/pmf-engine-dev` for an `ERROR`/exception, and `/ecs/broker-dev` for a 401 (bad/expired broker scope ticket) or Databricks/allowlist rejection. Runs that hit `timeout_seconds` publish a partial or no artifact.
- **Artifact has `data_quality.overall: failed` or empty sections** → the agent ran but couldn't reach a data source (wrong district name → zero rows; domain not on the broker allowlist). Re-check params against a known-good run.
- **Change isn't reflected** → you smoked the deployed image, not your branch. See "What a smoke run actually tests" above.
