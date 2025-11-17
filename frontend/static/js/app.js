import {
  listDocuments,
  uploadDocument,
  parseDocument,
  fetchDocumentStatus,
  fetchSowRun,
  createSowRun,
  downloadBlob,
  toCsv,
} from './api.js';
import {
  initDropZone,
  createUploadTracker,
  renderDocumentList,
  setDocumentMeta,
  setPanelLoading,
  setPanelError,
  renderParseSummary,
  renderProcessSteps,
  showToast,
} from './ui.js';

function createDefaultSowUiState() {
  return {
    loading: false,
    running: false,
    errorMessage: null,
  };
}

const state = {
  documents: [],
  selectedId: null,
  parse: null,
  statusById: new Map(),
  sowById: new Map(),
  sowUi: createDefaultSowUiState(),
};

const elements = {
  dropZone: document.querySelector('#drop-zone'),
  fileInput: document.querySelector('#file-input'),
  browseButton: document.querySelector('#browse-button'),
  uploadProgress: document.querySelector('#upload-progress'),
  refreshDocuments: document.querySelector('#refresh-documents'),
  documentsStatus: document.querySelector('#documents-status'),
  documentsList: document.querySelector('#documents-list'),
  documentMeta: document.querySelector('#document-meta'),
  workspaceSubtitle: document.querySelector('#workspace-subtitle'),
  parseContent: document.querySelector('#parse-content'),
  sowContent: document.querySelector('#sow-content'),
  processButton: document.querySelector('#run-sow'),
  sowExportCsv: document.querySelector('[data-export="sow-csv"]'),
  sowExportJson: document.querySelector('[data-export="sow-json"]'),
};

function setDocumentsStatus(message) {
  if (elements.documentsStatus) {
    elements.documentsStatus.textContent = message;
  }
}

function currentDocument() {
  return state.documents.find((doc) => doc.id === state.selectedId) ?? null;
}

function currentSteps() {
  const payload = state.selectedId ? state.sowById.get(state.selectedId) : null;
  return Array.isArray(payload?.steps) ? payload.steps : [];
}

function setSowExportAvailability(enabled) {
  [elements.sowExportCsv, elements.sowExportJson].forEach((button) => {
    if (!button) return;
    button.disabled = !enabled;
  });
}

function setProcessButtonState() {
  if (!elements.processButton) return;
  const docId = state.selectedId;
  if (!docId) {
    elements.processButton.disabled = true;
    elements.processButton.textContent = 'Process steps';
    return;
  }
  if (state.sowUi.running) {
    elements.processButton.disabled = true;
    elements.processButton.textContent = 'Processing…';
    return;
  }
  const status = state.statusById.get(docId);
  if (!status?.parsed) {
    elements.processButton.disabled = true;
    elements.processButton.textContent = 'Parsing document…';
    return;
  }
  elements.processButton.disabled = false;
  elements.processButton.textContent = 'Process steps';
}

async function refreshDocuments({ selectFirst = false } = {}) {
  try {
    const documents = await listDocuments();
    state.documents = documents;
    if (!documents.length) {
      setDocumentsStatus('No documents uploaded yet.');
    } else {
      setDocumentsStatus(`${documents.length} document${documents.length === 1 ? '' : 's'} available.`);
    }
    if (!documents.find((doc) => doc.id === state.selectedId)) {
      state.selectedId = null;
      state.parse = null;
      state.sowUi = createDefaultSowUiState();
    }
    renderDocumentList(elements.documentsList, documents, state.selectedId);
    if (selectFirst && documents.length) {
      await selectDocument(documents[0].id);
    } else {
      renderWorkspace();
    }
  } catch (error) {
    console.error('Failed to list documents', error);
    setDocumentsStatus('Unable to load documents.');
  }
}

