# Runbooks

A standalone collection of reusable runbooks and scripts for AI agents.

## Project Structure

```
runbooks/
├── books/               # Procedures and reference docs (markdown) — read-only-when-asked
│   ├── INDEX.md         # Routing table — read this first to find the right procedure (covers books/ AND commands/)
│   ├── .env.example     # Non-sensitive config (paths, regions, org names)
│   └── .env             # AI agents MAY read this
├── commands/            # Procedures that ALSO register as Claude Code slash commands via install.sh
│                        # Same shape as books/; difference is invocation surface, not content
├── scripts/
│   ├── INDEX.md         # Script inventory — what each script does and which procedure uses it
│   ├── .env.example     # Secrets and credentials for script execution
│   ├── .env             # AI agents MUST NOT read this
│   ├── python/          # Python scripts — managed by uv (pyproject.toml)
│   ├── node/            # Node scripts — managed by nvm + npm (package.json, .nvmrc)
│   └── shell/           # Shell scripts — no runtime manager
├── install.sh           # Symlinks (or copies) commands/*.md into a Claude Code commands dir
└── CLAUDE.md
```

When given a task, start by reading `books/INDEX.md` to find the relevant procedure. The index routes to both `books/` and `commands/` — the agent should treat both the same way when reading.

## Used by the delegate worker

The `ops/delegate/worker` clones this repo at boot via the GitHub App token and sets `RUNBOOKS_DIR=/app/runbooks` in the agent environment. Updates to `commands/*.md` propagate to the bot on the next agent run with no `ops` redeploy. See `ops/delegate/worker/entrypoint.ts` for the clone step and `ops/delegate/README.md` for the operator runbook.

This is the only first-party consumer that pins specific paths into this repo's content. Other consumers should treat the repo as cloneable to anywhere.

## Rules

### Standalone Project
Procedures and references in `books/` and `commands/` are self-contained. Do not reference or link to external repositories, file paths outside this repo, or project-specific directories from those documents. Users clone this repo wherever they want — never assume a specific path.

Exception: the top-level `CLAUDE.md` may include a dedicated "Used by" section that names first-party consumers (e.g., bots and services that clone this repo at boot), so maintainers know where the runbooks are read from. Keep individual procedures clean.

### Books

Books are markdown files in `books/`. There are two types:

**Procedures** (`proc`) — step-by-step workflows for accomplishing a task:
- Keep focused — one procedure per workflow or concern
- Name by the action, not the topic (`query-voter-data.md` not `voter-data.md`)
- List prerequisites (tools, access, permissions) before the steps
- Should be concise and actionable — prefer examples over lengthy explanations

