import {
  listDocuments,
  uploadDocument,
  parseDocument,
  fetchHeaders,
  fetchCachedHeaders,
  fetchDocumentStatus,
  fetchSectionText,
  downloadBlob,
} from './api.js';
import {
  initDropZone,
  createUploadTracker,
  renderDocumentList,
  setDocumentMeta,
  setPanelLoading,
  setPanelError,
  renderParseSummary,
  renderHeaderRawResponse,
  renderHeaderOutline,
  showToast,
} from './ui.js';

const state = {
  documents: [],
  selectedId: null,
  parse: null,
  headers: null,
  statusById: new Map(),
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
  headersContent: document.querySelector('#headers-content'),
  headersRawContent: document.querySelector('#headers-raw-content'),
  headerModeTag: document.querySelector('#header-mode-tag'),
  refreshHeaders: document.querySelector('#refresh-headers'),
};

function setDocumentsStatus(message) {
  if (elements.documentsStatus) {
    elements.documentsStatus.textContent = message;
  }
}

function currentDocument() {
  return state.documents.find((doc) => doc.id === state.selectedId) ?? null;
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
    }
    renderDocumentList(elements.documentsList, documents, state.selectedId);
    if (selectFirst && documents.length) {
      await selectDocument(documents[0].id);
    }
  } catch (error) {
    console.error('Failed to list documents', error);
    setDocumentsStatus('Unable to load documents.');
  }
}

async function selectDocument(documentId) {
  if (!Number.isFinite(Number(documentId))) {
    return;
  }
  if (state.selectedId === documentId) {
    return;
  }
  state.selectedId = documentId;
  state.parse = null;
  state.headers = null;
  renderDocumentList(elements.documentsList, state.documents, state.selectedId);
  const doc = currentDocument();
  setDocumentMeta(elements.documentMeta, doc);
  if (elements.workspaceSubtitle) {
    elements.workspaceSubtitle.textContent = doc ? `Viewing ${doc.filename}` : 'Select a document to begin.';
  }
  setPanelLoading(elements.parseContent, 'Loading parse summary…');
  setPanelLoading(elements.headersContent, 'Loading header outline…');
  setPanelLoading(elements.headersRawContent, 'Loading raw response…');
  if (elements.headerModeTag) {
    elements.headerModeTag.hidden = true;
  }
  try {
    await ensureParse(documentId);
  } catch (error) {
    console.error('Parse request failed', error);
    setPanelError(elements.parseContent, 'Unable to parse document.');
  }
  try {
    await ensureHeaders(documentId);
  } catch (error) {
    console.error('Header detection failed', error);
    setPanelError(elements.headersContent, 'Unable to load headers.');
    setPanelError(elements.headersRawContent, 'Unable to load raw response.');
  }
}

async function ensureStatus(documentId) {
  if (state.statusById.has(documentId)) {
    return state.statusById.get(documentId);
  }
  try {
    const status = await fetchDocumentStatus(documentId);
    state.statusById.set(documentId, status);
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
    return state.parse;
  }
  const payload = await parseDocument(documentId);
  state.parse = payload;
  const nextStatus = { ...(status ?? {}), parsed: true };
  state.statusById.set(documentId, nextStatus);
  renderParseSummary(elements.parseContent, payload);
  return payload;
}

async function ensureHeaders(documentId, { force = false } = {}) {
  let payload = null;
  if (!force) {
    try {
      payload = await fetchCachedHeaders(documentId);
    } catch (error) {
      console.info('No cached headers available', error);
    }
  }
  if (!payload) {
    payload = await fetchHeaders(documentId, { force });
  }
  state.headers = payload;
  const status = state.statusById.get(documentId) ?? {};
  state.statusById.set(documentId, { ...status, headers: true });
  updateHeaderViews(payload);
  return payload;
}

function updateHeaderViews(payload) {
  if (!payload) {
    setPanelError(elements.headersContent, 'No headers detected.');
    setPanelError(elements.headersRawContent, 'No raw response available.');
    return;
  }
  const mode = payload.mode || payload.meta?.mode || null;
  if (elements.headerModeTag) {
    if (mode) {
      elements.headerModeTag.textContent = mode;
      elements.headerModeTag.hidden = false;
    } else {
      elements.headerModeTag.hidden = true;
    }
  }
  renderHeaderOutline(elements.headersContent, payload, {
    documentId: state.selectedId,
    fetchSection: fetchSectionText,
  });
  renderHeaderRawResponse(elements.headersRawContent, payload);
}

function handleDocumentListClick(event) {
  const target = event.target.closest('.document-item');
  if (!target) {
    return;
  }
  const documentId = Number(target.dataset.documentId);
  if (Number.isFinite(documentId)) {
    selectDocument(documentId);
  }
}

function handleExportClick(event) {
  const trigger = event.target.closest('[data-export]');
  if (!trigger) {
    return;
  }
  const kind = trigger.dataset.export;
  if (kind === 'parse') {
    if (!state.parse) {
      showToast('Parse data unavailable.', 'warning');
      return;
    }
    downloadBlob('parse.json', JSON.stringify(state.parse, null, 2));
  } else if (kind === 'headers') {
    if (!state.headers) {
      showToast('Headers not ready yet.', 'warning');
      return;
    }
    downloadBlob('headers.json', JSON.stringify(state.headers, null, 2));
  }
}

function wireUpload() {
  if (!elements.dropZone) {
    return;
  }
  initDropZone({
    zone: elements.dropZone,
    input: elements.fileInput,
    browseButton: elements.browseButton,
    onFiles: (files) => {
      files.forEach(uploadFile);
    },
  });
}

async function uploadFile(file) {
  const tracker = createUploadTracker(elements.uploadProgress, file.name);
  try {
    await uploadDocument(file, (progress) => tracker.updateProgress(progress));
    tracker.markComplete('Uploaded');
    await refreshDocuments({ selectFirst: !state.selectedId });
    showToast(`Uploaded ${file.name}`, 'info');
  } catch (error) {
    console.error('Upload failed', error);
    tracker.markError('Failed');
    showToast(`Upload failed for ${file.name}`, 'error');
  }
}

function wireEvents() {
  elements.documentsList?.addEventListener('click', handleDocumentListClick);
  elements.refreshDocuments?.addEventListener('click', () => refreshDocuments({ selectFirst: false }));
  elements.refreshHeaders?.addEventListener('click', async () => {
    if (!state.selectedId) {
      showToast('Select a document first.', 'warning');
      return;
    }
    setPanelLoading(elements.headersContent, 'Detecting headers…');
    setPanelLoading(elements.headersRawContent, 'Requesting raw response…');
    try {
      await ensureHeaders(state.selectedId, { force: true });
      showToast('Header detection complete.', 'info');
    } catch (error) {
      console.error('Unable to refresh headers', error);
      setPanelError(elements.headersContent, 'Unable to refresh headers.');
      setPanelError(elements.headersRawContent, 'Unable to refresh headers.');
    }
  });
  document.addEventListener('click', handleExportClick);
}

async function bootstrap() {
  wireUpload();
  wireEvents();
  await refreshDocuments({ selectFirst: true });
}

bootstrap();
