## Project: Deep Insight Ops
## Implementation Plan

---

## Principles

1. **Infrastructure is installed by the infra team.** The developer provides `deploy_ops.sh`; the infra team executes it. Same pattern as existing `deploy.sh`.
2. **Notifications first, dashboard second.** Phase 1A delivers job tracking and email notifications. Phase 1B adds the admin dashboard. This order ensures value is delivered early — admins get notified even before the dashboard exists.
3. **Non-breaking changes only.** All DynamoDB/SNS calls in `app.py` are wrapped in try/except so failures never affect the existing analysis workflow.
4. **Zero changes to `managed-agentcore/`.** All instrumentation happens at the Web Server layer.
5. **Maximum decoupling.** Ops Admin code lives in `deep-insight-web/ops/` as a self-contained module. The only coupling to `app.py` is 3 imports and 3 function calls. Removing the `ops/` folder and the imports leaves the Web UI fully functional.
6. **Env var preservation.** `deploy.sh` must read existing env vars from the current task definition and merge them with its base vars. This prevents `deploy_ops.sh`-added env vars (e.g., `DYNAMODB_TABLE_NAME`) from being wiped on redeploy.

---

## Folder Structure

```
deep-insight-web/
├── app.py                      # Existing + 3 imports + 3 function calls
├── static/                     # Web UI static files (unchanged)
├── deploy.sh                   # Web UI deployment (unchanged)
├── ops/                        # Ops Admin — self-contained module
│   ├── __init__.py
│   ├── job_tracker.py          # DynamoDB write functions (Start, Link, Failed)
│   ├── admin_router.py         # FastAPI APIRouter for /admin/* routes
│   ├── auth.py                 # Cognito JWT middleware
│   ├── static/                 # Admin dashboard HTML/JS/CSS
│   │   ├── login.html
│   │   ├── jobs.html
│   │   └── job.html
│   ├── deploy_ops.sh           # Ops infrastructure (DynamoDB, SNS, Lambda, IAM)
│   └── lambda/
│       └── job_complete.py     # Lambda function code
├── Dockerfile
└── requirements.txt
```

**Coupling points in `app.py`** (minimal):
```python
from ops.job_tracker import track_job_start, track_job_link, track_job_failure
from ops.admin_router import admin_router
app.include_router(admin_router)
```

---

## Phase 1A: Job Tracking & Email Notifications

### Step 1: Infrastructure Deployment Script (`deploy_ops.sh`)

**Goal**: Write `deep-insight-web/ops/deploy_ops.sh` for the infra team to provision all Ops AWS resources.

**File**: `deep-insight-web/ops/deploy_ops.sh`

**Pattern**: Same as existing `deploy.sh` — imperative AWS CLI calls, idempotent (safe to re-run), with cleanup mode.

**Usage**:
```bash
bash ops/deploy_ops.sh admin1@x.com admin2@x.com   # First deploy (multiple emails OK)
bash ops/deploy_ops.sh                              # Redeploy (updates Lambda code + ECS task def)
bash ops/deploy_ops.sh cleanup                      # Remove all Ops resources
```

On first deploy vs redeploy:

| Resource | First Deploy | Redeploy |
|----------|-------------|----------|
| DynamoDB table + GSIs | Created | Skipped (already exists) |
| SNS topic | Created | Skipped (already exists) |
| SNS subscriptions | Created (emails from args) | Skipped (no email args) |
| Lambda IAM role + policy | Created | Skipped (already exists) |
| Lambda function | Created | **Updated** (zips and uploads latest `ops/lambda/`) |
| S3 event notification | Created | Skipped (already exists) |
| ECS task role policy | Created (DynamoDB + SNS) | Skipped (already exists) |
| ECS task definition | **New revision** (adds env vars) | Skipped (no env var changes) |

**Adding subscribers later** (documented in script output and guide):
```bash
# Add SNS email subscriber (receives job completion/failure emails):
aws sns subscribe --topic-arn <ARN> --protocol email --endpoint new-admin@x.com
# → New subscriber receives confirmation email, must click to activate

# Add Cognito admin user (can log into dashboard):
aws cognito-idp admin-create-user --user-pool-id <ID> --username new-admin@x.com --desired-delivery-mediums EMAIL
# → New admin receives welcome email with temporary password
# → First login: enter temporary password → prompted to set permanent password

# Example: Add co-worker "alice" to both notifications and dashboard
aws sns subscribe --topic-arn arn:aws:sns:us-west-2:XXXXXXXXXXXX:deep-insight-job-notifications \
    --protocol email --endpoint alice@example.com
aws cognito-idp admin-create-user --user-pool-id us-west-2_XXXXXXXXX \
    --username alice@example.com --desired-delivery-mediums EMAIL
```

**Resources created by the script** (in order):

