Port a locally-developed PMF experiment from runbooks to the PMF engine (gp-ai-projects → gp-api → gp-webapp).

## Prerequisites

**Tools**: Claude Code CLI, Docker, AWS CLI, `uv`, `npm`
**Access**: AWS (`work` profile), GitHub (`Collin-GP`)
**Repos**: `~/work/gp-ai-projects`, `~/work/gp-api`, `~/work/gp-webapp`

## When to Use

You've built and tested an experiment locally using `books/run-pmf-experiment.md`. The instruction markdown produces a valid artifact that passes contract validation. Now you want it running on Fargate, triggered from the dashboard.

## Inputs

Before starting, you should have:

| File | Location in this repo | What it is |
|------|----------------------|------------|
| Instruction | `books/pmf-engine/instructions/{experiment_id}.md` | The agent playbook |
| Contract schema | `books/pmf-engine/contracts/{experiment_id}.json` | JSON schema for output validation |
| Sample artifact | `outputs/{run-dir}/output/{experiment_id}.json` | A passing artifact from a local run |
| Sample conversation | `outputs/{run-dir}/conversation.jsonl` | Proof the experiment works |

## Steps

### 1. Choose experiment config

Decide these values:

| Field | Options | Notes |
|-------|---------|-------|
| `experiment_id` | snake_case name | Must be unique across all experiments |
| `mode` | `win` or `serve` | win = candidates, serve = elected officials |
| `model` | `opus` or `sonnet` | opus for complex research, sonnet for data-heavy scripts |
| `max_turns` | 30-60 | More turns = more cost. Walking plan needs ~20, meeting briefing needs ~50 |
| `timeout_seconds` | 300-900 | Fargate task timeout. 600 (10 min) is default |
| `cpu` / `memory` | `1024`/`2048` or `2048`/`4096` | Higher for experiments that process large datasets |

### 2. Port to gp-ai-projects

**2a. Create experiment module**

```python
# gp-ai-projects/pmf_engine/runner/experiments/{experiment_id}.py
from pathlib import Path

_instruction_path = Path(__file__).parent / "instructions" / "{experiment_id}.md"
_instruction = _instruction_path.read_text()

EXPERIMENT = {
    "instruction": _instruction,
    "contract": {
        "type": "json",
        "s3_key_template": "{experiment_id}/{run_id}/{experiment_id}.json",
        "schema": {
            # Paste from books/pmf-engine/contracts/{experiment_id}.json
        },
    },
    "harness": "claude_sdk",
    "model": "opus",
    "mode": "win",  # or "serve"
    "max_turns": 50,
    "cpu": "2048",
    "memory": "4096",
    "timeout_seconds": 600,
}
```

**2b. Copy instruction**

```bash
cp books/pmf-engine/instructions/{experiment_id}.md \
   ~/work/gp-ai-projects/pmf_engine/runner/experiments/instructions/{experiment_id}.md
```

Review the instruction — replace any runbook-specific paths (`$RUN_DIR/`) with Fargate paths (`/workspace/`). The instruction should reference:
- `/workspace/output/` for final artifact
- `/workspace/validate_output.py` for self-validation
- `/workspace/contract_schema.json` for the schema
- `/tmp/` for scratch files

**2c. Register the experiment**

Add to `gp-ai-projects/pmf_engine/control_plane/registry.py`:

```python
from pmf_engine.runner.experiments.{experiment_id} import EXPERIMENT as {EXPERIMENT_ID}_EXPERIMENT

EXPERIMENT_REGISTRY["{experiment_id}"] = {EXPERIMENT_ID}_EXPERIMENT
```

Add to `gp-ai-projects/pmf_engine/control_plane/dispatch_registry.py`:

```python
"{experiment_id}": {
    "harness": "claude_sdk",
    "model": "opus",
    "timeout_seconds": 600,
    "contract": {"s3_key_template": "{experiment_id}/{run_id}/{experiment_id}.json"},
},
```

**2d. Add tests**

In `tests/test_registry.py` — add registration + mode test.
In `tests/test_contract_validation.py` — add schema validation test using the sample artifact.

**2e. Update Lambda build**

Verify `pmf_engine/scripts/build_lambda_package.sh` copies `dispatch_registry.py` (it already does — just ensure the new experiment is importable from the registry).

**2f. Run tests**

```bash
cd ~/work/gp-ai-projects && uv run pytest pmf_engine/tests/ -v
```

The `test_registry_consistency.py` test will fail if the dispatch registry and full registry don't match — fix until green.

### 3. Port to gp-api

**3a. Add experiment ID**

In `gp-api/src/agentExperiments/schemas/agentExperiments.schema.ts`, add to `EXPERIMENT_IDS`:

```typescript
export const EXPERIMENT_IDS = [
  'voter_targeting',
  'walking_plan',
  'district_intel',
  'peer_city_benchmarking',
  'meeting_briefing',
  '{experiment_id}',  // NEW
] as const
```

