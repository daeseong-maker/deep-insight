## Project: Deep Insight Ops
## Research Findings

This document summarizes research conducted for the Deep Insight Ops business requirements (01_business_requirement).

---

## 1. Strands Agents SDK (v1.19.0) — Relevant Features

### Hooks System (Potential for Job State Tracking)
- The SDK provides a composable hook system (`strands.hooks`) with typed lifecycle events:
  - `AgentInitializedEvent`, `BeforeInvocationEvent`, `AfterInvocationEvent`
  - `BeforeToolCallEvent`, `AfterToolCallEvent`
  - `MessageAddedEvent`
- Multi-agent hooks: `MultiAgentInitializedEvent`, `BeforeNodeCallEvent`, `AfterNodeCallEvent`
- **Relevance**: These hooks could emit job lifecycle events to DynamoDB without modifying core graph logic. However, instrumenting at the BFF layer (app.py) is simpler for Phase 1.

### Session Management
- Built-in `S3SessionManager` with structured S3 key hierarchy
- `FileSessionManager` for local development
- Deep Insight currently uses custom global state, not the SDK session managers
- **Relevance**: Not directly useful for job tracking, but worth evaluating for Phase 2.

### Multi-Agent Patterns
- **GraphBuilder** (currently used by Deep Insight): Deterministic graph orchestration with conditional edges, cyclic support, streaming
- **Swarm**: Self-organizing agent teams with shared memory and handoff detection (not currently used)
- **Relevance**: The Phase 2 Ops chatbot could use a simple standalone Agent (no graph needed).

### OpenTelemetry Integration
- Full OTEL tracing: Agent spans > Event loop > Model invoke > Tool call
- Metrics: token usage, tool call counts, duration histograms
- Already integrated in managed-agentcore via `aws-opentelemetry-distro`
- **Relevance**: Complements but does not replace custom job tracking. OTEL provides observability; DynamoDB provides operational state.

---

## 2. A2A Protocol — Applicability Assessment

### What is A2A
- Google's Agent-to-Agent protocol for inter-agent discovery and communication
- JSON-RPC 2.0 over HTTP, Agent Cards at `/.well-known/agent-card.json`
- Task model: submitted → working → input-required → completed → failed → canceled
- Strands SDK has built-in support via `strands.multiagent.a2a` (experimental)
- Amazon Bedrock AgentCore natively supports A2A protocol

### Assessment: NOT Recommended for Phase 1

| Requirement | A2A Fit |
|-------------|---------|
| F1: Job status dashboard | Poor — A2A has no centralized job registry |
| F2: Job State Store | N/A — A2A is a protocol, not a persistence layer |
| F3: Admin login (Cognito) | Neutral — unrelated |
| F4: Email notification | Poor — A2A has no notification mechanism |
| F5: Recipient management | N/A — pure CRUD |
| F6: Chatbot (Phase 2) | Good fit — Ops agent could use A2A |
| F7: SMS notification | N/A |
| F8: Job cancellation | Partial — A2A defines `tasks/cancel` but Strands executor raises `UnsupportedOperationError` |

### Key Reasons to Defer A2A
1. **Solves a different problem**: A2A is for agent-to-agent interoperability, not admin tooling
2. **Project precedent**: A2A was built as PoC (v1.26.0, a2a-sdk v0.3.22) and then deferred for deep-insight-web because wrapping the graph as a single agent lost custom events (plan_review_request, etc.)
3. **Experimental status**: SDK logs warning about "frequent breaking changes"
4. **Overhead without benefit**: Adds protocol complexity for a simple dashboard that just reads from DynamoDB

### Where A2A Makes Sense (Future)
- Phase 2+ Ops chatbot querying status via natural language
- Integration with external agent systems (Text2SQL, RAG, DataPipeline) per the existing hybrid architecture design
- Multi-team, multi-framework agent ecosystems

### References
- AWS Blog: https://aws.amazon.com/blogs/machine-learning/introducing-agent-to-agent-protocol-support-in-amazon-bedrock-agentcore-runtime/
- AWS Docs: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html
- Google A2A spec: https://google-a2a.github.io/A2A/latest/
- Project PoCs: docs/front-end/02-technical-proof-points.md (PoC 1-3)
- Project A2A deferral: docs/front-end/01-plan.md (lines 197-200)

---

## 3. Architecture Decision: Separate App vs Admin Section

### Recommendation: Admin routes in existing `deep-insight-web` (Phase 1)

| Option | Pros | Cons |
|--------|------|------|
| **A: Admin routes in deep-insight-web** | Single deployment, shared config, BFF already sees SSE events | Shared failure domain, weaker security boundary |
| **B: Standalone deep-insight-ops app** | Clean separation, independent scaling | Two deployments, duplicate env vars, more infrastructure |

