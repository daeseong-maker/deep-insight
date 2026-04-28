---
chapter: design
status: draft
---

# Design

Concrete file-by-file changes needed to implement the prompt-generation
feature. Decisions resolved in `02-research.md` are referenced rather
than re-justified here.

## Files changed

| File | Change type | Summary |
|---|---|---|
| `deep-insight-web/app.py` | Add | New `POST /generate-prompts` endpoint. |
| `deep-insight-web/static/index.html` | Modify | Add `#prompt-autogen-area`, `#prompt-autogen-status`, `#prompt-regen-btn` inside `.prompt-examples-area`. |
| `deep-insight-web/static/js/upload.js` | Modify | Add `_generatedPrompts` state, `generatePrompts()`, `initPromptAutogen()`, visibility helpers. Wire into `initUpload()`. |
| `deep-insight-web/static/js/i18n.js` | Modify | Extend `renderPromptExamples()` to read from `_generatedPrompts` when set, using safe DOM construction. Add `prompt_tag_medium` and `prompt_autogen_*` translation keys (KR + EN). |
| `deep-insight-web/static/css/styles.css` | Modify | Add `.tag-medium`. |

No new files. Reuse keeps the implementation as a delta on `upload.js` +
`i18n.js`, matching json-generation's single-file convention.

## Backend: `POST /generate-prompts`

Inserted in `deep-insight-web/app.py` directly after the existing
`/generate-column-definitions` endpoint (around line 237).

### Endpoint signature

```python
@app.post("/generate-prompts")
async def generate_prompts(
    column_definitions: UploadFile = File(...),
    lang: str = Form("ko"),
):
    """Generate 3 sample analysis prompts (simple/medium/complex) from a
    column-definitions JSON, using Bedrock Claude."""
```

### Implementation outline

1. Read and parse the uploaded `column_definitions` file as JSON.
   Validation: must be a list of `{column_name, column_desc}` objects.
   On parse failure → return `{success: False, error: ...}` with HTTP 400.
2. Build the LLM prompt (template below) substituting the JSON and
   language instruction.
3. Call `bedrock-runtime invoke_model` with `WEB_UTILITY_MODEL_ID`,
   `max_tokens: 512`. Reuse the same boto3 client construction as
   `/generate-column-definitions`.
4. Strip markdown code fences from the response (verbatim copy of
   `app.py:215–219`).
5. Parse the JSON array. Validate it has exactly 3 entries with
   `level`, `tag`, `text` keys. On structural mismatch → HTTP 500.
6. Return `{success: True, prompts: [...]}`.

### LLM prompt template

```python
lang_instruction = (
    "Write all prompt text in Korean."
    if lang == "ko"
    else "Write all prompt text in English."
)

tag_simple   = "간단" if lang == "ko" else "Simple"
tag_medium   = "중간" if lang == "ko" else "Medium"
tag_complex  = "복잡" if lang == "ko" else "Complex"

prompt = f"""You generate sample business-analysis prompts for a data
analysis tool, given a column-definitions JSON describing the dataset.

Generate exactly 3 sample prompts at distinct complexity levels:

- "simple":  one metric or one operation (e.g., summarize key metrics,
             calculate a total). 1 sentence, under 40 characters.
- "medium":  a focused trend, segmentation, or comparison spanning 2–3
             columns. 1–2 sentences.
- "complex": a strategic, multi-dimensional question requiring synthesis
             across many columns — e.g., growth-opportunity discovery,
             multi-factor optimization. 2–4 sentences. Should ask for
             prioritized actionable strategies with expected impact.

Use a business perspective, not a technical one. Reference actual column
names from the JSON where natural.

{lang_instruction}

Return ONLY a valid JSON array with this exact shape, no markdown fences,
no explanation:

[
  {{"level": "simple",  "tag": "{tag_simple}",  "text": "..."}},
  {{"level": "medium",  "tag": "{tag_medium}",  "text": "..."}},
  {{"level": "complex", "tag": "{tag_complex}", "text": "..."}}
]

Column definitions:
{json.dumps(column_definitions_data, ensure_ascii=False)}
"""
```

### Response shape

```json
{
  "success": true,
  "prompts": [
    {"level": "simple",  "tag": "간단", "text": "총 매출액을 계산해줘"},
    {"level": "medium",  "tag": "중간", "text": "지역별·월별 매출 추이를 비교해줘"},
    {"level": "complex", "tag": "복잡", "text": "고객 세그먼트별 수익 기여도를 분석하고, ..."}
  ]
}
```

Error response: `{success: false, error: "<message>"}` with HTTP 400/500.

## Security: rendering LLM-generated text safely

The chips that render generated prompts must NOT use string-based
HTML interpolation, because `prompts[].text` originates from an LLM and
could contain markup. Use safe DOM construction (`textContent` +
`createElement`) so that any markup the LLM emits becomes literal text
rather than executable HTML. This pattern is already used in
`renderColdefTable()` at `upload.js:268-282` for the same reason.

