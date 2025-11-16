# QA Notes — Phase 03

## Automated checks
- `pytest` (entire suite) — see log below.

## Additional verification
- Exercised the new SOW panel states (no document selected, prerequisites missing, data loaded) via manual JS state inspection to ensure the correct copy/buttons render before wiring it into the DOM.
- Confirmed CSV/JSON export helpers reuse the same filtered dataset and section lookup that power the table, so downloads mirror the on-screen data.
- Manual browser verification with a realistic SOW PDF is still pending because the hosted LLM parsing flow is unavailable inside this container. Please rerun the end-to-end checklist in a staging environment with OpenRouter credentials before shipping.
