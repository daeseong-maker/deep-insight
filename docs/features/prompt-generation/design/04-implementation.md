---
chapter: implementation
status: draft
---

# Implementation

Build sequence, acceptance criteria, and rollout notes for the
prompt-generation feature. Specs are in `03-design.md`; this chapter
captures *how* and *in what order* the work is done.

## Where the code lives

- `deep-insight-web/app.py` — new `/generate-prompts` endpoint
- `deep-insight-web/static/index.html` — new button + regenerate UI in
  `.prompt-examples-area`
- `deep-insight-web/static/js/upload.js` — new `_generatedPrompts`
  state, `generatePrompts()`, `initPromptAutogen()`
- `deep-insight-web/static/js/i18n.js` — extended
  `renderPromptExamples()`, new translation keys
- `deep-insight-web/static/css/styles.css` — new `.tag-medium`

No new files. No new dependencies. No new env vars
(reuses `WEB_UTILITY_MODEL_ID`).

## Build sequence

The order below is chosen to keep the app runnable at each step and to
allow incremental manual verification — never break a working state.

### Step 1 — Backend endpoint (server-only, no UI)

Add `POST /generate-prompts` to `deep-insight-web/app.py` per the
endpoint spec in `03-design.md`. No UI changes yet.

**Verification:**

```bash
# In one terminal
cd managed-agentcore
uv run python ../deep-insight-web/app.py

# In another terminal — manual upload coldef path
curl -X POST http://localhost:8080/generate-prompts \
  -F "column_definitions=@./sample_data/some_dataset/column_definitions.json" \
  -F "lang=ko"
```

Expected: HTTP 200, JSON body with `success: true` and 3 prompts at
`level: simple|medium|complex`. Validate visually that prompts reference
columns from the JSON.

Repeat with `lang=en` → English prompts and English tags.
Repeat with a malformed JSON → HTTP 400 with `success: false`.

### Step 2 — i18n keys + safe `renderPromptExamples()` rewrite

Edit `deep-insight-web/static/js/i18n.js`:
1. Add the new `prompt_*` keys to both `ko` and `en` blocks.
2. Rewrite `renderPromptExamples()` per `03-design.md` (safe DOM
   construction, fallback branch). Add the `levelToTagClass()` helper.

`_generatedPrompts` is referenced via `typeof ... !== "undefined"` —
safe even if `upload.js` hasn't been edited yet, so this step doesn't
require Step 3 first.

**Verification:**
- Reload UI. Existing 3 hard-coded chips render unchanged (fallback
  branch is exercised since `_generatedPrompts` is undefined).
- Click each chip → fills `<textarea id="query">` exactly as before.
- Toggle language → chips update label text (existing behavior).
- DevTools console: `document.querySelector("#prompt-examples").innerHTML`
  shows the chips were built from text nodes (no markup other than the
  expected `<span class="prompt-tag …">…</span>` wrapper).

### Step 3 — `.tag-medium` CSS

Add the `.tag-medium` rule to `deep-insight-web/static/css/styles.css`
after `.tag-detailed`.

**Verification:**
- In DevTools, manually add `class="prompt-tag tag-medium"` to a span;
  visual color is amber and visually distinct from `tag-simple` (green)
  and `tag-detailed` (blue). Adjust the rule if it clashes.

### Step 4 — HTML markup for the button + regenerate UI

Edit `deep-insight-web/static/index.html` per `03-design.md`. Adds:
- `#prompt-autogen-area` (wraps `#prompt-autogen-btn`, description,
  `#prompt-autogen-status`)
- `.prompt-examples-header` wrapping the existing label and the new
  `#prompt-regen-btn`

**Verification:**
- Reload UI. Upload a data file + coldef → click upload.
- Analyze card now shows: primary "프롬프트 샘플 생성하기" button +
  description + 3 hard-coded fallback chips below.
- Button is non-functional (no JS yet) — that's expected.

### Step 5 — `generatePrompts()` + wiring

Edit `deep-insight-web/static/js/upload.js`:
1. Add `let _generatedPrompts = null;` near `_generatedColdefJson`
   (around line 156).
2. Add `generatePrompts()` and `initPromptAutogen()` per `03-design.md`.
3. Add `initPromptAutogen();` to `initUpload()` after
   `initColdefAutogen();` (line 43).

**Verification (full feature):** see "Acceptance criteria" below.

### Step 6 — End-to-end verification

Run the full manual test plan from `03-design.md` § Behavior verification.

## Acceptance criteria

The feature is complete when **all** of the following are true:

| # | Behavior | Status check |
|---|---|---|
| 1 | Pre-generation, the analyze card shows the primary button + the 3 hard-coded fallback chips. | Visual |
| 2 | After clicking the button via the **manual coldef path** (user dropped a JSON file), 3 generated chips replace the fallback, the primary button is hidden, and the small 재생성 button appears. | Visual |
| 3 | After clicking the button via the **auto-generated coldef path** (user used `coldef-autogen-btn` and confirmed), the same outcome as #2 is reached. | Visual |
| 4 | Each generated chip, when clicked, fills `<textarea id="query">` with its `text` value verbatim. | Click each chip, inspect textarea |
| 5 | Clicking 재생성 disables both buttons, shows a loading status, and replaces chips on success. | Visual + DevTools network tab |
| 6 | Switching language (KR ↔ EN) does **not** clear `_generatedPrompts` and does **not** refetch. Existing chips remain in their original language. | Toggle language after generation |
| 7 | If the LLM call fails (e.g., revoke Bedrock access in test), the red error appears in `#prompt-autogen-status`, and the button is re-enabled. State is unchanged. | Force a failure |
| 8 | If the user has neither a manual coldef file nor an auto-generated one, clicking the button shows the `prompt_no_coldef` red message and does not POST. | Clear both, click button |
| 9 | XSS safety: a returned `text` containing `<script>alert(1)</script>` renders as literal text and does not execute. | Stub the endpoint or use DevTools to mutate `_generatedPrompts` |
| 10 | The endpoint returns HTTP 400 for malformed JSON input and HTTP 500 for malformed LLM output. | curl tests in Step 1 |

## Rollout notes

### Local development

```bash
cd managed-agentcore
uv run python ../deep-insight-web/app.py
# UI at http://localhost:8080
```

The endpoint and UI run in the same FastAPI process — no separate
service to start. `WEB_UTILITY_MODEL_ID` is loaded from the
`managed-agentcore/.env` file, same as `/generate-column-definitions`.

### Deployment

This feature ships as part of the existing `deep-insight-web` ECS
service. No infrastructure changes:
- No new IAM permissions needed (already has `bedrock:InvokeModel` for
  the same `WEB_UTILITY_MODEL_ID`).
- No new env vars.
- No CloudFront/ALB rule changes (single new path, same domain).

```bash
cd deep-insight-web
bash deploy.sh
aws ecs wait services-stable \
  --cluster deep-insight-cluster-prod \
  --services deep-insight-web-service \
  --region us-west-2
```

Per project convention: do not test during the rolling deployment — the
old task gets killed mid-stream and may produce confusing UI behavior
(stale chips that disappear on next reload).

### Backward compatibility

- The hard-coded `prompt_simple_1`, `prompt_simple_2`, `prompt_detailed_1`
  translation keys remain — they're the pre-generation fallback. No
  breaking change for users who never click the new button.
- `/upload` and `/analyze` endpoints are unchanged.
- The chip-click → textarea behavior is unchanged in shape; only the
  source of `examples` has been extended.

### Observability

No new metrics or logs beyond the existing `logger.info` /
`logger.error` calls inside the endpoint (mirroring
`/generate-column-definitions`). Job tracking via
`ops/job_tracker.py` is **not** invoked here — this endpoint is a
synchronous pre-analysis utility, not an analysis job, just like
`/generate-column-definitions`.

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| LLM emits malformed JSON | Medium | Markdown-fence stripping (copied from `/generate-column-definitions`) handles the common case. On `JSONDecodeError`, the endpoint returns HTTP 500; the user sees a red error and can click 재생성. |
| LLM emits structurally wrong array (wrong number of items, missing keys) | Low | Server-side validates count == 3 and keys `level`, `tag`, `text`. On mismatch → HTTP 500 with descriptive error. |
| LLM emits malicious markup in `text` | Low | Safe DOM construction in `renderPromptExamples()` (`textContent` + `createTextNode`) renders any markup as literal text. |
| User clicks button before coldef exists | High | `prompt_no_coldef` red message; no network call. |
| User toggles language during generation | Low | `currentLang` is read at button-click time, not at fetch-completion time. Chips arrive in the originally requested language; the language toggle does not race. |
| User uploads a 1MB+ coldef JSON | Very low | Bedrock max input is well above realistic coldef size; if it ever became a concern, add server-side size cap. Out of scope for v1. |

## Out of scope (recap from `03-design.md`)

- Cross-session caching of generated prompts.
- Streaming the generation response (one-shot is fine for ~3 short outputs).
- A/B testing prompt-complexity definitions.
- More than 3 chips, or user-configurable counts.