The existing `renderPromptExamples()` at `i18n.js:237-256` currently
interpolates trusted (hard-coded) translation strings via `innerHTML`.
Since we're extending it to also handle untrusted LLM strings, the
function is rewritten in this design to use safe construction for
all cases — eliminating both the new and latent risks at once.

## Frontend: `index.html`

Modification within `.prompt-examples-area` (currently at line 183–186).

### Before

```html
<div class="prompt-examples-area">
    <div class="prompt-examples-label" data-i18n="prompt_examples_label">예시를 클릭하면 자동 입력됩니다</div>
    <div id="prompt-examples"></div>
</div>
```

### After

```html
<div class="prompt-examples-area">
    <!-- Auto-generate (Primary) — shown before first generation -->
    <div id="prompt-autogen-area">
        <button type="button" id="prompt-autogen-btn" class="btn btn-autogen-primary" data-i18n="prompt_autogen_btn">✨ 프롬프트 샘플 생성하기</button>
        <div class="coldef-autogen-desc" data-i18n="prompt_autogen_desc">컬럼 정의를 기반으로 AI가 3가지(간단/중간/복잡) 프롬프트를 생성합니다</div>
        <div id="prompt-autogen-status" class="hidden"></div>
    </div>
    <div class="prompt-examples-header">
        <span class="prompt-examples-label" data-i18n="prompt_examples_label">예시를 클릭하면 자동 입력됩니다</span>
        <button type="button" id="prompt-regen-btn" class="btn btn-sm btn-outline hidden" data-i18n="prompt_regen_btn">🔄 재생성</button>
    </div>
    <div id="prompt-examples"></div>
</div>
```

Notes:
- `#prompt-autogen-area` is shown by default (visible whenever the
  analyze card is visible).
- `#prompt-regen-btn` carries `hidden` by default; revealed after the
  first successful generation.
- `.coldef-autogen-desc` is reused as-is for the description below the
  primary button (renaming to a more general `.autogen-desc` class is
  out of scope for this feature — keep the existing class to avoid
  cross-feature CSS churn).

## Frontend: `js/upload.js`

### New module-level state

Inserted near `_generatedColdefJson` (around line 156):

```js
let _generatedPrompts = null;  // [{level, tag, text}, ...] or null
```

### New functions

```js
function initPromptAutogen() {
    document.getElementById("prompt-autogen-btn")
        .addEventListener("click", () => generatePrompts());
    document.getElementById("prompt-regen-btn")
        .addEventListener("click", () => generatePrompts());
}

async function generatePrompts() {
    const t = translations[currentLang];
    const autogenBtn = document.getElementById("prompt-autogen-btn");
    const regenBtn = document.getElementById("prompt-regen-btn");
    const statusDiv = document.getElementById("prompt-autogen-status");

    // Resolve column-definitions source (manual upload OR auto-generated)
    const colDef = document.getElementById("col-def").files[0];
    let coldefBlob;
    let coldefName = "column_definitions.json";
    if (colDef) {
        coldefBlob = colDef;
        coldefName = colDef.name;
    } else if (_generatedColdefJson) {
        coldefBlob = new Blob(
            [JSON.stringify(_generatedColdefJson, null, 2)],
            { type: "application/json" }
        );
    } else {
        statusDiv.textContent = t.prompt_no_coldef ||
            "Please provide column definitions first (upload a JSON file or auto-generate).";
        statusDiv.style.color = "var(--red)";
        statusDiv.classList.remove("hidden");
        return;
    }

    // Loading state — pattern copied from generateColdef()
    autogenBtn.disabled = true;
    regenBtn.disabled = true;
    autogenBtn.textContent = t.prompt_generating || "Generating...";
    statusDiv.textContent = t.prompt_generating_hint ||
        "AI is generating sample prompts...";
    statusDiv.style.color = "var(--text-muted)";
    statusDiv.classList.remove("hidden");

    try {
        const formData = new FormData();
        formData.append("column_definitions", coldefBlob, coldefName);
        formData.append("lang", currentLang);

        const res = await fetch("/generate-prompts", {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        if (data.success) {
            _generatedPrompts = data.prompts;
            statusDiv.classList.add("hidden");
            // Switch from primary to regenerate button
            document.getElementById("prompt-autogen-area")
                .classList.add("hidden");
            regenBtn.classList.remove("hidden");
            renderPromptExamples();  // re-render chips from new state
        } else {
            statusDiv.textContent = (t.prompt_gen_failed ||
                "Generation failed: ") + (data.error || "Unknown error");
            statusDiv.style.color = "var(--red)";
        }
    } catch (err) {
        statusDiv.textContent = (t.prompt_gen_failed ||
            "Generation failed: ") + err.message;
        statusDiv.style.color = "var(--red)";
    } finally {
        autogenBtn.disabled = false;
        regenBtn.disabled = false;
        autogenBtn.textContent = t.prompt_autogen_btn ||
            "Generate Sample Prompts";
    }
}
```

### Wiring change

In `initUpload()` (line 2), add one line after `initColdefAutogen()`:

```js
initColdefAutogen();
initPromptAutogen();   // NEW
```

## Frontend: `js/i18n.js`

### `renderPromptExamples()` extension (line 237)

