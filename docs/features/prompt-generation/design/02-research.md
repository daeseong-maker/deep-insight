---
chapter: research
status: draft
---

# Research

This chapter captures the reuse analysis against the existing `json-generation`
feature and records the four design decisions made during planning review.
It feeds `03-design.md`, where concrete file-level changes are specified.

## Reuse analysis: json-generation → prompt-generation

The plan constrains implementation to reuse `json-generation`'s patterns where
possible. The table below maps each json-generation surface to its
prompt-generation analog.

### Backend (`deep-insight-web/app.py`)

| json-generation | Reuse strategy for prompt-generation |
|---|---|
| `POST /generate-column-definitions` (lines 157–236) | Clone endpoint shape as `POST /generate-prompts`. Same error handling, same Bedrock `invoke_model` pattern, same markdown-fence stripping (lines 215–219). Input is the column-definitions JSON file, not a CSV. |
| `WEB_UTILITY_MODEL_ID` (Haiku 4.5, line 45) | Reuse as-is — same utility model, no new env var. |
| `_parse_csv_preview()` (line 141) | Not used. Input is already structured JSON. |
| Bedrock request body with `max_tokens: 2048` | Reuse shape with a smaller limit (prompts are short — 512 is sufficient). |
| `lang` form field (`ko` / `en`) | Reuse — same language switch selects the language of the tag labels (간단/중간/복잡 vs. Simple/Medium/Complex) and prompt text. |

### Frontend — `deep-insight-web/static/index.html`

| json-generation structure | prompt-generation analog |
|---|---|
| `#coldef-autogen-area` with `#coldef-autogen-btn` (lines 134–139) | New `#prompt-autogen-area` with `#prompt-autogen-btn`, placed inside `.prompt-examples-area` around line 183 (analyze card). |
| `#coldef-autogen-status` loading text | New `#prompt-autogen-status` — reuses the same visual pattern. |
| `#coldef-review-panel` with Table/JSON toggle, edit, confirm (lines 152–168) | **Not needed.** Prompts are short text; the "review" is clicking a chip into `<textarea id="query">` where editing is already possible. |
| `#prompt-examples` container (line 185) | Repurposed: the same container now receives generated chips. Before generation, renders the existing 3 hard-coded fallback chips. |

### Frontend — `deep-insight-web/static/js/upload.js`

| json-generation function | prompt-generation analog |
|---|---|
| `generateColdef()` (line 203) | `generatePrompts()` — `fetch("/generate-prompts")` with `column_definitions: Blob\|File` and `lang`. |
| `_generatedColdefJson` module variable (line 156) | `_generatedPrompts` — holds `[{level, tag, text}, ...]` (3 entries). |
| `updateAutogenVisibility()` (line 160) | `updatePromptAutogenVisibility()` — shown when the analyze card is visible. |
| Status/error-handling pattern (lines 213–240) | Copied verbatim for the new button. |
| `confirmColdef()` Blob-wrapping (lines 57–59) | Reused at call-time: if `_generatedColdefJson` is present, wrap as `Blob` + send as `column_definitions` field; otherwise send the `<input id="col-def">` File directly. |

### Frontend — `deep-insight-web/static/js/i18n.js`

| Existing keys (lines 20–24 KR, 113–117 EN) | New keys to add |
|---|---|
| `prompt_tag_simple`, `prompt_tag_detailed` | Add `prompt_tag_medium` (중간 / Medium). Existing `prompt_tag_detailed` is repurposed as the "복잡 / Complex" tag. |
| `prompt_simple_1`, `prompt_simple_2`, `prompt_detailed_1` | Kept as **pre-generation fallback** so the UI is never empty. |
| `coldef_autogen_btn`, `coldef_generating`, `coldef_gen_failed`, `coldef_regen_btn` | Add `prompt_autogen_btn`, `prompt_generating`, `prompt_gen_failed`, `prompt_regen_btn`. |

The existing `renderPromptExamples()` at `i18n.js:237–256` is already a
data-driven loop. It will be extended to read from `_generatedPrompts` when
populated and fall back to the hard-coded 3 chips otherwise.

### CSS — `deep-insight-web/static/css/styles.css`

| Class | Reuse |
|---|---|
| `.btn-autogen-primary` | Reuse as-is on `#prompt-autogen-btn`. |
| `.coldef-autogen-desc` | Reuse as-is for the description under the new button. |
| `.prompt-chip`, `.prompt-tag`, `.tag-simple`, `.tag-detailed` | Reuse as-is. |
| — | Add one new `.tag-medium` variant for the 중간 / Medium level. |

### Reuse summary

Approximately 70% of the implementation is structural copy: the endpoint
shape, the loading UX, the button CSS, the i18n key pattern, and the
client-side state variable pattern all transfer directly. The genuinely
new work is a new endpoint, a new CSS tag variant, a new i18n key group,
and extending `renderPromptExamples()` to read from a dynamic source.

## Design decisions

Four decisions were resolved during planning review.

### Decision 1: Source of column-definitions JSON at generation time

**Resolved:** multipart form submission with the JSON as a file field.

- `POST /generate-prompts` accepts `column_definitions: UploadFile` + `lang: Form`.
- This mirrors `/generate-column-definitions` exactly in endpoint signature,
  keeping server-side ergonomics identical.
