Review Peerly-related errors and endpoint health in Grafana via the Grafana MCP server.

## Prerequisites

**Tools**: Grafana MCP server connected (datasource UID: `grafanacloud-logs`)
**Context**: Read `books/platform-overview.md` sections on P2P & Outreach and Peerly API Services for full architecture context.

## Grafana Datasource

All queries target Loki: `grafanacloud-logs`. All logs are structured JSON via OpenTelemetry/pino.

Base selector for prod:
```
{service_name="gp-api", deployment_environment_name="prod"}
```

## Key Log Fields

| Field | Where | Values |
|-------|-------|--------|
| `context` | JSON body | NestJS class that emitted the log (see table below) |
| `detected_level` | JSON body | `debug`, `error`, `warn` |
| `request_endpoint` | JSON body | e.g. `POST /v1/p2p/phone-list`, `GET /v1/outreach` |
| `statusCode` | JSON body | HTTP status code returned to client |
| `err_name` | JSON body | Exception class: `BadGatewayException`, `BadRequestException`, etc. |
| `err_message` | JSON body | Human-readable error message |
| `user` | JSON body | User ID that triggered the request |
| `requestId` | JSON body | Unique request ID for correlating log lines within a single request |

## Peerly Service Context Values

| `context` value | Layer | What it covers |
|-----------------|-------|----------------|
| `PeerlyHttpService` | HTTP client | Every outbound Peerly API request (URL, method, headers) |
| `PeerlyAuthenticationService` | Auth | JWT token acquisition and renewal |
| `PeerlyIdentityService` | TCR/10DLC | Identity creation, brand submission, campaign verify, use case checks |
| `PeerlyPhoneListService` | Phone lists | Upload to Peerly, status checking |
| `PeerlyP2pJobService` | P2P jobs | Job creation, list assignment, canvasser requests |
| `PeerlyMediaService` | Media | MMS image uploads |
| `PeerlyErrorHandlingService` | Error handling | Wraps Peerly upstream errors into 502 BadGatewayExceptions |
| `P2pController` | Controller | `/v1/p2p/*` routes — controller-level errors |
| `P2pPhoneListUploadService` | Service | Phone list CSV generation and upload orchestration |
| `CampaignTcrComplianceService` | Service | TCR compliance registration and status checking |
| `QueueConsumerService` | SQS consumer | Background TCR status polling (every 12h) |
| `OutreachService` | Service | Outreach campaign creation (P2P type) |

## Step 1: Get the High-Level Error Counts

Run these four queries to understand the current state. Adjust the time window (`[24h]`, `[7d]`) as needed.

### All Peerly errors (catch-all)
```logql
sum(count_over_time(
  {service_name="gp-api", deployment_environment_name="prod"}
  | json
  | detected_level = `error`
  | context =~ `Peerly.*|P2pController|P2pPhoneList.*`
[24h]))
```

### TCR compliance errors only
```logql
sum(count_over_time(
  {service_name="gp-api", deployment_environment_name="prod"}
  | json
  | detected_level = `error`
  | context =~ `CampaignTcrCompliance.*|PeerlyIdentity.*`
[24h]))
```

### Phone list failures only
```logql
sum(count_over_time(
  {service_name="gp-api", deployment_environment_name="prod"}
  | json
  | detected_level = `error`
  | context =~ `P2pController|P2pPhoneListUpload.*|PeerlyPhoneList.*`
[24h]))
```

### Auth token renewal failures
```logql
sum(count_over_time(
  {service_name="gp-api", deployment_environment_name="prod"}
  | json
  | detected_level = `error`
  | context = `PeerlyAuthenticationService`
[24h]))
```

Use `queryType: instant` for these count queries. Use the `query_loki_logs` tool with `startRfc3339` and `endRfc3339` to set the window.

## Step 2: Read the Actual Error Logs

Once you know which category has errors, pull the log lines to understand what's happening.

### All Peerly errors with details
```logql
{service_name="gp-api", deployment_environment_name="prod"}
  | json
  | detected_level = `error`
  | context =~ `Peerly.*|P2pController|P2pPhoneList.*`
```

### Errors on a specific endpoint
```logql
{service_name="gp-api", deployment_environment_name="prod"}
  | json
  | detected_level = `error`
  | request_endpoint = `POST /v1/p2p/phone-list`
```

