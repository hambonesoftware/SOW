# SOW Refactor Agents – Index

This bundle (`agents_sow.zip`) defines the agents that work with `plan_sow.zip`
to refactor **SimpleSpecs** into a **SOW** (Scope-of-Work) step extractor.

The structure mirrors the phases in `plan_sow.zip`:

- `Phase01_Agents.md` → supports `Phase01_Repo_Prune_SOW.md`
- `Phase02_Agents.md` → supports `Phase02_Backend_SOW_Extraction.md`
- `Phase03_Agents.md` → supports `Phase03_Frontend_SOW_UI_Export.md`

Each file describes one or more agents that should be invoked for that phase,
along with their responsibilities and boundaries.

## Usage

For each phase:

1. Open the matching **plan file** from `plan_sow.zip`.
2. Open the matching **agents file** from `agents_sow.zip`.
3. In your /agent or Codex environment, provide:
   - The phase plan file as the main task description.
   - The corresponding agents file to define the roles and constraints.
4. Let the lead agent run end-to-end for that phase.
5. Only after a clean completion and commit, move on to the next phase.
