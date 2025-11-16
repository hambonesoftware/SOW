import {
  listDocuments,
  uploadDocument,
  parseDocument,
  fetchHeaders,
  fetchCachedHeaders,
  fetchDocumentStatus,
  fetchSectionText,
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
  renderHeaderRawResponse,
  renderHeaderOutline,
  showToast,
} from './ui.js';

function createDefaultSowUiState() {
  return {
    loading: false,
    running: false,
    search: '',
    phase: '',
    actor: '',
    errorMessage: null,
  };
}

const state = {
  documents: [],
  selectedId: null,
  parse: null,
  headers: null,
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
  headersContent: document.querySelector('#headers-content'),
  headersRawContent: document.querySelector('#headers-raw-content'),
  headerModeTag: document.querySelector('#header-mode-tag'),
  refreshHeaders: document.querySelector('#refresh-headers'),
  sowContent: document.querySelector('#sow-content'),
  sowExportCsv: document.querySelector('[data-export="sow-csv"]'),
  sowExportJson: document.querySelector('[data-export="sow-json"]'),
};

function setSowExportAvailability(enabled) {
  [elements.sowExportCsv, elements.sowExportJson].forEach((button) => {
    if (!button) return;
    button.disabled = !enabled;
  });
}

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
      state.sowUi = createDefaultSowUiState();
      renderSowPanel();
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
  const numericId = Number(documentId);
  if (!Number.isFinite(numericId)) {
    return;
  }
  if (state.selectedId === numericId) {
    return;
  }
  state.selectedId = numericId;
  state.parse = null;
  state.headers = null;
  state.sowUi = createDefaultSowUiState();
  renderDocumentList(elements.documentsList, state.documents, state.selectedId);
  const doc = currentDocument();
  setDocumentMeta(elements.documentMeta, doc);
  if (elements.workspaceSubtitle) {
    elements.workspaceSubtitle.textContent = doc ? `Viewing ${doc.filename}` : 'Select a document to begin.';
  }
  renderSowPanel();
  setPanelLoading(elements.parseContent, 'Loading parse summary…');
  setPanelLoading(elements.headersContent, 'Loading header outline…');
  setPanelLoading(elements.headersRawContent, 'Loading raw response…');
  if (elements.headerModeTag) {
    elements.headerModeTag.hidden = true;
  }
  try {
    await ensureParse(numericId);
  } catch (error) {
    console.error('Parse request failed', error);
    setPanelError(elements.parseContent, 'Unable to parse document.');
  }
  try {
    await ensureHeaders(numericId);
  } catch (error) {
    console.error('Header detection failed', error);
    setPanelError(elements.headersContent, 'Unable to load headers.');
    setPanelError(elements.headersRawContent, 'Unable to load raw response.');
  }
  try {
    await hydrateSowIfAvailable(numericId);
  } catch (error) {
    console.warn('Unable to load existing SOW run', error);
  }
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
    return state.parse;
  }
  const payload = await parseDocument(documentId);
  state.parse = payload;
  const nextStatus = { ...(status ?? {}), parsed: true };
  state.statusById.set(documentId, nextStatus);
  if (state.selectedId === documentId) {
    renderSowPanel();
  }
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
  if (state.selectedId === documentId) {
    renderSowPanel();
  }
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

async function hydrateSowIfAvailable(documentId) {
  const status = await ensureStatus(documentId);
  if (!status?.sow) {
    state.sowById.delete(documentId);
    if (state.selectedId === documentId) {
      renderSowPanel();
    }
    return null;
  }
  return loadSow(documentId);
}