**Rationale**: For 1-3 admin users, a second ECS service adds operational complexity without benefit. The existing `app.py` already has boto3 clients, IAM permissions, and SSE event parsing. Adding `/admin/*` routes with Cognito middleware is the minimal viable approach.

**Phase 2 exit ramp**: If the ops dashboard grows significantly (chatbot, SMS, cancellation), extract it into a separate service at that point.

---

## 4. Architecture Decision: Job State Tracking

### Recommendation: DynamoDB single table with direct writes from BFF

**Table Design:**
```
Table: deep-insight-jobs (PAY_PER_REQUEST)
PK: job_id (String, UUID)

Attributes:
  - status: submitted | running | plan_review | success | failed
  - user_query: String
  - upload_id: String
  - submitted_at: Number (epoch seconds) — GSI sort key
  - updated_at: Number (epoch seconds)
  - completed_at: Number (epoch seconds, null until done)
  - error_message: String (on failure)
  - report_path: String (on success)
  - ttl: Number (epoch seconds, auto-expire after 90 days)

GSI: StatusIndex
  PK: status
  SK: submitted_at
  Projection: ALL
```

### Instrumentation Point: BFF SSE Relay (app.py)

The `agentcore_sse_generator()` function in `app.py` (lines 233-293) already parses every SSE event as it relays from AgentCore to the browser. This is the natural place to add DynamoDB writes:

```
[analyze() endpoint] → DynamoDB: status=submitted
  → [first SSE event] → DynamoDB: status=running
    → [plan_review_request event] → DynamoDB: status=plan_review
      → [workflow_complete event] → DynamoDB: status=success + SNS notification
      → [error/timeout] → DynamoDB: status=failed + SNS notification
```

**Key benefit**: Zero changes to `managed-agentcore/` runtime code.

### Why Not Event Sourcing (Phase 1)
- At most a few jobs per day (20+ minute sessions)
- Simple status field with `status_history` list attribute provides enough audit trail
- Event sourcing adds complexity without proportional value at this scale

### DynamoDB TTL for 90-Day Retention
- Set `ttl` attribute to `submitted_at + 90 days` (epoch seconds)
- DynamoDB auto-deletes expired items at no cost (within a few hours of expiration)
- Dashboard queries should filter `ttl > current_time` to hide logically-expired items
- For audit archival: DynamoDB Streams → Lambda → S3 Glacier (Phase 2)

---

## 5. Architecture Decision: Notifications

### Recommendation: SNS Topic with Email Subscriptions (Phase 1)

| Option | Simplicity | Phase 2 SMS | Rich Email |
|--------|-----------|-------------|------------|
| **SNS topic** | High | Native | No (plain text) |
| **SES direct** | Medium | No | Yes (HTML) |
| **EventBridge → Lambda → SES** | Low | Via Lambda | Yes (HTML) |

**Rationale**: SNS provides built-in fan-out (multiple subscribers), built-in retry, and SMS support for Phase 2 without code changes. For 1-3 admins receiving plain text notifications, SNS is sufficient.

**Recipient management (F5)**: Map directly to SNS subscribe/unsubscribe APIs. Store subscription ARNs in a DynamoDB table or a simple config.

**Upgrade path**: For rich HTML emails in Phase 2, use SNS → Lambda → SES hybrid.

---

## 6. Architecture Decision: Dashboard Refresh

### Recommendation: Polling at 30-second intervals (Phase 1)

| Option | Latency | Complexity | Infrastructure |
|--------|---------|-----------|----------------|
| **Polling (30s)** | Up to 30s | Very low | None |
| **SSE** | Real-time | Low-medium | ALB idle timeout |
| **WebSocket** | Real-time | Medium-high | Connection store |

**Rationale**: Jobs run 20+ minutes. Admins glance at the dashboard periodically, not watch it continuously. 30-second polling with DynamoDB reads is trivial to implement and costs pennies. The existing app already runs behind ALB on Fargate — polling adds zero infrastructure complexity.

**Upgrade path**: Add SSE endpoint in Phase 2 using existing `StreamingResponse` pattern from `app.py`.

---

## 7. Architecture Decision: Authentication

### Recommendation: Cognito User Pool + BFF JWT Middleware (Phase 1)

**Two viable options depending on HTTPS availability:**

| Option | Requires HTTPS | Code Complexity | UX |
|--------|---------------|-----------------|-----|
| **ALB + Cognito (built-in)** | Yes | None (ALB handles auth) | Redirect to Hosted UI |
| **Custom login + BFF middleware** | No | Low (JWT validation) | Seamless dark-theme login |

**If HTTPS available**: Use ALB listener rule for `/admin/*` → Cognito authenticate action. Zero auth code in the app. ALB injects `x-amzn-oidc-identity` headers.