| Step | Resource | Name | CLI Command |
|------|----------|------|-------------|
| 1 | DynamoDB Table | `deep-insight-jobs` (PAY_PER_REQUEST, PK: `job_id`, 2 GSIs) | `aws dynamodb create-table` |
| 2 | SNS Topic | `deep-insight-job-notifications` | `aws sns create-topic` |
| 3 | SNS Subscription | (admin email) | `aws sns subscribe` |
| 4 | Lambda IAM Role | `deep-insight-ops-lambda-role` | `aws iam create-role` + `put-role-policy` |
| 5 | Lambda Function | `deep-insight-job-complete` (Python 3.12, zipped from `ops/lambda/`) | `aws lambda create-function` |
| 6 | S3 Event Notification | Prefix + suffix filter → Lambda | `aws s3api put-bucket-notification-configuration` |
| 7 | DynamoDB + SNS Policy | Add to existing `deep-insight-web-task-role` | `aws iam put-role-policy` |
| 8 | ECS Task Definition | Add `DYNAMODB_TABLE_NAME`, `SNS_TOPIC_ARN` env vars, re-register + update service | `aws ecs register-task-definition` |

**Pre-check**: Script reads existing S3 notification configuration and merges (not overwrites) with new Lambda trigger.

**Cleanup**: `deploy_ops.sh cleanup` removes all resources in reverse order.

**Acceptance**: Script runs successfully, admin confirms SNS subscription email, Lambda can be invoked manually.

---

### Step 2: Job Tracker Module

**Goal**: Create `ops/job_tracker.py` with DynamoDB write functions, and add 3 calls in `app.py`.

**New file**: `deep-insight-web/ops/job_tracker.py`

**Functions**:

```python
def track_job_start(upload_id, query, data_filename="", column_def_filename=""):
    """Write Start record to DynamoDB. Non-breaking (try/except)."""

def track_job_link(upload_id, session_id):
    """Link session_id to existing job record. Non-breaking."""

def track_job_failure(upload_id, error_message):
    """Mark job as Failed with error_message. Non-breaking."""
```

All functions:
- Read `DYNAMODB_TABLE_NAME` from environment
- Skip silently if `DYNAMODB_TABLE_NAME` is empty (Ops not deployed)
- Wrap all DynamoDB calls in try/except — failures log a warning but never block the analysis

**Changes to `app.py`** (minimal):

1. Add imports:
   ```python
   from ops.job_tracker import track_job_start, track_job_link, track_job_failure
   ```

2. In `analyze()`, before returning `StreamingResponse`:
   ```python
   track_job_start(request.upload_id, request.query)
   ```

3. In `agentcore_sse_generator()` at `workflow_complete`:
   ```python
   track_job_link(upload_id, session_id)
   ```
   Note: `upload_id` must be passed into `agentcore_sse_generator()` as a new parameter.

4. In `agentcore_sse_generator()` at `except`:
   ```python
   track_job_failure(upload_id, str(e))
   ```

**Dockerfile**: Add `COPY ops/ ops/` to `deep-insight-web/Dockerfile`.

**Acceptance**: After `/analyze`, a DynamoDB record appears with `status: Start`. After `workflow_complete`, `session_id` is linked. On SSE error, `status: Failed` with `error_message`.

---

### Step 3: Job Tracker — Notification on Failure

**Goal**: When `track_job_failure()` is called, also send an SNS notification for immediate failure alerts.

**File**: `deep-insight-web/ops/job_tracker.py`

**Changes**:

- `track_job_failure()` publishes to SNS topic (if `SNS_TOPIC_ARN` env var is set)
- SNS message includes: job_id, error_message, query summary
- This provides immediate failure notification without waiting for Lambda
- Success notifications are handled by Lambda (Step 4) since it has access to full execution stats

**Acceptance**: When an analysis fails, admin receives a failure notification email immediately.

---

### Step 4: Lambda Function — Job End + SNS Notification

**Goal**: Write the Lambda function that triggers on `token_usage.json` upload, updates DynamoDB, and sends SNS notification.

**File**: `deep-insight-web/ops/lambda/job_complete.py`

**Logic**:

1. **Trigger**: S3 PUT event, filtered by prefix `deep-insight/fargate_sessions/` and suffix `token_usage.json`
2. **Extract `session_id`**: Parse from S3 key path (`deep-insight/fargate_sessions/{session_id}/output/token_usage.json`)
3. **Read `token_usage.json`**: Extract `total_tokens`, `cache_hit_rate` from the JSON
4. **List artifacts**: S3 `list_objects_v2` on `deep-insight/fargate_sessions/{session_id}/artifacts/` to get output file list
5. **Find DynamoDB record**: Query `SessionIdIndex` GSI with `session_id` to get `job_id`
6. **Idempotency guard**: If record status is already `Success`, log and skip (prevents duplicate SNS emails from S3 event retries or versioned object re-uploads)
7. **Update DynamoDB record**:
   - `status: Success`
   - `ended_at`: current epoch seconds
   - `elapsed_seconds`: `ended_at - started_at`
   - `total_tokens`, `cache_hit_rate`: from `token_usage.json`
   - `report_path`, `report_filename`: first `.docx` or `.txt` in artifacts
   - `output_files`: list of all artifact filenames
