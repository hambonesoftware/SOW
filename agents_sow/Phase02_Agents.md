# Agents for Phase 02 – Backend SOW Extraction API & Data Model

This file defines the agents that should be used with
`Phase02_Backend_SOW_Extraction.md` from `plan_sow.zip`.

The goal is to add a new SOW extraction pipeline, including data models,
prompted LLM call, and `/api/sow` endpoints, while reusing the existing
document + header infrastructure.

---

## Global assumptions for all agents

- Phase 01 is complete and merged.
- The repo builds and runs:
  - Backend parses documents and detects headers.
  - There is no remaining specs pipeline.
- The environment provides:
  - Shell, git, Python tooling, test execution.
  - Network access for OpenRouter (or a way to inject a fake client).

All agents must:

- Keep the SOW features logically separate from headers, even if they reuse
  header data.
- Provide good docstrings and inline comments for new modules and models.
- Keep LLM prompts and response parsing **robust** and **defensive**.

---

## Agent 1 – SOW_BackendAgent (Lead)

**Role:** End-to-end owner of the SOW backend pipeline.

**Primary responsibilities:**

1. **Data Models**
   - Implement `SOWRun` and `SOWStep` models exactly as required in
     `Phase02_Backend_SOW_Extraction.md` (or with only minor pragmatic
     deviations clearly documented).
   - Integrate them into the existing DB initialisation logic so they are
     created alongside document + header tables.

2. **Settings / Config**
   - Extend the existing settings module with:
     - `SOW_LLM_MODEL`
     - `SOW_LLM_TIMEOUT_S`
     - `SOW_LLM_MAX_INPUT_TOKENS`
     - `SOW_CACHE_DIR` (if applicable)
   - Provide reasonable defaults (e.g., reuse the header model for now).

3. **SOW Extraction Service**
   - Create a module such as `backend/services/sow_extraction.py` that:
     - Accepts a `document_id`, DB session, and settings object.
     - Loads the parsed document text (and optionally header sections).
     - Builds a SOW-specific prompt per the plan requirements.
     - Calls the OpenRouter client.
     - Parses the JSON output into a list of `SOWStep` instances.
     - Creates a `SOWRun` record and associates its steps.
   - Implement robust JSON parsing:
     - Handle missing optional fields.
     - Provide clear error messages if the returned structure is invalid.
   - Include simple helper utilities:
     - computing `source_hash` from the text that was sent
     - computing `prompt_hash` from the prompt template.

4. **API Router**
   - Implement a router module such as `backend/routers/sow.py` that exposes:
     - `POST /api/sow/{document_id}` – trigger SOW extraction.
     - `GET /api/sow/{document_id}` – fetch latest run for a document.
     - Optional: `GET /api/sow/{document_id}/status`.
   - Wire this router into the main FastAPI app under the `/api` prefix.

5. **Document Status Extension**
   - Extend the existing document status endpoint so its response includes
     a `sow: bool` field.
   - The flag should be `true` when there is at least one successful
     `SOWRun` for the document.

6. **Idempotency & Caching**
   - Ensure `POST /api/sow/{document_id}` supports a `force` query param:
     - `force=false` (default): if a successful run exists for the current
       `source_hash`, return it without calling the LLM again.
     - `force=true`: always perform a new extraction and create a new run.

7. **Tests**
   - Add at least:
     - A unit test for converting a sample SOW JSON response into `SOWStep`
       objects.
     - An integration-style test that:
       - Inserts a small synthetic document into the DB.
       - Mocks the LLM client to return a known JSON payload.
       - Calls `POST /api/sow/{document_id}`.
       - Verifies we get `steps` back and they persisted correctly.

8. **Commit**
   - After all checks pass, commit with a message like:
     - `git commit -am "Phase 02 – add SOW extraction backend"`

**Constraints:**

- No changes to header-detection algorithms, except where necessary to
  expose header section keys/texts to SOW extraction.
- The LLM call should go through the existing OpenRouter client abstraction
  if one exists; do not duplicate HTTP client code.

---

## Agent 2 – SOW_DBAgent (Support)

**Role:** DB schema correctness and migrations for new SOW tables.

**Responsibilities:**

- Review `SOWRun` and `SOWStep` model definitions for consistency with
  existing models (naming, types, indexes).
- Update or generate DB migrations as required by the project’s migration
  strategy.
- Confirm that creating a fresh database results in:
  - all existing document/header tables
  - the new SOW tables
  - no orphaned references or broken foreign keys.

**Constraints:**

- Should not modify API routes or business logic.
- Changes should be limited to schema, migrations, and maybe DB init utilities.

---

## Agent 3 – SOW_QAAgent (Support)

**Role:** Validate that the backend SOW pipeline behaves correctly.

**Responsibilities:**

- Start the backend dev server.
- Use HTTP calls (curl, HTTP client, or tests) to simulate:
  - Document parsing.
  - Header detection.
  - SOW extraction via `POST /api/sow/{document_id}`.
- Confirm that:
  - Success path returns a non-empty `steps` array.
  - Failure paths (missing document, unparsed doc) return clear errors.
  - `GET /api/sow/{document_id}` returns the same data as the initial POST.
  - `GET /api/documents/{document_id}/status` includes an accurate `sow` flag.
- Capture findings and any known limitations in `QA_NOTES_PHASE02.md` in
  the repo root.

**Constraints:**

- Should not introduce new backend features; only small tweaks for logging
  or error clarity as needed.