**If HTTP only (current state)**: Build a login page matching the existing dark theme. Use Cognito `InitiateAuth` API from the BFF. Store JWT in HTTP-only cookie. FastAPI dependency validates JWT on `/admin/*` routes.

**Key principle**: Auth applies only to `/admin/*` routes. Existing Web UI routes remain unchanged (VPN-only access).

### CloudFormation Resources
```yaml
- AWS::Cognito::UserPool (deep-insight-ops-admins)
- AWS::Cognito::UserPoolGroup (admin)
- AWS::Cognito::UserPoolClient (public, PKCE, no secret)
```

---

## 8. Architecture Decision: Event Architecture

### Recommendation: Direct DynamoDB + SNS Writes (Phase 1)

```
BFF (app.py)
  → DynamoDB.update_item() — job state tracking (synchronous, fast)
  → SNS.publish() — notifications (fire-and-forget)
```

**Why not EventBridge**: Deep Insight has one producer (BFF) and two consumers (DynamoDB, SNS). EventBridge is designed for multiple producers and multiple consumers that need decoupling. The operational overhead of EventBridge rules, Lambda functions, and IAM roles is not justified for this simple topology.

**Phase 2 trigger for EventBridge**: If a second client (CLI, mobile) is added as a job submission channel, introduce EventBridge to centralize event routing.

---

## 9. Overall Phase 1 Architecture

```
VPN Users ──────────────┐
                        │
                        ▼
                   ┌────────┐          ┌─────────────────────┐
                   │  ALB   │          │   Cognito User Pool  │
                   │ (HTTP) │          │  (admin group)       │
                   └───┬────┘          └──────────┬──────────┘
                       │                          │ JWT
                       ▼                          │
          ┌────────────────────────────────────────┴──────────────┐
          │              deep-insight-web (FastAPI)               │
          │                                                      │
          │  Existing routes (unchanged):   New admin routes:    │
          │  GET /                          GET /admin/login     │
          │  POST /upload                   POST /admin/login    │
          │  POST /analyze ──┐              GET /admin/jobs      │
          │  POST /feedback  │              GET /admin/jobs/{id} │
          │  GET /artifacts  │              POST /admin/notify   │
          └──────────────────┼──────────────────┬────────────────┘
                             │                  │
           ┌─────────────────┼──────┐           │
           │                 │      │           │
           ▼                 ▼      ▼           ▼
    ┌────────────┐   ┌──────────┐  ┌────────┐  ┌──────────────┐
    │ DynamoDB   │   │AgentCore │  │  S3    │  │  SNS Topic   │
    │ jobs table │   │ Runtime  │  │(data)  │  │ (email/SMS)  │
    └────────────┘   └──────────┘  └────────┘  └──────────────┘
```

### New AWS Resources
1. DynamoDB table: `deep-insight-jobs` (on-demand, TTL enabled)
2. DynamoDB GSI: `StatusIndex` (status + submitted_at)
3. SNS topic: `deep-insight-job-notifications`
4. Cognito User Pool: `deep-insight-ops-admins`
5. IAM policy additions: DynamoDB, SNS, Cognito for existing ECS task role

### Files to Modify
| File | Changes |
|------|---------|
| `deep-insight-web/app.py` | Add admin routes, DynamoDB/SNS clients, Cognito middleware, job tracking in SSE generator |
| `deep-insight-web/deploy.sh` | Add DynamoDB, SNS, Cognito IAM permissions |
| `deep-insight-web/static/` | Add admin dashboard HTML/JS/CSS |
| `managed-agentcore/` | No changes (Phase 1 instruments at BFF layer only) |

---

## References

### AWS Documentation
- DynamoDB Best Practices: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-general-nosql-design.html
- DynamoDB TTL: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/time-to-live-ttl-how-to.html
- SNS Email Notifications: https://docs.aws.amazon.com/sns/latest/dg/sns-email-notifications.html
- Cognito User Pool Groups: https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-user-groups.html
- ALB + Cognito Auth: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/listener-authenticate-users.html
- Bedrock AgentCore A2A: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html

### Project References
- A2A PoC results: docs/front-end/02-technical-proof-points.md
- A2A deferral decision: docs/front-end/01-plan.md (lines 197-200)
- A2A hybrid architecture: managed-agentcore/under_development/a2a_hybrid_architecture.md
- BFF SSE relay: deep-insight-web/app.py (agentcore_sse_generator, lines 233-293)
- Event queue: managed-agentcore/src/utils/event_queue.py
- Fargate coordinator: managed-agentcore/src/tools/global_fargate_coordinator.py
- Strands SDK source: managed-agentcore/production_deployment/scripts/phase3/.venv/lib/python3.12/site-packages/strands/

### External References
- Google A2A Protocol: https://google-a2a.github.io/A2A/latest/
- Strands Agents SDK: https://github.com/strands-agents/sdk-python
- Strands Agents Docs: https://strandsagents.com
