# QA Notes – Phase 02 (Backend SOW Extraction)

## Automated coverage
- `pytest backend/tests/test_sow_service.py backend/tests/test_sow_router.py backend/tests/test_database_migrations.py`
  - Confirms JSON coercion for SOW steps, router happy-path including caching behaviour, and presence of new DB tables.

## Manual observations
- SOW endpoints expose `reused` flag so the UI can show when cached runs are returned.
- Document status payload now includes `sow` making it trivial to enable/disable frontend affordances.
- LLM prompts use `#sow#` fences and aggressively validate JSON before persisting to reduce failure cases.
