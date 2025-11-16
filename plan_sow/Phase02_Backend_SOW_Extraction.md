# Phase 02 – Backend SOW Extraction API & Data Model

## 1. Objective

Add a new LLM‑backed backend pipeline that reads a parsed Scope of Work document and produces an ordered list of industrial process steps. Persist these runs and steps in the database and expose them over a dedicated `/api/sow` surface.

The SOW pipeline should reuse the existing document + header infrastructure but must be **independent** of the removed specs agents.

## 2. High‑level behaviour

Given a `document_id` that has already been parsed (and ideally has headers aligned):

1. The client calls `POST /api/sow/{document_id}`.
2. The backend:
   - loads the document’s full text and, when available, the text of any sections whose headers look like Scope‑of‑Work content (e.g. “Scope of Work”, “System Description”, “Sequence of Operations”, “Functional Description”)
   - builds a SOW‑specific prompt
   - calls the configured OpenRouter model
   - parses the response into structured `SOWStep` records
   - stores a `SOWRun` row plus its associated `SOWStep` rows.
3. The client can then call `GET /api/sow/{document_id}` to retrieve the latest run and steps.

For the first implementation it’s acceptable to feed the **full document text** when in doubt; later refinements can narrow to SOW‑like sections.

## 3. Data model

Add two new SQLModel (or SQLAlchemy) models in the backend DB layer.

### 3.1. `SOWRun`

Fields (suggested):

- `id: int` primary key
- `document_id: int` (FK to documents table)
- `model: str` (LLM model used)
- `source_hash: str` (hash of the document text used for this run)
- `prompt_hash: str` (hash of the prompt template/config used)
- `tokens_prompt: Optional[int]`
- `tokens_completion: Optional[int]`
- `latency_ms: Optional[int]`
- `status: str` (e.g. `"ok"`, `"error"`)
- `error_message: Optional[str]`
- `created_at: datetime`
- `updated_at: datetime`

### 3.2. `SOWStep`

Fields (suggested):

- `id: int` primary key
- `run_id: int` (FK → `SOWRun.id`)
- `order_index: int` (0‑based or 1‑based sequential index)
- `step_id: Optional[str]` (human‑facing identifier like `"1"`, `"1.2"`, etc.)
- `phase: Optional[str]` (e.g. `"Design"`, `"Build"`, `"FAT"`, `"SAT"`)
- `title: str`
- `description: str`
- `actor: Optional[str]` (e.g. `"Customer"`, `"Integrator"`, `"Vendor"`)
- `location: Optional[str]` (e.g. `"Plant floor"`, `"OEM facility"`)
- `inputs: Optional[str]`
- `outputs: Optional[str]`
- `dependencies: Optional[str]` (free‑text reference to prior steps or prerequisites)
- `header_section_key: Optional[str]` (FK‑ish link to header sections table, if applicable)
- `start_page: Optional[int]`
- `end_page: Optional[int]`

In the DB init / migration logic, ensure these tables are created along with the existing document + header tables.

## 4. Environment configuration

Extend the existing settings/config module with SOW‑specific keys:

- `SOW_LLM_MODEL` (default to the same model used for headers, e.g. `anthropic/claude-3.5-sonnet`)
- `SOW_LLM_TIMEOUT_S` (e.g. 120)
- `SOW_LLM_MAX_INPUT_TOKENS` (e.g. 80000)
- `SOW_CACHE_DIR` (optional, for raw completion caching)

Follow the same pattern used by the header pipeline (reusing any shared OpenRouter client abstraction).

## 5. Prompt and response schema

Create a new service module (e.g. `backend/services/sow_extraction.py`) responsible for:

1. Building the SOW prompt.
2. Calling the LLM.
3. Parsing and validating the JSON response.
4. Writing `SOWRun` and `SOWStep` rows.

### 5.1. Prompt shape (guidelines)

The prompt should instruct the model to:

- Act as an **industrial automation engineer** reading a Scope of Work or Sequence of Operations.
- Produce a **step‑by‑step process** that covers the full lifecycle of the described system.
- Keep each step **atomic**: one main action per row.
- Preserve the **original wording** as much as possible in `description`; do not rewrite or summarize aggressively.
- Attach reasonable metadata (`phase`, `actor`, etc.) based on the text.

