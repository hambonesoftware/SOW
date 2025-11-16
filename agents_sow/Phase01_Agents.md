# Agents for Phase 01 – Bootstrap SOW Repo & Prune Specs

This file defines the agents that should be used with
`Phase01_Repo_Prune_SOW.md` from `plan_sow.zip`.

The goal is to create a new SOW-focused repo based on SimpleSpecs,
while **removing all specs-specific functionality** and preserving
document + header parsing.

---

## Global assumptions for all agents

- The environment provides:
  - Shell access (git, python, uvicorn, npm/pnpm/yarn as needed).
  - File editing (create, modify, delete files).
  - Ability to run test commands and the dev servers.
- The source repo is a clone of `hambonesoftware/SimpleSpecs` on the `main` branch.
- The work for this phase happens in a new directory (e.g. `SOW`) created from that clone.

All agents must:

- **Never** introduce secrets or real API keys in code or config.
- Prefer small, focused commits over huge monolithic changes when possible.
- Keep naming conservative and incremental; do not perform mass renames
  that are not explicitly requested in the plan.

---

## Agent 1 – SOW_RepoBootstrapAgent (Lead)

**Role:** End-to-end owner of Phase 01.

**Primary responsibilities:**

1. **Repo Bootstrap**
   - Copy the existing `SimpleSpecs` tree into a new `SOW` directory.
   - Remove any `.git` directory inside `SOW`.
   - Initialise a new git repository:
     - `git init`
     - `git add .`
     - `git commit -m "Bootstrap SOW from SimpleSpecs"`

2. **Specs Removal – Backend**
   - Scan `backend/` (and subpackages) to identify modules, routers, and services
     related to *specs extraction*. Typical markers:
       - API paths beginning with `/api/specs`
       - Names containing `specs`, `spec_records`, `spec_runs`, or “agent”
         logic tied to per-section specs.
   - Remove:
       - Specs-related router modules that expose `/api/specs` endpoints.
       - Specs-only service modules that dispatch specs agents or write
         specs-specific tables.
       - Specs-specific CLI helpers (e.g. `scripts/specs_dispatch.py`).
   - Update the main FastAPI app factory so it no longer includes the
     specs router(s).

3. **Specs Removal – Database**
   - Locate the database models (SQLModel/SQLAlchemy).
   - Identify and remove:
       - `SpecRecord`, `SpecRun`, or any table that exists *only* to store
         specs extraction results.
   - Update DB initialisation / migrations to **exclude** specs tables while
     keeping:
       - document registry tables
       - header outline and header section tables.

4. **Specs Removal – Frontend**
   - In `frontend/`, find components and views that:
       - Show “Analyze Specs” buttons.
       - Display per-discipline specs accordions or details.
       - Call `/api/specs` endpoints.
   - Remove those UI pieces or strip out the specs-related portions
     while keeping the **document list, upload flow, and header view** intact.

5. **Branding & README**
   - Update `README.md` to describe the app as SOW-focused:
       - Change top-level title to something like
         `SOW (Scope-of-Work Step Extractor)`.
       - Mention that it is derived from SimpleSpecs and currently focuses
         on document upload + parsing + header alignment as a baseline.
   - Update any obvious frontend title text (e.g. `<title>` in `index.html`)
     from “SimpleSpecs” to “SOW” where appropriate.

6. **Sanity Checks**
   - Run the backend locally (e.g. via `./start_local.sh` or `uvicorn ...`).
   - Confirm there are no import or schema errors on startup.
   - Hit the health endpoint (e.g. `GET /api/health`) and ensure it returns
     a healthy response.
   - Upload a sample document through the UI and verify:
       - Parsing runs successfully.
       - Header detection still works.
   - Confirm that **no** `/api/specs` endpoints are reachable, either by
     browsing the OpenAPI docs or by curl/HTTP tests.
   - Search the tree for `"/api/specs"`, `"spec_records"`, and `"Analyze Specs"`:
       - If any remain, they should only appear in comments or TODOs describing
         historical context, not active code paths.

7. **Commit**
   - When all of the above is complete and working, create a commit like:
     - `git commit -am "Phase 01 – prune specs; keep headers for SOW"`

**Constraints:**

- Do not change the internal Python package name (`simplespecs`) in this phase.
- Do not modify any header detection logic yet, except to remove direct
  dependencies on specs.
- Do not change the DB URI or environment variable names yet, except to
  remove specs-specific ones.

---

## Agent 2 – SOW_DBAgent (Support)

**Role:** Ensure database integrity after specs tables are removed.

**Responsibilities:**

- Review changes proposed by `SOW_RepoBootstrapAgent` to models/migrations.
- Confirm that:
  - All tables required for documents and headers are still created.
  - No references remain to removed specs tables.
- If the project uses Alembic or a similar migration tool, adjust or regenerate
  migrations as needed to reflect the new schema.

**Constraints:**

- Should not introduce new features; focus only on keeping schema coherent.
- Any schema changes must be backward-compatible enough to allow creating
  a fresh SQLite DB without manual intervention.

---

## Agent 3 – SOW_QAAgent (Support)

**Role:** Validation, smoke tests, and sanity checks.

**Responsibilities:**

- Run the documented dev startup commands.
- Perform black-box checks:
  - Upload at least one document.
  - Trigger parsing and headers via the UI or via API calls.
- Verify that there is no user-visible trace of “Specs” features:
  - No buttons labeled “Analyze Specs”.
  - No specs dashboards.
- Document any known issues or edge cases in a short `QA_NOTES_PHASE01.md`
  file in the repo root.

**Constraints:**

- Should not modify business logic code; only add small test helpers or
  QA notes when necessary.