### Errors for a specific user
```logql
{service_name="gp-api", deployment_environment_name="prod"}
  | json
  | detected_level = `error`
  | context =~ `Peerly.*|P2pController|P2pPhoneList.*`
  | user = `304129`
```

Use `limit: 20` and `direction: backward` (newest first) when calling `query_loki_logs`.

## Step 3: Correlate by Request ID

When you find an error, grab the `requestId` and pull all log lines for that request to see the full call chain:

```logql
{service_name="gp-api", deployment_environment_name="prod"}
  | json
  | requestId = `<the-request-id>`
```

This shows the full sequence: incoming request → Peerly HTTP calls → responses → error.

## Step 4: Check Peerly Outbound Call Health

To see all outbound Peerly HTTP calls (not just errors):

```logql
{service_name="gp-api", deployment_environment_name="prod"}
  | json
  | context = `PeerlyHttpService`
```

This logs every request with URL, method, and headers. Useful for seeing if calls are being made at all.

## Step 5: Check TCR Background Polling

The SQS consumer polls pending TCR records every 12 hours. To see polling activity:

```logql
{service_name="gp-api", deployment_environment_name="prod"}
  |= "tcrComplianceStatusCheck"
```

To see records that remain stuck (not yet activated):

```logql
{service_name="gp-api", deployment_environment_name="prod"}
  |= "TCR Registration is not active at this time"
```

## Step 6: Check Endpoint Latency and Traffic

To see all completed requests on Peerly-related endpoints:

```logql
{service_name="gp-api", deployment_environment_name="prod"}
  |= "Request completed"
  | json
  | request_endpoint =~ `.*p2p.*|.*tcr.*|.*outreach.*`
```

Each "Request completed" log line includes `responseTimeMs` and `response_statusCode`.

## Known Error Patterns

| Pattern | `err_message` | Meaning | Severity |
|---------|--------------|---------|----------|
| Missing identity ID | `TCR compliance record does not have a Peerly identity ID` | Candidate tried to upload phone list before TCR registration completed. Usually means TCR identity creation failed silently. | Medium — investigate the TCR record |
| Phone list Peerly 400 | `There may be an error with the phone list for context {token}` | Peerly rejected the phone list. Could be bad data, duplicate upload, or Peerly-side issue. | Medium |
| Phone list still processing | `Phone list is still processing. Please try again in a few moments.` | Frontend polling before Peerly finished processing. Often resolves on its own. | Low — usually transient |
| Upload failed (502) | `Failed to upload phone list` | Upstream Peerly API returned an error during CSV upload. | High — check Peerly outbound call logs |
| Auth failure | Errors from `PeerlyAuthenticationService` | Token renewal failed. All downstream Peerly calls will fail. | Critical — immediate investigation needed |

## Reference: gp-api Endpoints That Call Peerly

| Endpoint | Peerly Services Called | Peerly API Endpoints Hit |
|----------|----------------------|--------------------------|
| `POST /v1/campaigns/tcr-compliance` | PeerlyIdentityService (7 calls) | POST /identities, GET /identities/listByAccount, POST /identities/{id}/submitProfile, POST /v2/tdlc/{id}/submit, POST /v2/tdlc/{id}/submit_cv |
| `POST /v1/campaigns/tcr-compliance/:id/submit-cv-pin` | PeerlyIdentityService (3 calls) | POST /v2/tdlc/{id}/verify_pin, POST /v2/tdlc/{id}/create_cv_token, POST /v2/tdlc/{id}/approve |
| `GET /v1/campaigns/tcr-compliance/:id/status` | PeerlyIdentityService | GET /v2/tdlc/{id}/get_usecases |
| `POST /v1/p2p/phone-list` | PeerlyPhoneListService | POST /phonelists |
| `GET /v1/p2p/phone-list/:token/status` | PeerlyPhoneListService | GET /phonelists/{token}/checkstatus, GET /phonelists/{id} |
| `POST /v1/outreach` | PeerlyMediaService, PeerlyP2pJobService | POST /v2/media, POST /1to1/jobs, GET /1to1/agents, POST /1to1/jobs/{id}/assignlist |
| `GET /v1/outreach` | PeerlyP2pJobService | GET /1to1/jobs?identity_id={id} |
| SQS: TCR_COMPLIANCE_STATUS_CHECK | PeerlyIdentityService | GET /v2/tdlc/{id}/retrieve_cv, GET /v2/tdlc/{id}/get_usecases |
