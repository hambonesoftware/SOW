# SOW Refactor Plan – Plan Index

This bundle (`plan_sow.zip`) defines the minimal phases required to turn the existing **SimpleSpecs** app into a new **SOW** app that focuses on extracting step‑by‑step industrial process flows from Scope of Work (SOW) documents.

Use this together with `agents_sow.zip`. Each phase file is designed so that a single Codex/ChatGPT Agent run can complete that phase end‑to‑end.

## Phases

1. **Phase 01 – Bootstrap SOW Repo & Prune Specs**
   - Clone/fork the existing `SimpleSpecs` repo into a new repo (e.g., `SOW`).
   - Remove all "specs" extraction workflows, keeping only document parsing, header detection, and shared infrastructure.
   - Update naming and config so the project is clearly a SOW extractor, not a generic specs tool.

2. **Phase 02 – Backend SOW Extraction API & Data Model**
   - Introduce a new SOW‑specific run + step data model.
   - Add an LLM‑backed extraction pipeline that reads the parsed document text and returns ordered SOW steps with metadata.
   - Expose `/api/sow` endpoints mirroring the ergonomics of the current `/api/headers` endpoints.

3. **Phase 03 – Frontend SOW UI & Export**
   - Replace the existing Specs UI with a SOW‑focused screen.
   - Integrate the new `/api/sow` endpoints: status, run, and read.
   - Provide tabular, filterable SOW step views plus CSV/JSON export.

## How to use this plan

- Pick **one phase file at a time** and hand it to the appropriate agent(s) from `agents_sow.zip`.
- Ask the agent to:
  1. Read the phase file carefully.
  2. Apply all changes described there to the current codebase.
  3. Run the listed checks.
  4. Summarise what changed and any TODOs.

Once Phase 01 is merged and green, move to Phase 02, then Phase 03.

Each phase is intentionally self‑contained so that it can be completed in a single agent execution.