TypeScript will error on every exhaustive `Record<ExperimentId, ...>` until you update them all.

**3b. Add to experiment modes + allowlist**

In `gp-api/src/agentExperiments/services/candidateExperiments.service.ts`:

```typescript
const EXPERIMENT_MODES: Record<...> = {
  // ...existing...
  {experiment_id}: 'win',  // or 'serve'
}

const ALLOWED_USER_PARAMS: Record<...> = {
  // ...existing...
  {experiment_id}: [],
}
```

**3c. Wire params in dispatch method**

If the experiment needs special params (like `peer_city_benchmarking` needs district intel artifact), add logic in `dispatchWinExperiment()` or `dispatchServeExperiment()`.

**3d. Add tests**

In `candidateExperiments.service.test.ts` — test dispatch with auto-populated params, test it appears in available experiments list.

```bash
cd ~/work/gp-api && npx vitest run src/agentExperiments/
```

### 4. Port to gp-webapp

**4a. Add type + artifact interface**

In `gp-webapp/app/dashboard/ai-insights/types.ts`:

```typescript
export type ExperimentId = '...' | '{experiment_id}'

export interface {ExperimentName}Artifact {
  // Match the contract schema fields
}
```

**4b. Add tab**

In `AIInsightsPage.tsx`, add to `WIN_TABS` or `SERVE_TABS`:

```typescript
{ id: '{experiment_id}', label: 'Display Name', description: 'One-line description' }
```

**4c. Create results component**

Create `{ExperimentName}Results.tsx`:

```typescript
const { artifact, loading, error, retry } = useArtifact<{ExperimentName}Artifact>(runId)
```

Use `<Stat>`, `<Card>`, `<ArtifactError>` shared components. See existing results components for patterns.

**4d. Wire into ExperimentTab**

In `ExperimentTab.tsx`, add rendering case:

```typescript
{experimentId === '{experiment_id}' && <{ExperimentName}Results runId={run.runId} />}
```

**4e. Add tests**

```bash
cd ~/work/gp-webapp && npm test
```

### 5. Deploy

**5a. gp-ai-projects (Fargate + Lambda)**

```bash
cd ~/work/gp-ai-projects

# Rebuild Lambda package
bash pmf_engine/scripts/build_lambda_package.sh pmf_engine/.lambda_build

# Deploy Lambda
cd pmf_engine/.lambda_build && zip -r /tmp/dispatch_lambda.zip .
AWS_PROFILE=work aws lambda update-function-code \
  --function-name pmf-engine-dispatch-dev \
  --zip-file fileb:///tmp/dispatch_lambda.zip --region us-west-2

# Build + push Docker image
docker build --platform linux/arm64 -f pmf_engine/Dockerfile \
  -t 333022194791.dkr.ecr.us-west-2.amazonaws.com/gp-ai-projects:pmf-engine-dev .
AWS_PROFILE=work aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin 333022194791.dkr.ecr.us-west-2.amazonaws.com
docker push 333022194791.dkr.ecr.us-west-2.amazonaws.com/gp-ai-projects:pmf-engine-dev
```

**5b. gp-api**

Push branch, deploy to dev via CodeBuild or PR preview.

**5c. gp-webapp**

Push branch, Vercel auto-deploys preview.

### 6. Verify end-to-end

1. Open the webapp on dev
2. Navigate to AI Insights dashboard
3. Click "Generate Report" on the new experiment tab
4. Watch for PENDING → RUNNING → SUCCESS
5. Verify the results render correctly
6. Check CloudWatch logs for the Fargate task: `/ecs/pmf-engine-dev`
7. Check the S3 artifact: `aws s3 cp s3://gp-agent-artifacts-dev/{experiment_id}/{run_id}/{experiment_id}.json -`

## Keeping in Sync

The instruction file exists in two places:
- `runbooks/books/pmf-engine/instructions/{experiment_id}.md` — for local runs
- `gp-ai-projects/pmf_engine/runner/experiments/instructions/{experiment_id}.md` — for Fargate

Same for the contract schema:
- `runbooks/books/pmf-engine/contracts/{experiment_id}.json` — for local validation
- `gp-ai-projects/pmf_engine/runner/experiments/{experiment_id}.py` (inline in EXPERIMENT dict) — for Fargate

When you update an instruction or schema, update both. The runbook copy is the prototyping ground — iterate there first, then copy to gp-ai-projects when stable.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `test_registry_consistency` fails | Dispatch registry and full registry have mismatched values (model, timeout, s3_key_template) |
| TypeScript errors after adding to `EXPERIMENT_IDS` | Update all `Record<ExperimentId, ...>` maps — compiler tells you which ones |
| Fargate task fails but worked locally | Check env vars (DATABRICKS_*, ANTHROPIC_API_KEY) are set in the ECS task definition |
| Contract violation on Fargate but not locally | Schema in `EXPERIMENT` dict may differ from `books/pmf-engine/contracts/` JSON — sync them |