Rewritten to (a) read from `_generatedPrompts` when populated and (b)
build chip DOM with `textContent` + `createElement` so LLM-supplied
text cannot inject markup.

```js
function renderPromptExamples() {
    const container = document.getElementById("prompt-examples");
    const t = translations[currentLang];

    let examples;
    if (typeof _generatedPrompts !== "undefined" && _generatedPrompts) {
        examples = _generatedPrompts.map(p => ({
            tag: p.tag,
            tagClass: levelToTagClass(p.level),
            text: p.text,
        }));
    } else {
        examples = [
            { tag: t.prompt_tag_simple,   tagClass: "tag-simple",   text: t.prompt_simple_1 },
            { tag: t.prompt_tag_simple,   tagClass: "tag-simple",   text: t.prompt_simple_2 },
            { tag: t.prompt_tag_detailed, tagClass: "tag-detailed", text: t.prompt_detailed_1 },
        ];
    }

    container.textContent = "";  // clear safely (no innerHTML)
    for (const ex of examples) {
        const chip = document.createElement("div");
        chip.className = "prompt-chip";

        const tagSpan = document.createElement("span");
        tagSpan.className = `prompt-tag ${ex.tagClass}`;
        tagSpan.textContent = ex.tag;
        chip.appendChild(tagSpan);

        // Append text as a text node so any markup in `ex.text`
        // (which may originate from an LLM) becomes literal text.
        chip.appendChild(document.createTextNode(ex.text));

        chip.addEventListener("click", () => {
            const q = document.getElementById("query");
            if (q) { q.value = ex.text; q.focus(); }
        });
        container.appendChild(chip);
    }
}

function levelToTagClass(level) {
    if (level === "simple")  return "tag-simple";
    if (level === "medium")  return "tag-medium";
    if (level === "complex") return "tag-detailed";  // reuse detailed styling
    return "tag-simple";
}
```

### Translation keys to add

In the `ko` block (around line 24, after `prompt_detailed_1`):

```js
prompt_tag_medium:        "중간",
prompt_autogen_btn:       "✨ 프롬프트 샘플 생성하기",
prompt_autogen_desc:      "컬럼 정의를 기반으로 AI가 3가지(간단/중간/복잡) 프롬프트를 생성합니다",
prompt_regen_btn:         "🔄 재생성",
prompt_generating:        "생성 중...",
prompt_generating_hint:   "AI가 샘플 프롬프트를 생성하고 있습니다...",
prompt_gen_failed:        "생성 실패: ",
prompt_no_coldef:         "컬럼 정의가 필요합니다. JSON 파일을 업로드하거나 자동 생성하세요.",
```

In the `en` block (mirror at the matching line):

```js
prompt_tag_medium:        "Medium",
prompt_autogen_btn:       "✨ Generate Sample Prompts",
prompt_autogen_desc:      "AI generates 3 prompts (Simple / Medium / Complex) from your column definitions",
prompt_regen_btn:         "🔄 Regenerate",
prompt_generating:        "Generating...",
prompt_generating_hint:   "AI is generating sample prompts...",
prompt_gen_failed:        "Generation failed: ",
prompt_no_coldef:         "Column definitions required. Upload a JSON file or auto-generate first.",
```

## Frontend: `css/styles.css`

Add directly after `.tag-detailed` (line 714):

```css
.tag-medium {
    background: rgba(251, 191, 36, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3);
}
```

Amber/yellow chosen to sit visually between green (simple) and blue
(complex/detailed). Verify against the dark-theme palette during
implementation; adjust if it clashes with existing accents.

## Behavior verification (manual)

Once implemented, verify in a browser:

1. **Pre-generation**: upload data + coldef → analyze card shows the
   primary "프롬프트 샘플 생성하기" button + 3 hard-coded fallback chips.
2. **Manual coldef path**: drop a JSON file → click button → 3 chips
   replace the fallback, primary button hides, "재생성" button appears.
3. **Auto-generated coldef path**: auto-generate coldef → confirm →
   click button → same outcome as #2 (verifies the Blob-wrapping branch).
4. **Click chip → fills `<textarea id="query">`**, including newly
   generated chips at all 3 levels.
5. **Regenerate**: click 재생성 → loading state → new chips replace old.
6. **Language toggle**: KR ↔ EN preserves generated prompts (does not
   refetch). Tag labels stay in the original generation language until
   user clicks 재생성.
7. **Error path**: simulate Bedrock failure → error message in red in
   `#prompt-autogen-status`; primary button re-enabled, no state change.
8. **No-coldef path**: clear both manual file and `_generatedColdefJson`,
   click button → red error message.
9. **XSS safety**: stub the endpoint to return a prompt text containing
   `<script>alert(1)</script>` → chip displays it as literal text and
   does not execute it.

## Out of scope

- Caching generated prompts across sessions (no persistence).
- A/B testing different prompt complexity definitions.
- Showing the LLM's reasoning or confidence per generated prompt.
- Adapting the number of prompts (always exactly 3 — simple/medium/complex).
- Streaming generation (one-shot is fine for ~3 short outputs).
