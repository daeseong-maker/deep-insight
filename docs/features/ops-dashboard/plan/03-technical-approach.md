## Project: Deep Insight Ops
## Technical Approach

---

## 1. Phase 1 Architecture: Job Tracking & Notifications

### Principle

Decouple from `managed-agentcore/`. Minimize changes to `app.py`. Use existing signals.

### Three Components

#### 1.1 Job Start — Web Server writes to DynamoDB

- `app.py` `/analyze` endpoint writes one record to DynamoDB with `job_id = upload_id`, status `Start`, and input file info
- This is the Web Server recording its own action, not ops logic

#### 1.2 Job ID Linkage — Web Server writes session_id

- When `app.py` receives the `workflow_complete` SSE event from the runtime, it contains `session_id`
- Web Server writes `session_id` to the existing DynamoDB record (one `update_item` call)
- This links `job_id` (upload_id) to `session_id`, enabling Lambda to find the record later

#### 1.3 Job End — S3 Event triggers Lambda

- The runtime already uploads artifacts (`token_usage.json`, reports) to S3 on completion
- S3 PUT event notification → Lambda function
- Lambda extracts `session_id` from the S3 key path, looks up the DynamoDB record via `SessionIdIndex` (GSI)
- Lambda updates the record: `status: "Success"` or `"Failed"`, execution stats, output artifacts
- Lambda publishes to SNS topic (email/SMS notification)

#### 1.4 Admin Dashboard — Reads from DynamoDB

- Cognito-protected `/admin/*` routes
- Polls DynamoDB every 30 seconds
- Shows job list with status, links to artifacts

### Architecture Diagram

```
app.py /analyze ──(Start)──→ DynamoDB (job_id = upload_id, status: Start)
                                   ↑
app.py workflow_complete ──(Link)──┘ (writes session_id to record)

AgentCore Runtime
  └── uploads to S3 ──→ S3 Event ──→ Lambda ──(End)──→ DynamoDB (via SessionIdIndex GSI)
                                        └──→ SNS ──→ Email/SMS

Admin Browser ──→ Cognito Auth ──→ /admin/jobs ──→ DynamoDB (read)
```

### What Stays Untouched

- `managed-agentcore/` — zero changes
- Existing Web UI — unchanged

### Minimal Changes to app.py

- `/analyze`: One DynamoDB `put_item` call (write Start record)
- `workflow_complete` handler: One DynamoDB `update_item` call (write session_id)

### New AWS Resources

- DynamoDB table (`deep-insight-jobs`)
- Lambda function (S3 event → DynamoDB update + SNS)
- SNS topic (`deep-insight-job-notifications`)
- Cognito User Pool (`deep-insight-ops-admins`)
- S3 event notification configuration

### DynamoDB Table Design

```
Table: deep-insight-jobs (PAY_PER_REQUEST)
PK: job_id (String, UUID)

Written at Start (by Web Server at /analyze):
  - status: Start
  - user_query: String
  - data_filename: String
  - column_def_filename: String
  - data_rows: Number
  - data_columns: Number
  - started_at: Number (epoch seconds)

Written at Link (by Web Server at workflow_complete):
  - session_id: String (AgentCore session ID, received from SSE event)

Written at End (by Lambda, looks up record via SessionIdIndex GSI):
  - status: Success | Failed
  - ended_at: Number (epoch seconds)
  - elapsed_seconds: Number
  - total_tokens: Number
  - cache_hit_rate: Number (percentage)
  - report_path: String (S3 path)
  - report_filename: String
  - output_files: List (all artifact filenames)

Written at Failure (by Web Server SSE error handler):
  - status: Failed
  - ended_at: Number (epoch seconds)
  - error_message: String

GSI: StatusStartedIndex
  PK: status
  SK: started_at
  Projection: ALL

GSI: SessionIdIndex
  PK: session_id
  Projection: KEYS_ONLY
  (Used by Lambda to find record by session_id extracted from S3 path)
```

### Failure Detection

Two mechanisms for Phase 1, zero extra infrastructure:

1. **SSE error handler in `app.py`**: When the SSE stream from AgentCore errors out or disconnects, `app.py` already catches the exception (line 291-293). Write `status: Failed` and `error_message` to DynamoDB at that point. Covers ~95% of failures.