**References** (`ref`) — informational docs for lookup and context:
- Name by the topic (`platform-overview.md`)
- Can be broad — covering an entire system or domain is fine
- May reference external codebases, file paths, and infrastructure (that's the point)
- Keep accurate — stale reference docs are worse than none

**Shared rules for both types:**
- Every book starts with a one-line summary of what it does
- May reference scripts in `scripts/` by relative path (e.g., `scripts/example.py`)
- Should be self-explanatory without requiring external context
- Books can reference other books (`see books/vpn.md`) but should still work standalone
- Avoid deep reference chains — if book A requires B which requires C, something's wrong

### Commands

Commands are markdown procedures in `commands/` that *also* register as Claude Code slash commands via `install.sh`. Same shape as books — the difference is invocation surface, not content.

- A `commands/<name>.md` file is invokable as `/<name>` after the user runs `./install.sh`
- Without install, agents read `commands/<name>.md` directly the same way they read books
- All **shared rules for books** above apply to commands as well — one-line summary, kebab-case naming, self-explanatory, no deep reference chains
- Commands are usually procedures (`proc`); they should not be references (`ref`)
- Commands run from arbitrary working directories (the user invoked `/<name>` from some other project), so each command must include a "Where this runs" block at the top that resolves the runbooks repo path via `$RUNBOOKS_DIR` (with fallbacks)
- Add a row to `books/INDEX.md` under `Procedure: commands/<name>.md` with trigger keywords, same as for books
- When adding a new command, no `install.sh` change is required — it picks up `commands/*.md` automatically
- Commands header convention: start the file with `<!-- v<N> — <YYYY-MM-DD> -->` so reviewers can spot major revisions in the file itself
- The "Where this runs" / `$RUNBOOKS_DIR` resolution block is duplicated by design (slash commands run with only their own file in context, so a shared helper file would create a chicken-and-egg dependency). Each copy is wrapped in `<!-- BEGIN: resolve-runbooks-dir -->` … `<!-- END: resolve-runbooks-dir -->` markers so future bulk-edits across `commands/*.md` are mechanical — keep them in sync

### Scripts
- Reusable code that books reference
- If a runbook needs inline code longer than a few lines, extract it to `scripts/` instead
- Scripts should be runnable independently where possible
- Scripts should be safe to run multiple times (idempotent) where possible
- Note clearly if a script is destructive or non-reversible
- When adding or removing scripts, update `scripts/INDEX.md`
- Scripts are organized by language, each with its own runtime and dependency management:
  - `scripts/python/` — use `uv` (`uv sync` to install, `uv run` to execute)
  - `scripts/node/` — use `nvm` for Node version (`.nvmrc`), `npm` for packages
  - `scripts/shell/` — plain bash, list required tools at the top of each script
- Add new dependencies to the appropriate `pyproject.toml` or `package.json`
- Never install packages globally — always use the language-specific manager

### Environment Variables
- This repo has two `.env` files with different trust levels:
  - `books/.env` — non-sensitive config (paths, regions, org names). AI agents MAY read this to resolve `$VARIABLES` in books.
  - `scripts/.env` — secrets and credentials for script execution. AI agents MUST NEVER read this.
- When a book references `$VARIABLES`, resolve them from `books/.env`
- When a script needs secrets, it reads from `scripts/.env` at runtime
- Each book should list which `books/.env` vars it requires in its prerequisites

### Security
- Never commit `.env` files — only `.env.example`
- Never hardcode sensitive information in books or scripts
- Use `$VARIABLE` placeholders when referencing any user-specific values
- If a runbook requires credentials, document which env vars are needed without including values
- This repo is private as an extra safeguard, but write as if it were public

### Portability
- No hardcoded usernames, machine names, or OS-specific absolute paths
- Use `$HOME`, relative paths, or clearly marked placeholders
- Procedures must not assume a specific directory structure outside this repo
- References may reference external paths when documenting external systems

### Naming
- Use kebab-case for filenames (`deploy-ecs.md`, not `Deploy ECS.md`)
- Procedures: name by the action (`query-voter-data.md`, `debug-peerly-errors.md`)
- References: name by the topic (`platform-overview.md`, `aws-infrastructure.md`)

### Adding a New Book or Command

1. Create the markdown file in `books/` (read-when-asked) **or** `commands/` (also `/<name>`-invokable) following the appropriate template below
2. Add a row to `books/INDEX.md` with type, trigger keywords, path (`books/...` or `commands/...`), and description
3. If it references a new script, create it in the appropriate `scripts/` subdirectory and add it to `scripts/INDEX.md`
4. If it needs new env vars, add them to the appropriate `.env.example`
5. Commands only: prepend the `<!-- v1 — <YYYY-MM-DD> -->` header and include the "Where this runs" block that resolves `$RUNBOOKS_DIR`

**Procedure template:**

```markdown
One-line summary of what this procedure accomplishes.

## Prerequisites

**books/.env variables**: `$VAR1`, `$VAR2`
**scripts/.env variables**: `SECRET_1`, `SECRET_2`
**Tools**: list any required CLIs or access

## Steps

1. First step
2. Second step

## Troubleshooting

Common failure → fix
```

**Reference template:**

```markdown
# Topic Name

One-line summary of what this reference covers.

## Prerequisites

**books/.env variables**: `$VAR1`, `$VAR2`

## Section

Tables, code blocks, and structured content for quick lookup.
```

### Maintenance
- Delete stale runbooks rather than marking them deprecated — git history preserves them
- Don't commit dated snapshots — that's what git history is for

### Audience
- Write for AI agents as the primary reader, humans as secondary
- Be explicit — don't assume the reader has context about your infrastructure

### Writing Style
- Procedures should be concise and actionable — prefer examples over lengthy explanations
- References should be scannable — use tables, headers, and code blocks for quick lookup

---

## Active workstream: meeting_briefing experiment + qa-spine

Two related workstreams. **Read this section before working on either.** Last updated 2026-05-18.

### Branch state

| Branch | Worktree | What's there |
|---|---|---|
| `briefing-tone-style-content` | main repo at `/Users/melecia/Research/runbooks/` | 3 commits ahead of `origin/develop`. Pushed. Round-4 PM voice/tone prompt edits to `experiments/meeting_briefing/{instruction.md, manifest.json}` (incl. `constituent_quote` schema field). `validate_output.py` now enforces `skip_reasons_allowed`. New `scripts/python/render_briefing.py` (PM-facing markdown renderer). `databricks_query.py` fixed to read `DATABRICKS_TOKEN`. |
| `qa-spine` | separate worktree at `/Users/melecia/Research/runbooks-qa-spine/` | 1 commit ahead of `origin/qa-spine`. Pushed. Product-agnostic QA pipeline. |

Engineering confirmed (2026-05-18) that develop is the production-bound target; our prompt edits go on top.

### QA pipeline architecture (lives on `qa-spine`)

`scripts/python/qa_validate.py` reads a unified meeting_briefing artifact directly (no four-file adapter). Stages:

1. **Deterministic (12 checks, no LLM)**: artifact present, identity fields, priority count, high-weight claims have extracts, **all claims have provenance** (source_ids + source_extracts), citation IDs resolve, source snapshots present, prohibited phrases, **extracts appear in cited source** (bounded substring + rapidfuzz fallback within same cited source — never wanders), **summary-source coherence** (ROUGE-L; default threshold 0.33), **completeness floor**, **polish_grammar** (doubled words, common typos, double spaces).
2. **Phase 1 LLM** (Anthropic by default): per-claim triage into 8 accuracy categories.
3. **Phase 2 LLM** (Gemini by default, adversarial system prompt): escalation for high-weight Phase-1-not-OK only.
4. Writes `qa_bundle.json` with `release_verdict` ∈ {ok, warn, block}. Default exit 0 (non-blocking trial mode); `--enforce-verdict` opts into exit-1/2.

**All product-specific values live in `scripts/python/meeting_briefing_product_spec.json`.** Different product → write a new spec, zero Python changes. Spec controls: identity fields, priority filter, prohibited phrases + paths, claim types + blockable routing, accuracy categories, completeness thresholds, polish patterns, judge names → providers/models.

**Pluggable LLM judges via `QA_JUDGES` env var** (set in `~/Research/.env`):
```
QA_JUDGES=claude:anthropic:claude-sonnet-4-6,gemini:google:gemini-2.5-flash
```
Format `name:provider:model,...`. Spec's `judges.phase1` and `judges.phase2` reference the names. Adding OpenAI / Bedrock / etc. is a small Judge subclass + `PROVIDER_REGISTRY` entry.

### Test run conventions

**LOCAL (preferred for prompt iteration):**

`isolation: worktree` does NOT fork from the local branch HEAD — observed behavior is that it forks from `origin/HEAD` (the remote's default branch, which is `origin/develop` for this repo). So a worktree spawned from `briefing-tone-style-content` will check out at `origin/develop`'s HEAD, missing any local commits ahead of that point. Verify with `git -C .claude/worktrees/agent-<id> rev-parse HEAD` before relying on the run.

Two recipes:

(A) **Quick test against upstream develop state** — use `Agent` with `isolation: worktree`, `subagent_type: general-purpose`, `model: opus`. The temp worktree lands at `.claude/worktrees/agent-<id>/` checked out at `origin/HEAD`. Outputs in its `output/`. Subagent is a fresh Claude SDK instance with no parent context.

(B) **Test against a specific local commit (e.g., your branch HEAD with unmerged work)** — manually create a worktree at the commit you want:

```bash
git worktree add -b <test-branch-name> /Users/melecia/Research/runbooks-<scenario> <commit-sha>
```

Then spawn `Agent` WITHOUT `isolation`, instructing the subagent to operate via absolute paths under that worktree path. The subagent's CWD may reset between Bash calls, so always use absolute paths. Confirm with `do NOT read from /Users/melecia/Research/runbooks/` in the prompt to keep it scoped.

For both recipes:
- `.reference_docs/` is untracked, never appears in worktrees — safe to keep prior outputs there
- After completion: copy `output/*` into `.reference_docs/meeting_briefings_experiment_<YYYYMMDD>_<scenario>/` along with a `prompt_snapshot/` of the instruction.md + manifest.json that were active
- Run QA against the preserved artifact from the `runbooks-qa-spine` worktree

**FARGATE (full production runtime):**

Documented in `books/convert-runbook-to-experiment.md` Section 3. Summary:

1. `AWS_PROFILE=<profile> uv run python scripts/python/publish_experiments.py --env=dev` — uploads `experiments/<id>/` to `s3://agent-experiment-metadata-dev/`. Publishes the FULL set; branch is the curation surface.
2. `aws sqs send-message` to `agent-dispatch-dev.fifo` with `experiment_type=meeting_briefing` + PARAMS. **Note: use `experiment_type` not `experiment_id` — the dispatch Lambda rejects the latter.**
3. Output at `s3://gp-agent-artifacts-dev/meeting_briefing/<RUN_ID>/artifact.json`.
4. Log groups: `/aws/lambda/pmf-engine-dispatch-dev` (dispatch), `/ecs/pmf-engine-dev` (runner), `/ecs/broker-dev` (broker — scope rule violations, connectivity).
5. **The `work` AWS profile is not configured in agent envs** — only the user has AWS access. If using Fargate, the user runs publish + dispatch + fetch; the agent runs QA against the fetched artifact.

### Preserved test artifacts

Look in `.reference_docs/` for prior run outputs:

- `meeting_briefings_experiment_20260515_1831_toffel/` — original Toffel run (sparse extracts, no news, no sentiment, no `meeting_name`/`location`)
- `meeting_briefings_experiment_20260518_toffel_regen/` — fresh Toffel run after Round 4 prompt edits + dev sync (richer extracts at ~96 chars avg, news executed, sentiment populated, all new top-level fields populated)

Each folder has `artifact.json`, `rendered.md`, and `prompt_snapshot/` capturing the instruction + manifest at run time.

### Surprises worth knowing (don't relearn)

- The `gemini-qa-agent` env var name is **lowercase-hyphenated literal**, not `GEMINI_API_KEY`. `qa_validate.py`'s `_resolve_api_key('google')` handles this.
- `scripts/.env` is a **symlink** to `~/Research/.env` (not a copy). Don't replace with a literal file or you'll lose updates. If the symlink is missing or broken, recreate with `ln -sf "$HOME/Research/.env" scripts/.env`.
- `databricks_query.py` reads `DATABRICKS_TOKEN`, NOT `DATABRICKS_API_KEY`. A subagent worktree off an older commit may still have the bug.
- `briefing_type` enum (`city_council_meeting` | `county_legislature_meeting` | `school_board_meeting`) does NOT include `town_meeting`. Brookline Town Meeting maps to `city_council_meeting` as closest fit with `briefing_type_closest_fit` run_decision.
- The "qa-spine" pre-existed our work as a POC by the user (a research data scientist pushing prod QA across the team). We turned it product-agnostic and added 5 new deterministic checks.
- **Fargate runtime is single-agent.** Phase 2 same-family adversarial (different Anthropic model + adversarial Phase 2 system prompt) is the in-Fargate production path. Cross-family Phase 2 deferred until/if multi-provider Fargate exists.
- The `wrong` profile name for AWS in this environment is `work`. The user's working profile name appears to be `goodparty`. Confirm with the user before dispatching.

### What's deferred

See `.reference_docs/qa_todo.md` for the live list with status. Headline items as of 2026-05-18:

- Phase 1 + Phase 2 LLM stages wired but **never run with real API tokens** (~$0.10–0.50 per run estimated)
- Haystaq sentiment presentation format (raw 0-100 vs tiered vs support/oppose pair)
- Constituent quote source pipeline (schema slot exists; data source doesn't)
- Kemah/Thorne test run (abandoned mid-Fargate-dispatch 2026-05-18; can resume locally — agent was already finding substantive items including a US DOT SS4A grant resolution)
