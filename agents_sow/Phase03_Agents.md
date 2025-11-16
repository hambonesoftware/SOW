# Agents for Phase 03 – Frontend SOW UI & Export

This file defines the agents to use with
`Phase03_Frontend_SOW_UI_Export.md` from `plan_sow.zip`.

The goal is to surface the new SOW pipeline to users:
- Provide a SOW tab/panel on the document detail screen.
- Let users trigger extraction and view the ordered steps.
- Enable CSV/JSON export of the SOW steps.

---

## Global assumptions for all agents

- Phases 01 and 02 are complete and merged.
- Backend provides:
  - `GET /api/documents/{document_id}/status` with `sow` flag.
  - `POST /api/sow/{document_id}`.
  - `GET /api/sow/{document_id}`.
- Frontend stack is already configured and building successfully.

All agents must:

- Keep UI changes incremental and consistent with the existing style.
- Avoid large-scale refactors unless absolutely necessary.

---

## Agent 1 – SOW_FrontendAgent (Lead)

**Role:** Implement all UI and frontend wiring for SOW extraction.

**Primary responsibilities:**

1. **SOW Panel/Tab**
   - Identify the existing document detail / header results view.
   - Add a new SOW panel or tab labelled “SOW Steps”.
   - Implement the conditional UI:
     - If no SOW present → show explanation + “Extract SOW steps” button.
     - While extraction running → show spinner / progress messaging.
     - After extraction → show SOW steps table with filters and exports.

2. **Status & Data Loading**
   - Ensure the document detail screen:
     - calls the status endpoint to obtain `parsed`, `headers`, and `sow`.
     - stores `sow` in its state.
   - If `status.sow === true`, automatically call `GET /api/sow/{document_id}`
     to populate the table when the SOW panel is opened.

3. **Extraction Trigger**
   - Hook up the “Extract SOW steps” button to `POST /api/sow/{document_id}`.
   - On success:
     - store the returned `steps` and any `meta`.
   - On error:
     - show a clear error message in the panel.
   - Optionally disable the button if headers are not yet available, with
     explanatory text.

4. **Table & Filters**
   - Create or reuse a generic table component to render SOW steps.
   - Columns should include at least:
     - Order / Step ID
     - Phase
     - Title
     - Actor
     - Location
     - Inputs
     - Outputs
     - Depends On
     - Section (resolved from `header_section_key` when possible)
     - Pages
   - Implement search and filter UX:
     - A free-text search box for `title`/`description`.
     - Dropdown filters for `phase` and `actor`.

5. **Export Actions**
   - Implement “Download CSV”:
     - Convert the current SOW steps in state into a CSV string.
     - Trigger a browser download with filename:
       - `sow_steps_doc-{documentId}.csv`
   - Implement “Download JSON”:
     - Export the steps (or full SOW payload) as pretty-printed JSON.
     - Trigger a browser download with filename:
       - `sow_steps_doc-{documentId}.json`

6. **Copy & Cleanup**
   - Remove or reword any lingering references to “Specs extraction”
     in the UI.
   - Add a short help text or tooltip in the SOW panel that explains:
     - SOW steps represent the end-to-end industrial process implied by
       the scope of work.
     - Each row is a single actionable step.

7. **Commit**
   - After all checks pass, commit with a message such as:
     - `git commit -am "Phase 03 – SOW frontend integration and export"`

**Constraints:**

- Keep changes focused on SOW; do not refactor unrelated pages.
- Follow the existing styling approach (CSS/utility classes/framework).

---

## Agent 2 – SOW_QAAgent (Support)

**Role:** End-to-end validation of SOW UI.

**Responsibilities:**

- Start both backend and frontend dev servers.
- Using a realistic SOW-like document, manually verify the flow:
  1. Upload document.
  2. Run parsing and headers (existing UX).
  3. Open SOW tab:
     - see the “Extract SOW steps” button.
  4. Click extract and observe:
     - spinner/progress.
     - eventual display of a populated SOW table.
  5. Exercise:
     - search term filter.
     - phase and actor filters.
     - CSV and JSON downloads; confirm downloaded content matches table.
  6. Refresh the page and confirm:
     - SOW steps are reloaded via `GET /api/sow/{document_id}` without
       re-running the LLM.

- Record any issues or known limitations in `QA_NOTES_PHASE03.md` in the
  repo root.

**Constraints:**

- Should not modify core frontend logic except for tiny fixes required
  to get tests or manual flows passing.
