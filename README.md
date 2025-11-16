# SOW (Scope-of-Work Header Baseline)

SOW is a trimmed adaptation of the SimpleSpecs codebase that focuses on the
parts needed to ingest PDF documents, parse their contents, and align headers
into a reliable outline. All specification extraction, approval, and risk
comparison code has been removed so the application now provides a lean
foundation for future Scope-of-Work features.

## Local development

1. Create and activate a virtual environment:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the environment template and adjust values as needed:
   ```bash
   cp .env.template .env
   ```
4. Launch the backend locally (hot reload enabled):
   ```bash
   ./start_local.sh
   ```
   On Windows PowerShell:
   ```powershell
   .\start_local.bat
   ```
   The helper scripts honour `HOST`, `PORT`, and `LOG_LEVEL` if they are set in
   your `.env` file.
5. Visit `http://localhost:8000/api/health` to verify the service responds with
   `{ "ok": true }`.
6. Open `http://localhost:8000/` in your browser to use the lightweight SOW web
   app; the FastAPI server serves the static frontend from the same origin.

   If you need to host the static files separately, add a
   `<meta name="api-base">` tag to `frontend/index.html` or assign `window.API_BASE`
   at runtime with the full API origin (e.g. `http://127.0.0.1:8000`). The
   frontend falls back to the same origin when no override is provided.

The server creates the `uploads/` and `exports/` directories on startup if they
are missing. Adjust their locations via the `UPLOAD_DIR` and `EXPORT_DIR`
environment variables.

## Core workflow and endpoints

SOW keeps a small set of endpoints that cover the document lifecycle:

| Step      | Endpoint(s) |
|-----------|-------------|
| Upload    | `POST /api/upload` (multipart form field `file`) returns the stored `Document`. Use `DELETE /api/files/{id}` to remove uploads. |
| List      | `GET /api/files` returns all uploaded documents ordered by recency. |
| Parse     | `POST /api/parse/{document_id}` parses the PDF and returns blocks, tables, and basic metadata. Repeated calls reuse cached artefacts. |
| Status    | `GET /api/documents/{document_id}/status` reports `{ parsed: bool, headers: bool }`. |
| Cached headers | `GET /api/headers/{document_id}` fetches the last persisted outline + aligned sections. `GET /api/headers/{document_id}/outline` returns the raw outline payload only. |
| Fresh headers | `POST /api/headers/{document_id}` reruns the header alignment pipeline. Append `?align=sequential` or `?trace=1` to tune behaviour and request trace data. |
| Section text | `GET /api/headers/{document_id}/section-text?start=…&end=…&section_key=…` streams the lines belonging to a stored section span. |

The default frontend calls these endpoints in order: upload → parse → detect
headers. Once headers are cached the UI can load them instantly via
`GET /api/headers/{document_id}` and only hits the LLM when you click
**Detect headers**.

## Header extraction configuration

SOW sends the document text to OpenRouter for a high-fidelity outline. Configure
behaviour via the following environment variables (also available in
`.env.template`):

- `OPENROUTER_API_KEY`: required for LLM access.
- `HEADERS_MODE`: keep `llm_full` to enable the OpenRouter pipeline.
- `HEADERS_LLM_MODEL`: fully qualified OpenRouter model identifier (default
  `anthropic/claude-3.5-sonnet`).
- `HEADERS_LLM_MAX_INPUT_TOKENS`: approximate token budget per request chunk
  (default `120000`).
- `HEADERS_LLM_TIMEOUT_S`: request timeout in seconds (default `120`).
- `HEADERS_LLM_CACHE_DIR`: on-disk cache for previously processed documents.
- `HEADERS_CACHE_TO_DB`: set to `0` to disable persisting raw outlines to SQLite
  (disk caching remains active).

### Sequential alignment strategy

The default header locator uses a forward-only, parent-bounded sequential search
that resists table-of-contents anchors and running headers. Tune behaviour via
these environment variables:

```
HEADERS_ALIGN_STRATEGY=sequential  # use `legacy` to revert to the prior locator
HEADERS_SUPPRESS_TOC=1            # ignore pages that look like TOCs
HEADERS_SUPPRESS_RUNNING=1        # filter repeated running headers/footers
HEADERS_NORMALIZE_CONFUSABLES=1   # normalise numeric lookalikes (I/l → 1)
HEADERS_FUZZY_THRESHOLD=80        # token-set similarity for title matching
HEADERS_WINDOW_PAD_LINES=40       # expand parent search windows by ±N lines
HEADERS_BAND_LINES=5              # top/bottom lines per page considered a running band
HEADERS_L1_REQUIRE_NUMERIC=1      # insist on numeric prefixes for L1 anchors before fallback
HEADERS_L1_LOOKAHEAD_CHILD_HINT=30  # scan ahead for 1.1-style hints when ranking anchors
HEADERS_MONOTONIC_STRICT=1        # enforce forward-only anchoring with duplicate retries
HEADERS_REANCHOR_PASS=1           # repair parents that landed after their children
```

Recent hardening adds numeric-first anchoring for level-1 chapters, a strict
monotonic gate that retries later duplicates, running-header suppression, and a
coherence sweep that repositions parents ahead of their children. Enable tracing
(`?trace=1`) to inspect the sequential decisions end-to-end; the response
includes the `events`, `path`, and `summary_path` emitted by the tracer.

### DB-first header retrieval

Header discovery hydrates the UI from the persisted SQLite cache before invoking
the LLM:

1. `GET /api/documents/{document_id}/status` returns `{ parsed: bool, headers: bool }`.
2. If `headers` is `true`, `GET /api/headers/{document_id}` returns the stored
   outline, metadata, and aligned sections without touching the LLM.
3. `POST /api/headers/{document_id}` refreshes the outline on demand. The handler
   deduplicates runs by `document_id` + `prompt_hash` + `source_hash`, writes the
   outline to both SQLite (`header_outline_cache`) and the on-disk cache, and
   persists aligned sections.

Sample response from `GET /api/headers/42`:

```json
{
  "documentId": 42,
  "runId": 7,
  "outline": { "headers": [{ "text": "Introduction", "number": "1" }] },
  "meta": {
    "model": "anthropic/claude-3.5-sonnet",
    "promptHash": "9b0d…",
    "sourceHash": "c2a1…",
    "tokens": { "prompt": null, "completion": null },
    "latencyMs": 1842,
    "createdAt": "2025-01-01T00:00:00+00:00"
  },
  "sections": [
    {
      "section_key": "intro",
      "title": "Introduction",
      "number": "1",
      "level": 1,
      "start_global_idx": 12,
      "end_global_idx": 48,
      "start_page": 2,
      "end_page": 3
    }
  ],
  "simpleheaders": [
    {
      "text": "Introduction",
      "number": "1",
      "level": 1,
      "page": 2,
      "global_idx": 12,
      "section_key": "intro"
    }
  ],
  "mode": "llm_full"
}
```

When `HEADERS_CACHE_TO_DB=0`, sections continue to persist in SQLite but the raw
outline is only written to disk; the GET endpoints respond with `404` until a new
cached outline is created.

### Vector-enhanced locator (opt-in)

Set `HEADER_LOCATE_USE_EMBEDDINGS=1` to swap the sequential window search for a
vector-guided locator. The LLM outline remains the source of truth—each header is
matched against sliding line windows scored via lexical BM25/fuzzy matching,
cosine similarity, font size, and page position. Candidates that resemble TOC
entries (dot leaders, "contents", index terms) or running headers are discarded
before selection.

Key tuning knobs:

```
HEADER_LOCATE_USE_EMBEDDINGS=1
HEADER_LOCATE_FUSE_WEIGHTS=0.55,0.30,0.10,0.05  # lexical, cosine, font-rank, vertical bonuses
HEADER_LOCATE_MIN_LEXICAL=0.30
HEADER_LOCATE_MIN_COSINE=0.25
HEADER_LOCATE_PREFER_LAST_MATCH=1
```

Embeddings default to the local `sentence-transformers/all-MiniLM-L6-v2` model.
Override the provider or remote model via:

```
EMBEDDINGS_PROVIDER=local                # or 'openrouter'
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDINGS_CACHE_DIR=.cache/emb          # per-text + per-document vector cache
EMBEDDINGS_OPENROUTER_MODEL=openai/text-embedding-3-small
EMBEDDINGS_OPENROUTER_TIMEOUT_S=60
```

## Frontend highlights

The bundled static frontend provides a minimal workflow:

- Drag-and-drop or browse to upload PDFs.
- Select a document to trigger parsing and header detection.
- Inspect the LLM raw response, outline, and aligned sections directly in the
  browser.
- Download the parse or header JSON artefacts for offline analysis.

This stripped-down UI is intentionally narrow so future Scope-of-Work features
can be layered on top without carrying legacy specification approval code.