- **Manual-upload path:** the client forwards the `<input id="col-def">` File
  object directly as the form field.
- **Auto-generated path:** the client wraps `_generatedColdefJson` as a Blob
  using the same pattern already present at `upload.js:57–59`:

  ```js
  const blob = new Blob(
    [JSON.stringify(_generatedColdefJson, null, 2)],
    { type: "application/json" }
  );
  formData.append("column_definitions", blob, "column_definitions.json");
  ```

- **No S3 dependency.** The button can fire regardless of whether `/upload`
  has completed, since the JSON never leaves the browser until generation.

Alternatives considered and rejected: S3-via-`upload_id` (added a missing-object
failure mode and tied the button to post-upload state) and JSON-in-request-body
(required a different request shape from `/generate-column-definitions`).

### Decision 2: Button location

**Resolved:** inside the analyze card, above `#prompt-examples` in
`.prompt-examples-area` (around `index.html:183`).

- The button's effect (populating `<textarea id="query">` via chip clicks)
  is adjacent to its location — cause and effect are visually linked.
- Only one chip render surface is needed: `#prompt-examples`. Before
  generation, the existing 3 hard-coded chips serve as fallback content.
- Analyze card visibility (revealed after `/upload` success) naturally
  gates the button — no extra visibility state is required beyond what
  the analyze card already has.

Alternatives considered and rejected: upload-card placement (chips would
render in the upload card for preview but be non-functional there, since
the query textarea lives in the analyze card — forcing either dual render
surfaces or preview-only chips).

### Decision 3: LLM input

**Resolved:** column-definitions JSON only. No CSV sample preview, no
dataset metadata.

- Matches the plan's explicit wording ("JSON 파일을 기반으로").
- The JSON produced by json-generation already contains rich, value-aware
  `column_desc` strings (e.g., type, unit, format hints) — so most of
  the signal a CSV preview would carry is already present.
- Keeps the endpoint mirrored in shape to `/generate-column-definitions`
  (one input file + `lang`).
- If generated prompts prove too generic in practice, CSV preview can be
  added later without breaking the API shape.

Alternatives considered and rejected: column JSON + CSV preview
(reintroduces an `upload_id`/S3 dependency and doubles request size) and
column JSON + dataset metadata (marginal quality gain for the complexity).

### Decision 4: Trigger and regeneration

**Resolved:** two-state button, mirroring `coldef-autogen-btn` →
`coldef-regen-btn` (`index.html:136`, `index.html:157`).

- Before first click:
  - Primary button: `[✨ 프롬프트 샘플 생성하기]` with class
    `btn-autogen-primary`.
  - `#prompt-examples` shows the 3 hard-coded fallback chips.
- After successful generation:
  - Primary button becomes hidden.
  - A small `[🔄 재생성]` button (`btn-sm btn-outline`) appears near the
    chips.
  - `#prompt-examples` shows the 3 generated chips at 간단 / 중간 / 복잡.

**Paired defaults:**

| Concern | Behavior |
|---|---|
| Language toggle | Keep generated prompts; user clicks 재생성 to refresh in new language. Matches json-generation's existing language-behavior convention. |
| Column definitions change after prompts generated | Silent — generated prompts remain until the user clicks 재생성 explicitly. User drives regeneration. |
| Loading state | Disable button + show `#prompt-autogen-status` with "AI 가 프롬프트를 생성하고 있습니다..." — visual pattern copied from `upload.js:213–217`. |

Alternatives considered and rejected: one-shot with no regeneration
(no recovery path if the first output is poor) and single re-clickable
button (violates the "Json-generation 의 UI 처럼" instruction from the plan).

## Open questions for `03-design.md`

The decisions above specify *what* will be built. `03-design.md` resolves
the remaining *how* questions:

1. **Exact shape of the LLM response.** Proposed:
   ```json
   [
     {"level": "simple",  "tag": "간단", "text": "..."},
     {"level": "medium",  "tag": "중간", "text": "..."},
     {"level": "complex", "tag": "복잡", "text": "..."}
   ]
   ```
   The `tag` field matches `translations[lang].prompt_tag_*` so the
   client can render without an extra mapping step.

2. **Prompt template for Claude Haiku.** A single Korean/English-switched
   prompt that:
   - States the role ("You generate sample business-analysis prompts from
     a column-definitions JSON").
   - Provides the JSON.
   - Specifies 3 complexity tiers (simple: 1 metric / 1 operation; medium:
     a focused trend or comparison across 2–3 columns; complex: a strategic
     question requiring multi-dimensional synthesis).
   - Constrains output format (JSON array, no fences, no commentary).

3. **CSS for `.tag-medium`.** Needs a color that distinguishes it from
   `.tag-simple` and `.tag-detailed` in the current palette.

4. **Where the new JS lives.** Two options:
   - Extend `upload.js` (where the autogen pattern already lives).
   - New file `js/prompts.js` for clean separation.

   Decision deferred to `03-design.md` with current leaning toward
   extending `upload.js` to match json-generation's single-file pattern.

5. **Should the regenerate button reuse `#prompt-autogen-btn` with
   a class swap, or be a distinct button element?** Json-generation
   uses two separate elements (`coldef-autogen-btn` and `coldef-regen-btn`
   at lines 136 and 157). Mirror that.
