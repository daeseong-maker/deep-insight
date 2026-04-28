---
title: Auto-Generate Sample Prompts
status: active
last_updated: 2026-04-25
---

# Auto-Generate Sample Prompts (Prompt Generation)

Automatically generates 3 sample analysis prompts at distinct complexity tiers
(simple / medium / complex) from an uploaded `column_definitions.json`, using
Amazon Bedrock (Claude). Replaces the previous hard-coded fallback chips with
prompts grounded in the actual columns of the user's dataset.

## Overview

Before this feature, the analyze card showed three hard-coded sample prompts
("간단/간단/상세") regardless of the dataset. They were generic and rarely
runnable as-is — users had to rewrite them to reference real columns.

This feature reads the column-definitions JSON (whether the user uploaded it
manually or auto-generated it via [`json-generation`](../json-generation/))
and asks Claude to produce three business-perspective prompts at distinct
complexity tiers. Each generated prompt references the user's actual column
names and is immediately runnable.

## Workflow

```
User uploads CSV + column_definitions.json
       ↓
Analyze card appears (no chips by default)
       ↓
[💡 프롬프트 샘플 생성하기] button (primary CTA)
       ↓
Backend reads column_definitions JSON
       ↓
Bedrock Claude (WEB_UTILITY_MODEL_ID) generates 3 prompts
       ↓
Chips render in #prompt-examples:
  [간단]  Simple  — single metric / single operation
  [중간]  Medium  — focused trend or comparison (2-3 columns)
  [복잡]  Complex — strategic multi-dimensional analysis
       ↓
User clicks a chip → fills <textarea id="query"> → can edit before submitting
       ↓
[🔄 재생성] button replaces the primary button — regenerate at any time
```

## Changes

### Backend (`deep-insight-web/app.py`)

- **New endpoint**: `POST /generate-prompts`
  - Accepts: `column_definitions` (UploadFile, JSON), `lang` (form field: `ko` or `en`)
  - Validates input is a non-empty JSON array of `{column_name, column_desc}` objects
  - Calls Bedrock `invoke_model` with `WEB_UTILITY_MODEL_ID`, `max_tokens: 512`
  - Strips markdown code fences from LLM response (mirrors `/generate-column-definitions`)
  - Validates LLM output: must be exactly 3 entries with `level`, `tag`, `text` keys
  - Returns `{ success: true, prompts: [{level, tag, text}, ...] }`
  - Error contract: HTTP 400 for malformed input, HTTP 500 for LLM/parse failures

### Frontend (`deep-insight-web/static/`)

#### `index.html`
- New `#prompt-autogen-area` inside `.prompt-examples-area` — primary CTA button + description
- New `.prompt-examples-header` (initially hidden) — wraps the "예시를 클릭하면..." label and the small `🔄 재생성` button
- `#prompt-autogen-status` lives as a sibling to `#prompt-autogen-area` so it stays visible during regeneration (a `display:none` parent would hide it otherwise)
- Existing `#prompt-examples` container reused — chips render here

#### `js/upload.js`
- `_generatedPrompts` — module-level state holding `[{level, tag, text}, ...]`
- `generatePrompts()` — handles both initial generation and regeneration. Resolves the column-definitions source from either the manual `<input id="col-def">` File or `_generatedColdefJson` (Blob-wrapped, mirroring `confirmColdef()`)
- `initPromptAutogen()` — wires both `#prompt-autogen-btn` and `#prompt-regen-btn` to the same handler
- Both buttons (primary and regen) show loading text and re-enable themselves on completion

#### `js/i18n.js`
- New translation keys (KR + EN): `prompt_tag_medium`, `prompt_autogen_btn`, `prompt_autogen_desc`, `prompt_regen_btn`, `prompt_generating`, `prompt_generating_hint`, `prompt_gen_failed`, `prompt_no_coldef`, `guide_ai_helpers_title`, `guide_ai_helpers_desc`, `analyze_intro`
- `renderPromptExamples()` rewritten to (a) read from `_generatedPrompts` when set, otherwise render an empty container and (b) build chip DOM with `textContent` + `createTextNode` so any markup in LLM-supplied prompts becomes literal text rather than executable HTML
- `levelToTagClass()` helper maps `"simple" | "medium" | "complex"` → `tag-simple` / `tag-medium` / `tag-detailed`

