# Phase 01 – Bootstrap SOW Repo & Prune Specs

## 1. Objective

Create a new **SOW** repository based on the current **SimpleSpecs** codebase, but stripped down to:

- document upload / storage
- PDF parsing + text/line/page indexing
- header detection and outline alignment

All **per‑section specs extraction** code, database tables, API endpoints, background jobs, and UI should be removed. The result is a clean, smaller app that only knows how to:

1. register and parse documents
2. detect and align headers
3. expose this information over the API for later SOW‑specific features

This phase does **not** yet add SOW extraction logic; that happens in Phase 02.

## 2. Inputs & Starting Point

- Existing `SimpleSpecs` repo (current `main` branch).
- This `plan_sow.zip` and `agents_sow.zip`.
- Working Python 3.12 environment able to run the app as described in `README.md`.

The agent should assume the user will create a new empty GitHub repo (e.g. `hambonesoftware/SOW`) before pushing.

## 3. Outputs

By the end of this phase, the codebase should:

- live in a new repo (local folder can be renamed to `SOW` but paths inside the code can still use the `simplespecs` Python package name for now)
- **compile and run** the backend + frontend locally
- keep all **document + header** functionality intact
- have **no** `/api/specs…` endpoints, spec‑agent dispatch scripts, or specs‑specific tables in the default SQLite DB
- have an updated `README.md` that clearly describes the app as “SOW – Scope‑of‑Work Step Extractor (header‑only baseline)”

## 4. Primary Agents

- **Lead:** `SOW_RepoBootstrapAgent`
- **Support:** `SOW_DBAgent`, `SOW_QAAgent`

## 5. Detailed Tasks

### 5.1. Create new SOW repo shell

1. From the local `SimpleSpecs` clone, copy the entire directory to a new folder (e.g. `SOW`).
2. Remove any existing `.git` folder inside the new `SOW` directory.
3. Initialise a fresh Git repo in `SOW`:
   - `git init`
   - `git add .`
   - `git commit -m "Bootstrap SOW from SimpleSpecs"`
4. The remote origin will be added later by the user; do **not** hard‑code any Git remotes in code.

### 5.2. Identify and remove specs‑specific backend code

Work inside the new `SOW` folder.

1. Open the backend package (usually `backend/` with a Python module such as `backend/app` or similar).
2. Locate all modules and packages whose responsibility is **per‑section specs extraction**, including (names may vary slightly):
   - API routers exposing `/api/specs`, `/api/specs/status`, `/api/specs/{sectionId}`, etc.
   - service modules that:
     - dispatch multiple “discipline” agents per header section
     - write to `spec_records` or similar tables
   - CLI / script helpers such as `scripts/specs_dispatch.py`.
3. Delete those specs‑specific modules:
   - remove the API router file(s)
   - remove services that exist *only* for specs extraction
   - remove CLI scripts that exist *only* for specs extraction
4. In the main FastAPI app factory, remove any includes that mount `/api/specs` routes.
5. Search the codebase for `specs_dispatch`, `spec_records`, `/api/specs`, or similar marker strings and remove or neutralise any remaining dead references.

### 5.3. Remove specs DB tables and keep header/document schema

1. Locate the database models / schema definitions (SQLModel / SQLAlchemy models).
2. Identify any models dedicated purely to specs runs/results (for example, tables named like:
   - `spec_records`
   - `spec_runs`
   - any “agent result” tables that are only used by the specs workflow).
3. Remove those models from the code.
4. If there is an explicit migration or DB bootstrap file that creates these tables, remove or update it so that:
   - document registry tables remain
   - header outline / header section tables (e.g. `header_outline_cache`, `header_sections`) remain
   - specs‑only tables are no longer created.
5. Make sure the default SQLite DB can be created from scratch and the app still boots.

### 5.4. Prune specs‑specific frontend UI

1. In the `frontend/` folder, locate the views / components that:
   - show “Analyze Specs” buttons
   - show per‑discipline spec accordions
   - query `/api/specs…` endpoints.
2. Remove those components or strip out the specs‑related controls and network calls.
3. Ensure the **document list, upload flow, and header results view** remain fully functional.
4. On the header results screen, remove any buttons or text that mention “Specs” or “Analyze Specs” for now.

### 5.5. Rename top‑level branding to SOW

1. Update `README.md`:
   - Change the main heading to something like `# SOW (Scope‑of‑Work Step Extractor)`.
   - Briefly describe that this repo is derived from SimpleSpecs but is focused on SOW extraction.
   - Keep the local development steps but update any references that are clearly SimpleSpecs‑specific branding.
2. If there is an app title in the HTML (e.g. in `frontend/index.html`), change “SimpleSpecs” to “SOW”.

Do **not** rename the internal Python package (`simplespecs`) in this phase; that can be revisited later if needed.

## 6. Checks & Acceptance Criteria

Before completing this phase, the agent must:

1. **Run the backend** locally (e.g. `./start_local.sh` or equivalent) and confirm it starts without import errors.
2. Hit the health endpoint (usually `GET /api/health`) and confirm `{ "ok": true }` or equivalent.
3. Upload a sample document and:
   - ensure parsing completes
   - ensure header detection runs successfully
   - confirm that no `/api/specs` routes exist (manually or via auto‑generated docs).
4. Search the codebase for the strings `"spec_records"`, `"Analyze Specs"`, and `"/api/specs"` and verify that:
   - any remaining occurrences are either comments mentioning history **or**
   - they are part of a TODO explaining migration to the new SOW pipeline.

## 7. Handoff to Phase 02

Once all checks pass and the initial “SOW‑only (headers)” app runs cleanly, commit the changes with a message like:

> `git commit -am "Phase 01 – prune specs; keep headers for SOW"`

Phase 02 can then build the SOW extraction data model and API on top of this lean header‑only foundation.