8. **Publish to SNS**: Job completion message with job_id, status, query summary, duration, token usage

**SNS Message Format** (plain text):
```
Deep Insight Job Completed

Job ID: {job_id}
Status: Success
Query: {user_query (first 100 chars)}
Duration: {elapsed_seconds}s
Tokens: {total_tokens}
Report: {report_filename}
```

**Acceptance**: After a successful analysis, Lambda triggers, DynamoDB shows `status: Success`, and admin receives email.

---

### Step 5: End-to-End Test (Phase 1A)

**Goal**: Verify the full job tracking + notification flow.

**Test Scenarios**:

1. **Happy path**: Submit analysis → DynamoDB shows `Start` → `workflow_complete` links `session_id` → Lambda triggers on `token_usage.json` → DynamoDB shows `Success` → Admin receives email
2. **Failure path**: Submit analysis with invalid data → SSE error → DynamoDB shows `Failed` with error_message → (No Lambda trigger since no `token_usage.json`)
3. **Non-breaking**: Temporarily set `DYNAMODB_TABLE_NAME` to empty string → analysis works normally, no DynamoDB writes, no errors

**Acceptance**: All 3 scenarios pass. Phase 1A is complete.

---

## Phase 1B: Admin Dashboard

### Step 6: Cognito Infrastructure (`deploy_ops.sh` Phase 1B section)

**Goal**: Add Cognito resource creation to `deploy_ops.sh`.

**File**: `deep-insight-web/ops/deploy_ops.sh` (add Phase 1B section)

**Resources added to the script**:

| Step | Resource | Name | CLI Command |
|------|----------|------|-------------|
| 9 | Cognito User Pool | `deep-insight-ops-admins` (no self-signup) | `aws cognito-idp create-user-pool` |
| 10 | Cognito User Pool Client | `deep-insight-ops-web` (public, PKCE) | `aws cognito-idp create-user-pool-client` |
| 11 | Cognito Admin User | (admin email) | `aws cognito-idp admin-create-user` |
| 12 | ECS Task Definition | Add `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID` env vars | `aws ecs register-task-definition` |

**Usage**: `bash ops/deploy_ops.sh` (re-run adds Cognito resources if not yet created)

**Acceptance**: Admin user can authenticate via Cognito `InitiateAuth` API.

---

### Step 7: Admin Backend — Auth Middleware + API Routes

**Goal**: Create the admin API as a self-contained FastAPI `APIRouter`.

**New files**:
- `deep-insight-web/ops/admin_router.py` — all `/admin/*` routes
- `deep-insight-web/ops/auth.py` — Cognito JWT validation middleware

**Dependency**: Add `PyJWT[cryptography]` to `requirements.txt` (RS256 JWT verification).

**Changes to `app.py`** (one line):
```python
from ops.admin_router import admin_router
app.include_router(admin_router)
```

**`ops/auth.py`**:
- FastAPI dependency that validates JWT from HTTP-only cookie
- Verifies JWT signature against Cognito JWKS endpoint (public keys cached)
- Returns 401 if invalid or missing
- Reads `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID` from environment
- Applied to all `/admin/*` routes via `dependencies=[Depends(require_admin)]` on the router

**`ops/admin_router.py`** routes:
- `GET /admin/login` — Serve login page (HTML from `ops/static/login.html`). No auth required.
- `POST /admin/login` — Authenticate via Cognito `InitiateAuth`. No auth required.
  - On success (`AuthenticationResult`): set JWT cookie, redirect to `/admin/api/jobs`
  - On `NEW_PASSWORD_REQUIRED` challenge: return change-password form
- `POST /admin/change-password` — Handle first-login password change. No auth required.
  - Calls Cognito `RespondToAuthChallenge` with new password
  - On success: set JWT cookie, redirect to dashboard
- `POST /admin/logout` — Clear JWT cookie
- `GET /admin/api/jobs` — Query DynamoDB `StatusStartedIndex` GSI, return job list JSON
  - Query parameter: `status` (optional filter: Start, Success, Failed)
  - Default: all statuses, sorted by `started_at` descending
- `GET /admin/api/jobs/{job_id}` — Get single job record from DynamoDB

**First login flow** (new admin user created by infra team):
```
1. Cognito sends welcome email → admin gets temporary password
2. Admin goes to /admin/login, enters email + temporary password
3. POST /admin/login → Cognito returns NEW_PASSWORD_REQUIRED challenge
4. App shows change-password form (ops/static/login.html switches view)
5. Admin enters new password
6. POST /admin/change-password → Cognito RespondToAuthChallenge → JWT returned
7. Cookie set, redirect to dashboard
```

