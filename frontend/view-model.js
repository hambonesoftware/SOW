const initialState = {
  documentId: null,
  text: '',
  buckets: [],
  status: '',
  results: null,
  telemetry: null,
  running: false,
};

function shallowClone(state) {
  return {
    documentId: state.documentId,
    text: state.text,
    buckets: [...state.buckets],
    status: state.status,
    results: state.results,
    telemetry: state.telemetry,
    running: state.running,
  };
}

export function createSpecSearchViewModel() {
  let state = { ...initialState };
  const listeners = new Set();

  const getState = () => shallowClone(state);

  function notify(prevState) {
    const snapshot = getState();
    listeners.forEach((listener) => listener(snapshot, prevState ? shallowClone(prevState) : null));
  }

  function setState(update) {
    const nextState = { ...state, ...update };
    const changed = Object.keys(update).some((key) => !Object.is(nextState[key], state[key]));
    if (!changed) return state;
    const prevState = state;
    state = nextState;
    notify(prevState);
    return state;
  }

  function setText(value) {
    setState({ text: value ?? '' });
  }

  function setDocumentId(value) {
    const normalized = value === '' || value === null || value === undefined ? null : value;
    setState({ documentId: normalized });
  }

  function setBuckets(values) {
    const uniqueBuckets = Array.from(new Set(values ?? [])).filter(Boolean);
    setState({ buckets: uniqueBuckets });
  }

  function resetResults() {
    setState({ results: null, telemetry: null });
  }

  async function runSearch() {
    const text = (state.text || '').trim();
    const buckets = state.buckets || [];

    if (!text) {
      setState({ status: 'Paste specification text to run the search.' });
      return null;
    }

    if (!buckets.length) {
      setState({ status: 'Select at least one bucket.' });
      return null;
    }

    setState({ running: true, status: 'Running…' });

    try {
      const payload = {
        document_id: state.documentId || null,
        text,
        buckets,
      };

      const response = await fetch('/api/spec-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const contentType = response.headers.get('content-type') || '';
      const isJson = contentType.includes('application/json');
      const body = isJson ? await response.json() : await response.text();
      const telemetry = isJson && body && typeof body === 'object' ? body.meta ?? null : null;

      if (!response.ok) {
        const errorText = isJson ? body?.error || body?.message : body;
        const status = response.status >= 500
          ? `Server error (${response.status}). Please try again.`
          : errorText
            ? `Request failed (${response.status}): ${errorText}`
            : `Request failed (${response.status}).`;

        setState({ results: null, telemetry, status });
        return body;
      }

      if (isJson) {
        const status = body?.ok !== false ? 'Extraction complete.' : body?.error || 'Extraction failed.';
        setState({
          results: body?.ok !== false ? body?.data ?? null : null,
          telemetry,
          status,
        });
        return body;
      }

      setState({
        results: null,
        telemetry,
        status: 'Unexpected response format from /api/spec-search.',
      });
      return null;
    } catch (error) {
      console.error(error);
      setState({ results: null, telemetry: null, status: 'Network error when calling /api/spec-search.' });
      return null;
    } finally {
      setState({ running: false });
    }
  }

  function subscribe(listener) {
    listeners.add(listener);
    listener(getState(), null);
    return () => listeners.delete(listener);
  }

  return {
    subscribe,
    getState,
    setText,
    setDocumentId,
    setBuckets,
    resetResults,
    runSearch,
  };
}