#### `css/styles.css`
- New `.tag-medium` rule — amber color (`#fbbf24`) sitting visually between `tag-simple` (green) and `tag-detailed` (blue)
- `.btn-autogen-primary` base gradient opacity raised so the button reads visibly as a CTA on the dark theme

#### Guide updates
- Step 1 and Step 2 in the guide mention both AI helpers
- New `💡 AI 도우미` callout in the guide groups column-definition autogen and prompt autogen as a family of features
- New `💡` intro callout at the top of the analyze card orients first-time users

## User Experience

The primary action is presented as a prominent gradient button. Before the
user clicks, the analyze card's `#prompt-examples` container is empty —
no fallback chips, only the AI primary button. After the first successful
generation, the primary button hides and is replaced by a small `🔄 재생성`
button next to the "예시를 클릭하면 자동 입력됩니다" label.

```
Analyze card (BEFORE generation)
┌─────────────────────────────────────────────┐
│ 💡 분석 프롬프트를 직접 입력하거나, 아래     │
│    AI 추천 샘플을 사용하세요.                │
│ ┌──────────────────────────────────────────┐│
│ │ <textarea id="query">                    ││
│ │ 예: 매출 트렌드를 분석하고 보고서를...   ││
│ └──────────────────────────────────────────┘│
│ ┌──────────────────────────────────────────┐│
│ │ 💡 프롬프트 샘플 생성하기              💡│
│ └──────────────────────────────────────────┘│
│   컬럼 정의를 기반으로 AI가 3가지            │
│   (간단/중간/복잡) 프롬프트를 생성합니다     │
└─────────────────────────────────────────────┘

Analyze card (AFTER generation)
┌─────────────────────────────────────────────┐
│ 💡 분석 프롬프트를 직접 입력하거나, 아래     │
│    AI 추천 샘플을 사용하세요.                │
│ ┌──────────────────────────────────────────┐│
│ │ <textarea id="query">                    ││
│ └──────────────────────────────────────────┘│
│ 💡 예시를 클릭하면 자동 입력됩니다 [🔄 재생성]│
│ ┌──────────────────────────────────────────┐│
│ │ [간단]  Category별 총 Amount를 요약해...  ││
│ │ [중간]  Gender와 Age Group별로 주문 ...   ││
│ │ [복잡]  Category, ship-state, Age Group..││
│ └──────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

| User Type | Flow |
|-----------|------|
| First-time user | Upload data + coldef → click 💡 button → 3 chips appear → click one → edit textarea → 분석 시작 |
| Wants different prompts | Click 🔄 재생성 → 3 new chips replace the previous ones |
| Wants to write their own | Skip the AI button → type into textarea directly → 분석 시작 |

### Language Behavior

- Generated prompts are produced in the **language active at generation time** (Korean or English)
- Tag labels (간단/중간/복잡 vs. Simple/Medium/Complex) are baked into the LLM response, not re-translated client-side
- Switching language after generation does **not** auto-translate the prompts — user clicks 재생성 to refresh in the new language (consistent with [`json-generation`](../json-generation/)'s convention)

### Security

LLM-supplied prompt text is rendered using `textContent` and `createTextNode`
rather than `innerHTML`, so any markup the LLM returns (intentional or via
prompt injection) renders as literal text rather than executing. The same
safe-DOM pattern is used by `renderColdefTable()` for `json-generation`.

## Model Configuration

- **Model**: `WEB_UTILITY_MODEL_ID` from `managed-agentcore/.env` (currently `global.anthropic.claude-sonnet-4-6`)
- **Max tokens**: 512
- **Language**: Determined by the UI language toggle at generation time
- Sonnet 4.6 was chosen over Haiku 4.5 after a side-by-side quality comparison; Haiku produced overly generic prompts at the simple tier (e.g., "전체 주문 총액은 얼마인가?" with no column reference) while Sonnet referenced actual columns verbatim ("Category별 총 Amount를 요약해 주세요"). See `design/02-research.md` and `design/04-implementation.md` for the comparison data.

## Design history

For the planning, research, design, and implementation chapters, see:

- [`design/01-plan.md`](design/01-plan.md) — original requirement
- [`design/02-research.md`](design/02-research.md) — reuse analysis vs. `json-generation`, four locked design decisions
- [`design/03-design.md`](design/03-design.md) — file-by-file change spec, including safe-DOM rewrite of `renderPromptExamples()`
- [`design/04-implementation.md`](design/04-implementation.md) — build sequence, acceptance criteria, rollout notes