The model must respond with **pure JSON** shaped like:

```json
{
  "steps": [
    {
      "order_index": 1,
      "step_id": "1",
      "phase": "Design",
      "title": "Review customer RFQ and SOW",
      "description": "...",
      "actor": "Integrator",
      "location": "Office",
      "inputs": "Customer RFQ, SOW, reference standards",
      "outputs": "Approved internal SOW and clarifications",
      "dependencies": null,
      "header_section_key": "scope_of_work",
      "start_page": 3,
      "end_page": 4
    }
  ]
}
```

The service should validate and coerce this into the `SOWStep` model, tolerating minor format deviations (e.g. missing optional fields).

### 5.2. Ties to headers (optional but preferred)

When header sections exist:

- Prefer to include the **section key** of the source text in `header_section_key`.
- The simplest approach is:
  - for each SOW‑relevant section, send the section title + text as part of the prompt
  - ask the model to echo back the section key in each step that primarily comes from that section.

If headers are missing, the pipeline must still function; just leave `header_section_key` and page bounds `null`.

## 6. API design

Introduce a new router module (e.g. `backend/routers/sow.py`) with endpoints:

1. `POST /api/sow/{document_id}`
   - Triggers SOW extraction for the document.
   - Query params:
     - `force: bool = false` – when true, ignore existing runs and create a new one.
   - Behaviour:
     - Verify that the document is parsed; if not, return 400 with guidance.
     - Optionally verify that headers exist; if not, still allow a best‑effort run.
     - Compute `source_hash` from the text being sent.
     - If `force=false` and a successful run already exists for this `document_id` + `source_hash`, return that run instead of calling the model again.
     - Otherwise perform a new run and persist it.
   - Response:
     - `201 Created` or `200 OK` with a payload:

```json
{
  "documentId": 42,
  "runId": 7,
  "status": "ok",
  "meta": {
    "model": "...",
    "sourceHash": "...",
    "promptHash": "...",
    "tokens": { "prompt": 1234, "completion": 567 },
    "latencyMs": 1842,
    "createdAt": "..."
  },
  "steps": [ /* SOWStep records */ ]
}
```

2. `GET /api/sow/{document_id}`
   - Returns the latest successful run for that document, or `404` if none exist.

3. (Optional) `GET /api/sow/{document_id}/status`
   - Light‑weight status endpoint if extraction becomes asynchronous.
   - For now this can simply indicate whether a successful run exists.

### 6.1. Document status extension

Update the existing document status endpoint (e.g. `GET /api/documents/{document_id}/status`) to include:

```json
{
  "parsed": true,
  "headers": true,
  "sow": true
}
```

This allows the frontend (Phase 03) to know whether SOW data is available.

## 7. Implementation steps

1. Add `SOWRun` and `SOWStep` models and include them in DB initialisation.
2. Add SOW config fields to the Settings class / config module.
3. Implement `sow_extraction` service with:
   - prompt builder
   - LLM call via existing OpenRouter client
   - robust JSON parsing + validation
   - persistence helpers.
4. Add `sow` router with the endpoints described above; wire it into the FastAPI app.
5. Extend the document status endpoint to include `sow`.
6. Add minimal tests:
   - Unit test for JSON → `SOWStep` parsing using a sample response.
   - Integration‑style test that exercises the router with a fake LLM client (no real API call).

## 8. Checks & Acceptance Criteria

Before considering this phase complete:

1. Run the backend and ensure it starts cleanly with the new models.
2. With a sample document that has been parsed (and preferably has headers):
   - Call `POST /api/sow/{document_id}`.
   - Confirm the response matches the contract above and includes a non‑empty `steps` array.
3. Call `GET /api/sow/{document_id}` and verify it returns the same run/steps.
4. Call `GET /api/documents/{document_id}/status` and confirm a `sow` boolean is present and accurate.
5. Verify that repeated POSTs with `force=false` reuse the existing run, and with `force=true` create a new run.

Once all checks pass, commit with a message such as:

> `git commit -am "Phase 02 – add SOW extraction backend"`

This backend surface will then be wired into the UI in Phase 03.