2. **Dashboard "Stale" indicator**: If a job has `status: Start` and `started_at` is older than 30 minutes, the dashboard UI shows a "Stale" warning. No backend change — just a UI calculation. Lets the admin investigate manually.

Phase 2: Add a scheduled Lambda (CloudWatch EventBridge rule) to auto-mark stale jobs as `Failed` if this becomes a recurring problem.

### S3 Event Trigger

Lambda is triggered by S3 PUT with:
- **Prefix**: `deep-insight/fargate_sessions/`
- **Suffix**: `token_usage.json`

`token_usage.json` is the last file the runtime uploads (after graph execution, history printing, and all artifact uploads). It is the most reliable signal that the job is complete. Lambda extracts `session_id` from the S3 key path, reads `token_usage.json` for execution stats, lists the `artifacts/` prefix for output files, then updates DynamoDB via `SessionIdIndex` GSI.

## 2. A2A Protocol

Not recommended for Phase 1. A2A is designed for agent-to-agent interoperability, not admin dashboards. The project already built and deferred A2A (PoC 1-3) because wrapping the graph as a single agent lost custom SSE events (`plan_review_request`, etc.). The SDK marks A2A as experimental with "frequent breaking changes."

Phase 2+ potential: Ops chatbot (F6) could use A2A to query job status via natural language.

## 3. Notifications: SNS

SNS for Phase 1. Reasons:

- Built-in fan-out (multiple email subscribers)
- Built-in retry
- SMS support for Phase 2 without code changes
- Recipient management maps directly to SNS subscribe/unsubscribe APIs
- Plain text email is sufficient for 1-3 admins

The Lambda function (triggered by S3 event at job end) publishes to the SNS topic. Upgrade path: SNS → Lambda → SES for rich HTML emails in Phase 2.

## 4. Dashboard Refresh: Polling

Polling at 30-second intervals for Phase 1. Jobs run 20+ minutes — admins don't need real-time push. 1-3 admins polling = ~6 requests/minute, negligible load on DynamoDB. Stateless — works with ALB and Fargate rolling deployments. Zero infrastructure beyond a `/admin/jobs` endpoint that queries DynamoDB.

Upgrade path: SSE endpoint in Phase 2 using existing `StreamingResponse` pattern from `app.py`.

## 5. Authentication: Cognito

Cognito User Pool with admin accounts created manually (no self-signup). Auth applies only to `/admin/*` routes — existing Web UI remains unchanged (VPN-only access).

Two options depending on HTTPS availability:

- **If HTTPS available**: ALB listener rule for `/admin/*` → Cognito authenticate action. Zero auth code in the app. ALB injects `x-amzn-oidc-identity` headers.
- **If HTTP only (current state)**: Custom login page matching the dark theme + JWT validation middleware in the Web Server. Store JWT in HTTP-only cookie.

Phase 2: Add MFA, federated identity (SAML/OIDC).

## 6. App Structure: Admin Routes in Existing Web Server

Add `/admin/*` routes to existing `deep-insight-web/app.py` for Phase 1. Single deployment — no second ECS service needed. Shared config (S3, region, env vars). 1-3 admin users don't justify separate infrastructure. Security boundary via Cognito middleware on `/admin/*` routes.

Phase 2 exit ramp: Extract to a separate service if ops dashboard grows significantly (chatbot, SMS, job cancellation).

## 7. Admin Dashboard Scope

Phase 1 dashboard is read-only with two views:

### Job List Page (`/admin/jobs`)

Table with columns:

| Status | Query | Data File | Started | Duration | Tokens | Cache Hit |
|--------|-------|-----------|---------|----------|--------|-----------|

- Filterable by status (Start / Success / Failed)
- Sorted by most recent first
- "Stale" warning shown for `Start` jobs older than 30 minutes
- Auto-refreshes every 30 seconds via polling

### Job Detail Page (`/admin/jobs/{job_id}`)

- Full record details (all DynamoDB attributes)
- Links to download artifacts (reuses existing `/download/{session_id}/{filename}` endpoint)
- Token usage summary, cache hit rate

### No Actions in Phase 1

- No retry, cancel, or delete
- Read-only monitoring only
