const DATE_OPTIONS = {
  dateStyle: 'medium',
  timeStyle: 'short',
};

export function initDropZone({ zone, input, browseButton, onFiles }) {
  if (!zone) return;

  const handleFiles = (fileList) => {
    const files = Array.from(fileList ?? []).filter((file) =>
      file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'),
    );
    if (!files.length) {
      showToast('Select at least one PDF file.', 'error');
      return;
    }
    onFiles?.(files);
  };

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
    });
  });

  zone.addEventListener('dragover', () => zone.classList.add('is-dragging'));
  zone.addEventListener('dragleave', () => zone.classList.remove('is-dragging'));
  zone.addEventListener('drop', (event) => {
    zone.classList.remove('is-dragging');
    const files = event.dataTransfer?.files;
    if (files?.length) {
      handleFiles(files);
    }
  });

  zone.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      input?.click();
    }
  });

  browseButton?.addEventListener('click', () => input?.click());
  input?.addEventListener('change', (event) => {
    const files = event.target?.files;
    if (files?.length) {
      handleFiles(files);
      event.target.value = '';
    }
  });
}

export function createUploadTracker(list, filename) {
  const item = document.createElement('li');
  const name = document.createElement('span');
  name.textContent = filename;
  name.style.flex = '1 1 auto';
  const progress = document.createElement('progress');
  progress.max = 100;
  progress.value = 0;
  const status = document.createElement('span');
  status.textContent = 'Starting…';

  item.append(name, progress, status);
  list?.prepend(item);

  return {
    updateProgress(value) {
      progress.value = value;
    },
    markComplete(text = 'Uploaded') {
      progress.value = 100;
      status.textContent = text;
    },
    markError(message) {
      progress.classList.add('upload-error');
      status.textContent = message;
    },
  };
}

export function renderDocumentList(container, documents, selectedId) {
  if (!container) return;
  container.innerHTML = '';

  if (!Array.isArray(documents) || !documents.length) {
    container.dataset.empty = 'true';
    return;
  }

  container.dataset.empty = 'false';

  documents.forEach((doc) => {
    const option = document.createElement('div');
    option.className = 'document-item';
    option.id = `document-${doc.id}`;
    option.setAttribute('role', 'option');
    option.tabIndex = -1;
    option.dataset.documentId = String(doc.id);
    if (doc.id === selectedId) {
      option.setAttribute('aria-selected', 'true');
      option.tabIndex = 0;
    } else {
      option.setAttribute('aria-selected', 'false');
    }

    const name = document.createElement('p');
    name.className = 'document-item__name';
    name.textContent = doc.filename;

    const meta = document.createElement('div');
    meta.className = 'document-item__meta';
    const status = document.createElement('span');
    status.textContent = doc.status ?? 'uploaded';
    const uploaded = document.createElement('span');
    uploaded.textContent = formatDate(doc.uploaded_at);
    meta.append(status, uploaded);

    option.append(name, meta);
    container.append(option);
  });
}

export function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString(undefined, DATE_OPTIONS);
}

export function setDocumentMeta(container, documentRecord) {
  if (!container) return;
  if (!documentRecord) {
    container.innerHTML = '<p class="panel-status">No document selected.</p>';
    return;
  }

  container.innerHTML = '';
  const id = document.createElement('span');
  id.textContent = `ID: ${documentRecord.id}`;
  const status = document.createElement('span');
  status.textContent = `Status: ${documentRecord.status}`;
  const uploaded = document.createElement('span');
  uploaded.textContent = `Uploaded: ${formatDate(documentRecord.uploaded_at)}`;
  container.append(id, status, uploaded);
}

export function setPanelLoading(container, message = 'Loading…') {
  if (!container) return;
  container.innerHTML = `<p class="panel-status">${message}</p>`;
}

export function setPanelError(container, message) {
  if (!container) return;
  container.innerHTML = `<p class="panel-error">${message}</p>`;
}

export function renderParseSummary(container, payload) {
  if (!container) return;
  if (!payload) {
    setPanelError(container, 'Parse data unavailable.');
    return;
  }

  const pages = Array.isArray(payload.pages) ? payload.pages : [];
  const totalBlocks = pages.reduce((acc, page) => acc + (page.blocks?.length ?? 0), 0);
  const totalTables = pages.reduce((acc, page) => acc + (page.tables?.length ?? 0), 0);

  const stats = [
    { label: 'Pages', value: pages.length },
    { label: 'Text blocks', value: totalBlocks },
    { label: 'Tables', value: totalTables },
    { label: 'OCR used', value: payload.has_ocr ? 'Yes' : 'No' },
    { label: 'MinerU fallback', value: payload.used_mineru ? 'Yes' : 'No' },
  ];

  const grid = document.createElement('div');
  grid.className = 'parse-grid';
  stats.forEach((stat) => {
    const card = document.createElement('div');
    card.className = 'parse-stat';
    const title = document.createElement('strong');
    title.textContent = stat.label;
    const value = document.createElement('span');
    value.textContent = String(stat.value);
    card.append(title, value);
    grid.append(card);
  });

  container.innerHTML = '';
  container.append(grid);
}

export function renderProcessSteps(container, steps) {
  if (!container) return;
  container.innerHTML = '';

  if (!Array.isArray(steps) || !steps.length) {
    const empty = document.createElement('p');
    empty.className = 'panel-status';
    empty.textContent = 'No process steps available yet.';
    container.append(empty);
    return;
  }

  const list = document.createElement('ol');
  list.className = 'process-step-list';

  steps.forEach((step) => {
    const item = document.createElement('li');
    item.className = 'process-step';

    const header = document.createElement('div');
    header.className = 'process-step__header';
    const orderBadge = document.createElement('span');
    orderBadge.className = 'process-step__order';
    orderBadge.textContent = `#${step.order}`;
    header.append(orderBadge);

    if (step.phase) {
      const phase = document.createElement('span');
      phase.className = 'process-step__phase';
      phase.textContent = step.phase;
      header.append(phase);
    }

    if (step.label) {
      const label = document.createElement('span');
      label.className = 'process-step__label';
      label.textContent = step.label;
      header.append(label);
    }

    const title = document.createElement('h4');
    title.className = 'process-step__title';
    title.textContent = step.title;

    const description = document.createElement('p');
    description.className = 'process-step__description';
    description.textContent = step.description;

    const footer = document.createElement('div');
    footer.className = 'process-step__footer';
    if (step.source_section_title) {
      const section = document.createElement('span');
      section.textContent = step.source_section_title;
      footer.append(section);
    }
    if (step.source_page_start || step.source_page_end) {
      const pages = document.createElement('span');
      const start = step.source_page_start ?? step.source_page_end;
      const end = step.source_page_end ?? step.source_page_start;
      pages.textContent = start === end ? `p.${start}` : `p.${start}-${end}`;
      footer.append(pages);
    }

    item.append(header, title, description);
    if (footer.childElementCount) {
      item.append(footer);
    }
    list.append(item);
  });

  container.append(list);
}

export function showToast(message, variant = 'info', timeout = 3500) {
  const region = document.getElementById('toast-region');
  if (!region) return;
  const toast = document.createElement('div');
  toast.className = `toast toast--${variant}`;
  toast.textContent = message;
  region.append(toast);
  setTimeout(() => {
    toast.classList.add('toast--hide');
    toast.addEventListener('transitionend', () => toast.remove(), { once: true });
  }, timeout);
}

