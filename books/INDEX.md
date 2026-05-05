# Book Index

Read this first when given a task. Match keywords to find the right book.

## Routing Rules

1. First, choose the primary book from the Routing Table.
2. Then, check whether any companion books apply.
3. If the task involves generation, experiments, evaluations, comparisons, or production-candidate outputs, also read `books/qa-protocol.md`.
4. The companion book does not replace the primary book. It adds QA obligations to the task.

## Companion Books

These books are invoked in addition to the primary routed book.

| Companion Book | Invoke When | Purpose |
|---|---|---|
| books/qa-protocol.md | Any experiment, generation run, briefing creation, eval, comparison, or production-candidate output | Defines QA artifacts, evidence capture, claim traceability, scoring, and pre/post-generation checks |


## Routing Table



| Type | Trigger Keywords | Book | Description |
|------|------------------|------|-------------|
| ref | platform, architecture, services, how services connect, codebases, infrastructure, AWS, ECS, RDS, S3, SQS, deployment, integrations, onboarding flow, path to victory, P2V, P2P, outreach, polling, data platform, dbt | books/platform-overview.md | Complete GoodParty tech ecosystem reference — codebases, service architecture, auth flows, AWS infrastructure, deployment, data pipelines, and end-to-end feature walkthroughs |
| proc | voter, haystaq, scores, flags, databricks, L2, voter data, quick query, issue scores | books/query-voter-data.md | Quick-query Haystaq voter data (scores, flags, demographics) via Databricks |
| ref | grafana, traces, metrics, alerts, tempo, prometheus, loki, spans, connection pool, histogram, alert history, TraceQL | books/query-grafana.md | Query Grafana Cloud for traces, metrics, and alert history via the API |
| proc | circle, community, engagement, members, posts, comments, social media, circle.so | books/connect-circle-api.md | Query the Circle Admin API v2 for community engagement — spaces, posts, comments, members |
| proc | dau, mau, wau, stickiness, retention, cohort, engagement snapshot, circle report, community health | books/circle-engagement-snapshot.md | Generate Circle community engagement snapshot — DAU/WAU/MAU, stickiness, contribution mix, cohort retention, top spaces/contributors |

## Types

- **proc** — step-by-step procedure for accomplishing a task
- **ref** — informational reference for lookup and context

## Quick Decisions

```
No match? → Ask the user or proceed without a book
```