async function loadSow(documentId, { silent = false } = {}) {
  const isActive = () => state.selectedId === documentId;
  if (isActive() && !silent) {
    state.sowUi.loading = true;
    renderSowPanel();
  }
  try {
    const payload = await fetchSowRun(documentId);
    state.sowById.set(documentId, payload);
    if (isActive()) {
      state.sowUi.errorMessage = null;
    }
    return payload;
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unable to load SOW steps.';
    if (/404/.test(message)) {
      const previous = state.statusById.get(documentId) ?? {};
      state.statusById.set(documentId, { ...previous, sow: false });
      state.sowById.delete(documentId);
      if (isActive()) {
        state.sowUi.errorMessage = null;
      }
      return null;
    }
    console.error('Failed to load SOW run', error);
    if (isActive()) {
      state.sowUi.errorMessage = message;
    }
    showToast(message, 'error');
    return null;
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

  if (!state.selectedId) {
    container.innerHTML = '<p class="panel-status">Select a document to load SOW steps.</p>';
    return;
  }

  if (state.sowUi.loading) {
    setPanelLoading(container, 'Loading SOW steps…');
    return;
  }

  const status = state.statusById.get(state.selectedId);
  if (!status) {
    setPanelLoading(container, 'Checking document status…');
    return;
  }

  if (status.sow) {
    const payload = state.sowById.get(state.selectedId);
    if (!payload) {
      if (state.sowUi.errorMessage) {
        renderSowLoadErrorState(container, state.sowUi.errorMessage);
      } else {
        setPanelLoading(container, 'Loading SOW steps…');
      }
      return;
    }
    renderSowResults(container, payload);
    return;
  }

  renderSowCallToAction(container, status);
}

function renderSowCallToAction(container, status) {
  container.innerHTML = '';
  container.append(buildSowHelpText());
  if (state.sowUi.errorMessage) {
    const error = document.createElement('p');
    error.className = 'panel-error';
    error.textContent = state.sowUi.errorMessage;
    container.append(error);
  }
  const prerequisitesMet = Boolean(status.parsed && status.headers);
  const message = document.createElement('p');
  message.className = prerequisitesMet ? 'panel-status' : 'panel-status panel-status--warning';
  message.textContent = prerequisitesMet
    ? 'No SOW extraction has been run for this document.'
    : 'SOW extraction is available after parsing and header alignment. Please run headers first.';
  container.append(message);

  const actions = document.createElement('div');
  actions.className = 'sow-actions';
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'primary-button';
  button.dataset.sowAction = 'extract';
  if (!prerequisitesMet || state.sowUi.running) {
    button.disabled = true;
  }
  if (!prerequisitesMet) {
    button.textContent = 'Awaiting headers';
  } else if (state.sowUi.running) {
    button.textContent = 'Extracting…';
  } else {
    button.textContent = 'Extract SOW steps';
  }
  actions.append(button);
  container.append(actions);
}

function renderSowLoadErrorState(container, message) {
  container.innerHTML = '';
  container.append(buildSowHelpText());
  const error = document.createElement('p');
  error.className = 'panel-error';
  error.textContent = message;
  container.append(error);
  const hint = document.createElement('p');
  hint.className = 'panel-status';
  hint.textContent = 'The previous SOW run exists but could not be loaded. Try again below.';
  container.append(hint);
  const actions = document.createElement('div');
  actions.className = 'sow-actions';
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'ghost-button';
  button.dataset.sowAction = 'reload';
  button.textContent = 'Reload SOW data';
  actions.append(button);
  container.append(actions);
}

function renderSowResults(container, payload) {
  container.innerHTML = '';
  container.append(buildSowHelpText());
  const steps = Array.isArray(payload?.steps) ? payload.steps : [];
  const summary = document.createElement('p');
  summary.className = 'panel-status sow-summary';
  const count = `${steps.length} step${steps.length === 1 ? '' : 's'} extracted`;
  const runLabel = formatSowRunTimestamp(payload?.meta);
  summary.textContent = runLabel ? `${count} • ${runLabel}` : count;
  container.append(summary);
  container.append(buildSowControls(steps));
  const filteredSteps = applySowFilters(steps);
  if (!filteredSteps.length) {
    const empty = document.createElement('p');
    empty.className = 'sow-empty-state';
    empty.textContent = 'No steps match the current filters.';
    container.append(empty);
  } else {
    const wrapper = document.createElement('div');
    wrapper.className = 'sow-table-wrapper';
    wrapper.append(buildSowTable(filteredSteps, { sectionLookup: buildSectionLookup() }));
    container.append(wrapper);
  }
  setSowExportAvailability(Boolean(steps.length));
}

function buildSowHelpText() {
  const help = document.createElement('p');
  help.className = 'sow-help-text';
  help.textContent =
    'These steps describe the end-to-end industrial process implied by this scope of work. Each row is a single actionable step.';
  return help;
}

function buildSowControls(steps) {
  const controls = document.createElement('div');
  controls.className = 'sow-controls';
  const searchGroup = document.createElement('label');
  searchGroup.className = 'sow-filter-group';
  const searchLabel = document.createElement('span');
  searchLabel.textContent = 'Search';
  const searchInput = document.createElement('input');
  searchInput.type = 'search';
  searchInput.id = 'sow-search';
  searchInput.placeholder = 'Search title or description…';
  searchInput.value = state.sowUi.search;
  searchInput.addEventListener('input', handleSowSearchInput);
  searchGroup.append(searchLabel, searchInput);
  controls.append(searchGroup);

  controls.append(
    buildFilterSelect({
      label: 'Phase',
      id: 'sow-phase-filter',
      filterKey: 'phase',
      placeholder: 'All phases',
      options: uniqueFilterValues(steps, 'phase'),
    }),
  );
  controls.append(
    buildFilterSelect({
      label: 'Actor',
      id: 'sow-actor-filter',
      filterKey: 'actor',
      placeholder: 'All actors',
      options: uniqueFilterValues(steps, 'actor'),
    }),
  );
  return controls;
}

function buildFilterSelect({ label, id, filterKey, placeholder, options }) {
  const group = document.createElement('label');
  group.className = 'sow-filter-group';
  const text = document.createElement('span');
  text.textContent = label;
  const select = document.createElement('select');
  select.id = id;
  select.dataset.filter = filterKey;
  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = placeholder;
  select.append(defaultOption);
  options.forEach((value) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
  select.value = state.sowUi[filterKey] ?? '';
  select.addEventListener('change', handleSowFilterChange);
  group.append(text, select);
  return group;
}

function uniqueFilterValues(steps, key) {
  const values = new Set();
  steps.forEach((step) => {
    const value = normaliseSowValue(step?.[key]);
    if (value) {
      values.add(value);
    }
  });
  return Array.from(values).sort((a, b) => a.localeCompare(b));
}

function applySowFilters(steps) {
  const term = state.sowUi.search.trim().toLowerCase();
  const phaseFilter = state.sowUi.phase;
  const actorFilter = state.sowUi.actor;
  return steps.filter((step) => {
    const phase = normaliseSowValue(step?.phase);
    const actor = normaliseSowValue(step?.actor);
    if (phaseFilter && phase !== phaseFilter) {
      return false;
    }
    if (actorFilter && actor !== actorFilter) {
      return false;
    }
    if (!term) {
      return true;
    }
    const title = String(step?.title ?? '').toLowerCase();
    const description = String(step?.description ?? '').toLowerCase();
    return title.includes(term) || description.includes(term);
  });
}

function buildSowTable(steps, { sectionLookup = new Map() } = {}) {
  const table = document.createElement('table');
  table.className = 'sow-table';
  const head = document.createElement('thead');
  head.innerHTML = `
    <tr>
      <th>#</th>
      <th>Phase</th>
      <th>Title & description</th>
      <th>Actor</th>
      <th>Location</th>
      <th>Inputs</th>
      <th>Outputs</th>
      <th>Depends on</th>
      <th>Section</th>
      <th>Pages</th>
    </tr>
  `;
  table.append(head);
  const body = document.createElement('tbody');
  steps.forEach((step) => {
    const row = document.createElement('tr');
    const orderCell = document.createElement('td');
    if (Number.isFinite(step?.orderIndex)) {
      orderCell.textContent = String(step.orderIndex);
    } else if (step?.stepId) {
      orderCell.textContent = String(step.stepId);
    } else {
      orderCell.textContent = '—';
    }
    row.append(orderCell);

    const phaseCell = document.createElement('td');
    phaseCell.textContent = normaliseSowValue(step?.phase) || '—';
    row.append(phaseCell);

    const titleCell = document.createElement('td');
    const title = document.createElement('p');
    title.className = 'sow-table__title';
    title.textContent = step?.title?.trim() ? step.title.trim() : 'Untitled step';
    titleCell.append(title);
    const descriptionText = String(step?.description ?? '').trim();
    if (descriptionText && descriptionText !== title.textContent) {
      const description = document.createElement('p');
      description.className = 'sow-table__description';
      description.textContent = descriptionText;
      titleCell.append(description);
    }
    row.append(titleCell);

    const actorCell = document.createElement('td');
    actorCell.textContent = normaliseSowValue(step?.actor) || '—';
    row.append(actorCell);

    const locationCell = document.createElement('td');
    locationCell.textContent = normaliseSowValue(step?.location) || '—';
    row.append(locationCell);

    const inputsCell = document.createElement('td');
    inputsCell.textContent = formatSowField(step?.inputs);
    row.append(inputsCell);

    const outputsCell = document.createElement('td');
    outputsCell.textContent = formatSowField(step?.outputs);
    row.append(outputsCell);

    const dependenciesCell = document.createElement('td');
    dependenciesCell.textContent = formatSowField(step?.dependencies);
    row.append(dependenciesCell);

    const sectionCell = document.createElement('td');
    const sectionKey = normaliseSowValue(step?.headerSectionKey);
    const sectionLabel = sectionLookup.get(sectionKey);
    if (sectionLabel) {
      sectionCell.textContent = sectionLabel;
      if (sectionKey) {
        const keyLabel = document.createElement('span');
        keyLabel.className = 'sow-section-label';
        keyLabel.textContent = sectionKey;
        sectionCell.append(keyLabel);
      }
    } else {
      sectionCell.textContent = sectionKey || '—';
    }
    row.append(sectionCell);

    const pagesCell = document.createElement('td');
    pagesCell.textContent = formatSowPages(step);
    row.append(pagesCell);

    body.append(row);
  });
  table.append(body);
  return table;
}

function buildSectionLookup() {
  const lookup = new Map();
  const sections = Array.isArray(state.headers?.sections) ? state.headers.sections : [];
  sections.forEach((section) => {
    const key = section?.section_key || section?.sectionKey;
    if (!key) return;
    const number = section?.number || section?.section_number;
    const title = section?.title || section?.text;
    const labelParts = [];
    if (number) {
      labelParts.push(String(number));
    }
    if (title) {
      labelParts.push(String(title));
    }
    lookup.set(String(key), labelParts.join(' – ') || String(key));
  });
  return lookup;
}

function formatSowPages(step) {
  const start = Number.isFinite(step?.startPage) ? Number(step.startPage) + 1 : null;
  const end = Number.isFinite(step?.endPage) ? Number(step.endPage) + 1 : null;
  if (start && end) {
    return start === end ? `Page ${start}` : `Pages ${start}–${end}`;
  }
  if (start) {
    return `Page ${start}`;
  }
  if (end) {
    return `Page ${end}`;
  }
  return '—';
}

function formatSowField(value) {
  return value && String(value).trim() ? String(value).trim() : '—';
}

function normaliseSowValue(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function formatSowRunTimestamp(meta) {
  const timestamp = meta?.createdAt || meta?.updatedAt;
  if (!timestamp) {
    return '';
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return `Run ${date.toLocaleString()}`;
}

function buildSowCsvRows(steps, sectionLookup) {
  return steps.map((step) => {
    const sectionKey = normaliseSowValue(step?.headerSectionKey);
    return {
      order: Number.isFinite(step?.orderIndex) ? step.orderIndex : step?.stepId ?? '',
      phase: normaliseSowValue(step?.phase),
      title: String(step?.title ?? ''),
      description: String(step?.description ?? ''),
      actor: normaliseSowValue(step?.actor),
      location: normaliseSowValue(step?.location),
      inputs: String(step?.inputs ?? ''),
      outputs: String(step?.outputs ?? ''),
      dependencies: String(step?.dependencies ?? ''),
      section: sectionLookup.get(sectionKey) ?? sectionKey,
      pages: formatSowPages(step),
    };
  });
}

function handleSowActionClick(event) {
  const trigger = event.target.closest('[data-sow-action]');
  if (!trigger) {
    return;
  }
  const action = trigger.dataset.sowAction;
  if (action === 'extract') {
    runSowExtractionForSelected();
  } else if (action === 'reload' && state.selectedId) {
    loadSow(state.selectedId);
  }
}

function handleSowSearchInput(event) {
  if (event.target.id !== 'sow-search') {
    return;
  }
  state.sowUi.search = event.target.value;
  renderSowPanel();
}

function handleSowFilterChange(event) {
  const target = event.target;
  if (!target?.dataset?.filter) {
    return;
  }
  const key = target.dataset.filter;
  if (!Object.prototype.hasOwnProperty.call(state.sowUi, key)) {
    return;
  }
  state.sowUi[key] = target.value;
  renderSowPanel();
}

async function runSowExtractionForSelected({ force = false } = {}) {
  if (!state.selectedId) {
    showToast('Select a document first.', 'warning');
    return;
  }
  const status = await ensureStatus(state.selectedId);
  if (!status?.parsed || !status?.headers) {
    showToast('Parsing and headers must complete before running SOW extraction.', 'warning');
    return;
  }
  state.sowUi.running = true;
  state.sowUi.errorMessage = null;
  renderSowPanel();
  try {
    const payload = await createSowRun(state.selectedId, { force });
    state.sowById.set(state.selectedId, payload);
    state.statusById.set(state.selectedId, { ...(status ?? {}), sow: true });
    showToast('SOW extraction complete.', 'info');
  } catch (error) {
    console.error('SOW extraction failed', error);
    const message = error instanceof Error ? error.message : 'Unable to extract SOW steps.';
    state.sowUi.errorMessage = message;
    showToast(message, 'error');
  } finally {
    state.sowUi.running = false;
    state.sowUi.loading = false;
    renderSowPanel();
  }
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
  } else if (kind === 'sow-csv') {
    if (!state.selectedId) {
      showToast('Select a document first.', 'warning');
      return;
    }
    const payload = state.sowById.get(state.selectedId);
    if (!payload?.steps?.length) {
      showToast('SOW steps not ready yet.', 'warning');
      return;
    }
    const rows = buildSowCsvRows(payload.steps, buildSectionLookup());
    if (!rows.length) {
      showToast('SOW steps not ready yet.', 'warning');
      return;
    }
    downloadBlob(`sow_steps_doc-${state.selectedId}.csv`, toCsv(rows), 'text/csv');
  } else if (kind === 'sow-json') {
    if (!state.selectedId) {
      showToast('Select a document first.', 'warning');
      return;
    }
    const payload = state.sowById.get(state.selectedId);
    if (!payload) {
      showToast('SOW steps not ready yet.', 'warning');
      return;
    }
    downloadBlob(`sow_steps_doc-${state.selectedId}.json`, JSON.stringify(payload, null, 2));
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
  elements.sowContent?.addEventListener('click', handleSowActionClick);
  elements.sowContent?.addEventListener('input', handleSowSearchInput);
  elements.sowContent?.addEventListener('change', handleSowFilterChange);
  document.addEventListener('click', handleExportClick);
}

async function bootstrap() {
  wireUpload();
  wireEvents();
  renderSowPanel();
  await refreshDocuments({ selectFirst: true });
}

bootstrap();