**Cookie security flags** (set at `POST /admin/login`):
```python
response.set_cookie(
    key="token",
    value=jwt_token,
    httponly=True,       # JS cannot read (XSS protection)
    samesite="Lax",      # CSRF protection — cross-origin POST blocked
    path="/admin",       # Only sent on /admin/* requests
    secure=False,        # False for HTTP (Phase 2: True when HTTPS added)
    max_age=3600,        # 1 hour, matches Cognito token expiry
)
```

**Security notes**:
- **XSS**: HTTP-only cookie prevents JavaScript from reading the token
- **CSRF**: `SameSite=Lax` blocks cross-origin POST. GET returns JSON with no CORS headers (browser blocks cross-origin reads)
- **HTTP plaintext**: JWT travels unencrypted, but VPN-only access mitigates. Phase 2: add HTTPS + `secure=True`
- **Cookie scope**: `path="/admin"` ensures token is not sent on Web UI requests
- **Phase 1 acceptable risk**: Read-only dashboard, VPN-only, 1-3 admins
- **Phase 2 upgrades**: HTTPS + `Secure` flag, MFA, CSRF tokens for mutations, token refresh rotation

**Acceptance**: Authenticated admin can call `/admin/api/jobs` and see job records. Unauthenticated requests return 401.

---

### Step 8: Admin Dashboard UI

**Goal**: Build the admin dashboard HTML/CSS/JS pages.

**Files**: `deep-insight-web/ops/static/`

**Pages**:

1. **Login page** (`login.html`):
   - Email + password form
   - Dark theme matching existing UI
   - Error message display

2. **Job list page** (`jobs.html`):
   - Table: Status | Query | Data File | Started | Duration | Tokens | Cache Hit
   - Status filter buttons (All / Start / Success / Failed)
   - "Stale" warning badge for Start jobs older than 30 minutes
   - Auto-refresh every 30 seconds (polling `/admin/api/jobs`)
   - Click row → navigate to detail page

3. **Job detail page** (`job.html`):
   - All DynamoDB attributes displayed
   - Download links for artifacts (using existing `/download/{session_id}/{filename}`)
   - Back button to job list

**Design**:
- Reuse existing dark theme (colors, fonts, layout patterns from `static/`)
- Plain HTML/JS — no framework
- Responsive layout for desktop (mobile not required for 1-3 admins)

**Acceptance**: Admin can log in, view job list, filter by status, and see job details.

---

### Step 9: Deploy & End-to-End Test (Phase 1B)

**Goal**: Deploy the complete Phase 1 system and verify.

**Deployment Steps**:

1. Update ECS Task Definition with new environment variables (`DYNAMODB_TABLE_NAME`, `SNS_TOPIC_ARN`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`)
2. Deploy updated `deep-insight-web` via `deploy.sh`
3. Wait for ECS service stability

**Test Scenarios**:

1. **Auth**: Admin can log in, unauthenticated user gets redirected to login
2. **Job list**: Dashboard shows existing jobs from Phase 1A testing
3. **Real-time tracking**: Submit new analysis → job appears as "Start" in dashboard → updates to "Success" after completion
4. **Stale indicator**: Job stuck in "Start" for 30+ minutes shows "Stale" warning
5. **Detail view**: Click job → see all attributes, download artifacts
6. **Notification**: Admin receives email on job completion/failure

**Acceptance**: All scenarios pass. Phase 1 is complete.

---

## Summary

| Step | Phase | What | File(s) | Who |
|------|-------|------|---------|-----|
| 1 | 1A | Infrastructure Script (`deploy_ops.sh`) | `ops/deploy_ops.sh` | Developer writes, infra team runs |
| 2 | 1A | Job Tracker Module (Start, Link, Failed) | `ops/job_tracker.py`, `app.py` (+3 calls) | Developer |
| 3 | 1A | Failure Notification (SNS from tracker) | `ops/job_tracker.py` | Developer |
| 4 | 1A | Lambda Function (S3 → DynamoDB + SNS) | `ops/lambda/job_complete.py` | Developer writes, infra team deploys |
| 5 | 1A | End-to-End Test (tracking + notifications) | — | Developer + infra team |
| 6 | 1B | Cognito Infrastructure (add to `deploy_ops.sh`) | `ops/deploy_ops.sh` | Developer writes, infra team runs |
| 7 | 1B | Admin Backend (auth + API router) | `ops/admin_router.py`, `ops/auth.py`, `app.py` (+1 line) | Developer |
| 8 | 1B | Admin Dashboard UI | `ops/static/` | Developer |
| 9 | 1B | Deploy & End-to-End Test | — | Developer + infra team |