async function selectDocument(documentId) {
  const numericId = Number(documentId);
  if (!Number.isFinite(numericId) || numericId === state.selectedId) {
    return;
  }
  state.selectedId = numericId;
  state.parse = null;
  state.sowUi = createDefaultSowUiState();
  renderDocumentList(elements.documentsList, state.documents, state.selectedId);
  renderWorkspace();
  try {
    await ensureParse(numericId);
  } catch (error) {
    console.error('Parse request failed', error);
    setPanelError(elements.parseContent, 'Unable to parse document.');
    return;
  }
  try {
    await loadExistingSow(numericId);
  } catch (error) {
    console.warn('Unable to load existing SOW run', error);
  }
}

function renderWorkspace() {
  const doc = currentDocument();
  setDocumentMeta(elements.documentMeta, doc);
  if (elements.workspaceSubtitle) {
    elements.workspaceSubtitle.textContent = doc ? `Viewing ${doc.filename}` : 'Select a document to begin.';
  }
  if (!doc) {
    setPanelLoading(elements.parseContent, 'Select a document to view parse details.');
    setPanelLoading(elements.sowContent, 'Select a document to run process steps.');
    setProcessButtonState();
    setSowExportAvailability(false);
    return;
  }
  if (!state.parse) {
    setPanelLoading(elements.parseContent, 'Loading parse summary…');
  } else {
    renderParseSummary(elements.parseContent, state.parse);
  }
  renderSowPanel();
}

async function ensureStatus(documentId) {
  if (state.statusById.has(documentId)) {
    return state.statusById.get(documentId);
  }
  try {
    const status = await fetchDocumentStatus(documentId);
    state.statusById.set(documentId, status);
    if (state.selectedId === documentId) {
      renderSowPanel();
    }
    return status;
  } catch (error) {
    console.warn('Failed to fetch document status', error);
    return null;
  }
}

async function ensureParse(documentId) {
  const status = await ensureStatus(documentId);
  if (status?.parsed && state.parse) {
    renderParseSummary(elements.parseContent, state.parse);
    setProcessButtonState();
    return state.parse;
  }
  const payload = await parseDocument(documentId);
  state.parse = payload;
  const nextStatus = { ...(status ?? {}), parsed: true };
  state.statusById.set(documentId, nextStatus);
  renderParseSummary(elements.parseContent, payload);
  setProcessButtonState();
  return payload;
}

async function loadExistingSow(documentId) {
  const isActive = () => state.selectedId === documentId;
  if (isActive()) {
    state.sowUi.loading = true;
    renderSowPanel();
  }
  try {
    const payload = await fetchSowRun(documentId);
    state.sowById.set(documentId, payload);
    const status = state.statusById.get(documentId) ?? {};
    state.statusById.set(documentId, { ...status, sow: true });
    if (isActive()) {
      state.sowUi.errorMessage = null;
    }
    return payload;
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unable to load process steps.';
    if (/404/.test(message)) {
      const status = state.statusById.get(documentId) ?? {};
      state.statusById.set(documentId, { ...status, sow: false });
      state.sowById.delete(documentId);
      if (isActive()) {
        state.sowUi.errorMessage = null;
      }
      return null;
    }
    if (isActive()) {
      state.sowUi.errorMessage = message;
      showToast(message, 'error');
    }
    throw error;
  } finally {
    if (isActive()) {
      state.sowUi.loading = false;
      renderSowPanel();
    }
  }
}

