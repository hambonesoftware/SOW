# Phase 03 – Frontend SOW UI & Export

## 1. Objective

Expose the new SOW extraction pipeline to users through the existing web UI:

- Let users trigger SOW extraction for a parsed document.
- Show the resulting ordered SOW steps in a rich, filterable table.
- Provide CSV / JSON export options.

This phase does not change the core backend logic beyond small wiring tweaks; it focuses on frontend integration and user experience.

## 2. Inputs & Assumptions

- Phase 01 and Phase 02 are complete and merged.
- The backend exposes:
  - `GET /api/documents/{document_id}/status` with `parsed`, `headers`, and `sow` booleans.
  - `POST /api/sow/{document_id}` to create or reuse a SOW run.
  - `GET /api/sow/{document_id}` to fetch the latest run and steps.
- The frontend already has:
  - a document list / document detail view
  - a header‑results view that can call `/api/headers/{document_id}`.

## 3. UX design (high‑level)

On the **document detail** or **header results** screen:

1. Add a new SOW panel / tab labelled **“SOW Steps”**.
2. Within this panel:
   - If `status.sow === false`:
     - Show a short explanation: “No SOW extraction has been run for this document.”
     - Show a primary button: **“Extract SOW steps”**.
   - While a run is in progress:
     - Disable the button and show a spinner / “Extracting SOW steps…” message.
   - Once data is available:
     - Render a table of steps with key columns:
       - `#` (order_index or step_id)
       - `Phase`
       - `Title`
       - `Actor`
       - `Location`
       - `Inputs`
       - `Outputs`
       - `Depends on`
       - `Section` (resolved from `header_section_key` to display number + title)
       - `Pages`
     - Provide:
       - a search box to filter by substring within `title` or `description`
       - dropdown filters for `phase` and `actor`
       - buttons for **“Download CSV”** and **“Download JSON”**.

## 4. API integration

### 4.1. Document status wiring

1. Ensure the frontend code that loads the selected document also calls the document status endpoint.
2. Extend the local state shape to include `sow: boolean`.
3. Use this flag in the SOW panel to decide whether to show the “Extract SOW steps” button vs the table.

### 4.2. SOW extraction trigger

1. Implement a function such as `runSowExtraction(documentId)` that:
   - sends `POST /api/sow/{documentId}`
   - handles errors (network, 4xx/5xx) with a clear message in the UI
   - updates local state with the returned `steps` and `meta`.
2. Hook this function up to the **“Extract SOW steps”** button.
3. Consider disabling the button if parsing or headers are not yet complete; in that case show a message like:
   > “SOW extraction is available after parsing and header alignment. Please run headers first.”

### 4.3. SOW data loading

1. Implement a `loadSow(documentId)` function that:
   - calls `GET /api/sow/{documentId}`
   - if `404`, treats it as “no SOW yet” (do not show as an error)
   - otherwise stores the steps + meta in state.
2. When a document is selected:
   - load its status
   - if `status.sow === true`, call `loadSow(documentId)` automatically.

## 5. Table + filters implementation

1. Create or reuse a table component for SOW steps.
2. Map fields from the API response to table rows.
3. For `Section`:
   - If `header_section_key` is present and the frontend already has header section metadata, render it as e.g. `"5.2 – Sequence of Operations"`.
   - If not available, leave blank.
4. Search:
   - Maintain a `searchTerm` state.
   - Filter steps where `title` or `description` contains the term (case‑insensitive).
5. Dropdown filters:
   - Build unique sorted lists of `phase` and `actor` from the current steps.
   - Allow single‑select filtering; when “All” is selected, show everything.

## 6. Export functionality

1. **CSV export**
   - Build a CSV string with a header row and all steps.
   - Include at least the columns visible in the table.
   - Trigger a download in the browser (e.g. by creating a Blob and a temporary `<a>`).
2. **JSON export**
   - Export the raw `steps` array (or full API payload) as pretty‑printed JSON.
   - Same download mechanism as CSV.

Name the files using the pattern:

- `sow_steps_doc-{documentId}.csv`
- `sow_steps_doc-{documentId}.json`

## 7. Visual & copy updates

1. Remove or reword any remaining references to “Specs extraction” in the UI.
2. Make it clear on the header results screen that:
   - Headers form the backbone for both specs and SOW analysis.
   - This app is currently focused on SOW step extraction.
3. Add a brief help text or tooltip near the SOW panel explaining what’s being extracted:
   > “These steps describe the end‑to‑end industrial process implied by this Scope of Work. Each row is a single actionable step.”

## 8. Checks & Acceptance Criteria

Manually verify the following with a realistic SOW document:

1. Upload document → run parsing → run headers (from existing UI).
2. Open the document detail:
   - See the SOW tab/panel.
   - If no SOW yet, see the “Extract SOW steps” button.
3. Click **“Extract SOW steps”**:
   - Spinner/message appears.
   - After completion, a table of steps is shown.
4. Use filters and search; confirm the table contents change as expected.
5. Click **“Download CSV”** and **“Download JSON”**:
   - Files download.
   - Opening them shows data consistent with the on‑screen table.
6. Refresh the page:
   - The app detects existing SOW data and loads it without re‑running the LLM.
7. Confirm that no “Specs” buttons or panels remain in the UI.

Once all checks pass, commit with a message such as:

> `git commit -am "Phase 03 – SOW frontend integration and export"`

At this point the SOW app should be usable end‑to‑end for step‑by‑step SOW extraction driven by headers and document text.
