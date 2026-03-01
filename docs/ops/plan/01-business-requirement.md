## Project: Deep Insight Ops

## 1. Background

- Deep Insight is a multi-agent system specialized in data analysis and report generation. Users can request analyses via the Deep Insight Web UI.
- Currently, the system has the following operational limitations:
  - No way to check job execution status (success/failure/in-progress)
  - No visibility into the number of concurrently running jobs
  - No notifications sent to administrators when jobs complete or fail
  - No administrator authentication (currently relies on VPN-only access)

## 2. Job Model Definition

- **Job**: A single data analysis session requested through the Deep Insight Web UI (corresponds to one `invoke_agent_runtime()` call)
- **Job Lifecycle States**:
  ```
  submitted → running → success / failed
  ```
- **Tracked Data Per Job**:
  - Job ID (unique identifier)
  - Requester info (upload_id or user identifier)
  - Submitted timestamp, completed timestamp
  - Status (submitted, running, success, failed)
  - Request query (user_query)
  - Error message (on failure)
  - Result report path (on success)
- **Storage**: No persistent job state mechanism exists today. A new Job State Store must be built (e.g., DynamoDB).

## 3. Objectives

- Administrators can monitor the execution status of all jobs in real time.
- Administrators receive automatic notifications when jobs complete or fail.
- Administrator access is protected by authentication.

## 4. User Scenarios

### Scenario 1: Job Status Monitoring
1. Administrator logs into the admin page.
2. Views the list of currently running jobs and their statuses on the dashboard.
3. Browses history of completed/failed jobs.

### Scenario 2: Notification
1. A user requests a new analysis via the Web UI.
2. When the job completes or fails, a notification is sent to the registered email address.
3. The administrator checks the result via email and accesses the admin page if needed.

### Scenario 3: Status Inquiry via Chatbot (Phase 2)
1. Administrator asks the chatbot: "How many jobs are currently running?"
2. The chatbot queries the Job State Store and responds in natural language.

## 5. Functional Requirements

### Phase 1 (Small & Quick)

| ID | Requirement | Detail |
|----|-------------|--------|
| F1 | Job status dashboard | Display a list of all jobs with their current status (submitted/running/success/failed) |
| F2 | Job State Store | Build a new data store to persist job lifecycle events |
| F3 | Admin login | AWS Cognito-based authentication. Only authenticated admins can access the dashboard |
| F4 | Email notification | Send notifications to registered email addresses on job completion/failure |
| F5 | Notification recipient management | Register/edit/delete notification email addresses from the admin page |

### Phase 2+

| ID | Requirement | Detail |
|----|-------------|--------|
| F6 | Chatbot status inquiry | Query job status in natural language via a Strands Agent-based Ops chatbot |
| F7 | SMS notification | Add SMS as a notification channel in addition to email |
| F8 | Job cancellation | Allow administrators to cancel a running job |

## 6. Non-Functional Requirements

| Item | Requirement |
|------|-------------|
| Concurrent users | 1–3 administrators (small scale) |
| Data retention | 90-day job history retention (TBD) |
| Dashboard refresh | Polling-based, 30-second interval (Phase 1) |
| Availability | Same level as Deep Insight Web UI |

## 7. Admin Scope

### Allowed in Phase 1
- View job status (list and detail)
- Manage notification recipient emails

### Explicitly Excluded from Phase 1
- Job cancellation or retry
- Job result (report) download
- Admin account management
- System configuration changes

## 8. Relationship to Existing System

- Deep Insight Ops is a **separate admin-only application** from `deep-insight-web` (TBD: or an admin section within deep-insight-web)
- Shares the same ECS cluster and ALB infrastructure (TBD)
- Job State Store requires write integration with the deep-insight-web analysis request flow
- Authentication (Cognito) applies only to the admin page; the existing Web UI remains unchanged

## 9. Tech Stack & Constraints

- **Agent Framework**: Strands Agent, AgentCore
- **LLM**: AWS Bedrock (Phase 2 chatbot)
- **Authentication**: AWS Cognito
- **Notifications**: AWS SNS (email), AWS SES (alternative)
- **Job State Store**: AWS DynamoDB (candidate)
- **Constraint**: Maintain consistency with the existing Deep Insight architecture and deployment model

## 10. Research Requirements

- Reference latest research (papers, blogs, articles) on architecture and technical approaches (e.g., A2A protocol)
  - Request research from the AI Team if needed
- Reference latest features and APIs of Strands Agent and AgentCore
- Evaluate applicability of the A2A protocol

## 11. Implementation Approach

- Write a logical architecture and implementation plan before any code
- Begin implementation only after user approval of the architecture and plan
- Write the implementation plan in phases. Phase 1 pursues a small, quick implementation
- Execute implementation step by step, with user approval required before proceeding to the next step
- Write all code docstrings and comments in English with sufficient detail