function renderSowPanel() {
  const container = elements.sowContent;
  if (!container) return;
  setSowExportAvailability(false);
  setProcessButtonState();

  if (!state.selectedId) {
    container.innerHTML = '<p class="panel-status">Select a document to run process steps.</p>';
    return;
  }

  const status = state.statusById.get(state.selectedId);
  if (!status?.parsed) {
    setPanelLoading(container, 'Parsing document…');
    return;
  }

  if (state.sowUi.running) {
    setPanelLoading(container, 'Processing steps…');
    return;
  }

  if (state.sowUi.loading) {
    setPanelLoading(container, 'Loading process steps…');
    return;
  }

  if (state.sowUi.errorMessage) {
    container.innerHTML = '';
    const error = document.createElement('p');
    error.className = 'panel-error';
    error.textContent = state.sowUi.errorMessage;
    container.append(error);
    const hint = document.createElement('p');
    hint.className = 'panel-status';
    hint.textContent = 'Try running the extraction again.';
    container.append(hint);
    return;
  }

  const steps = currentSteps();
  if (!steps.length) {
    container.innerHTML = '';
    const intro = document.createElement('p');
    intro.className = 'panel-status';
    intro.textContent = 'Process steps are available after parsing. Click “Process steps” to run the extraction.';
    container.append(intro);
    return;
  }

  const payload = state.sowById.get(state.selectedId);
  container.innerHTML = '';
  const summary = document.createElement('p');
  summary.className = 'panel-status sow-summary';
  const count = `${steps.length} step${steps.length === 1 ? '' : 's'} extracted`;
  summary.textContent = payload?.model ? `${count} • ${payload.model}` : count;
  container.append(summary);
  renderProcessSteps(container, steps);
  setSowExportAvailability(true);
}

async function handleProcessSteps() {
  const documentId = state.selectedId;
  if (!documentId || state.sowUi.running) return;
  const status = state.statusById.get(documentId);
  if (!status?.parsed) return;

  state.sowUi.running = true;
  state.sowUi.errorMessage = null;
  renderSowPanel();

  try {
    const payload = await createSowRun(documentId);
    state.sowById.set(documentId, payload);
    state.statusById.set(documentId, { ...(status ?? {}), sow: true });
    showToast('Process steps ready.');
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to process steps.';
    state.sowUi.errorMessage = message;
    showToast(message, 'error');
  } finally {
    state.sowUi.running = false;
    renderSowPanel();
  }
}

function exportStepsAsJson() {
  const steps = currentSteps();
  if (!steps.length) return;
  downloadBlob('process-steps.json', JSON.stringify(steps, null, 2));
}

function exportStepsAsCsv() {
  const steps = currentSteps();
  if (!steps.length) return;
  const rows = steps.map((step) => ({
    order: step.order,
    label: step.label ?? '',
    phase: step.phase ?? '',
    title: step.title,
    description: step.description,
    source_page_start: step.source_page_start ?? '',
    source_page_end: step.source_page_end ?? '',
    source_section_title: step.source_section_title ?? '',
  }));
  downloadBlob('process-steps.csv', toCsv(rows) || '', 'text/csv');
}

async function handleUploads(files) {
  for (const file of files) {
    const tracker = createUploadTracker(elements.uploadProgress, file.name);
    try {
      await uploadDocument(file, (value) => tracker.updateProgress(value));
      tracker.markComplete();
    } catch (error) {
      console.error('Upload failed', error);
      tracker.markError('Failed');
      showToast(`Upload failed for ${file.name}`, 'error');
    }
  }
  await refreshDocuments({ selectFirst: true });
}

function bindEvents() {
  initDropZone({
    zone: elements.dropZone,
    input: elements.fileInput,
    browseButton: elements.browseButton,
    onFiles: (files) => handleUploads(files),
  });

  elements.refreshDocuments?.addEventListener('click', () => refreshDocuments());

  elements.documentsList?.addEventListener('click', (event) => {
    const option = event.target?.closest?.('.document-item');
    if (!option) return;
    selectDocument(Number(option.dataset.documentId));
  });

  elements.documentsList?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      const option = event.target?.closest?.('.document-item');
      if (!option) return;
      event.preventDefault();
      selectDocument(Number(option.dataset.documentId));
    }
  });

  elements.processButton?.addEventListener('click', () => handleProcessSteps());
  elements.sowExportJson?.addEventListener('click', exportStepsAsJson);
  elements.sowExportCsv?.addEventListener('click', exportStepsAsCsv);
}

bindEvents();
refreshDocuments({ selectFirst: true });
