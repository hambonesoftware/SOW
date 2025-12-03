import { createSpecSearchViewModel } from './view-model.js';

const elements = {
  textarea: document.getElementById('spec-text'),
  runButton: document.getElementById('run-search'),
  status: document.getElementById('status'),
  results: document.getElementById('results'),
  telemetryBody: document.getElementById('telemetry-body'),
  warnings: document.getElementById('warnings'),
  documentId: document.getElementById('document-id'),
  bucketInputs: document.querySelectorAll('.bucket-list input[type="checkbox"]'),
};

const levelColors = {
  MUST: '#dc2626',
  SHOULD: '#d97706',
  MAY: '#059669',
};

function normalizeBuckets(data) {
  if (!data) return {};
  if (data.buckets) return data.buckets;
  if (data.root) return data.root;
  return data;
}

function renderBuckets(data) {
  if (!elements.results) return;
  const buckets = normalizeBuckets(data);
  elements.results.innerHTML = '';
  Object.entries(buckets).forEach(([bucket, payload]) => {
    const card = document.createElement('article');
    card.className = 'bucket-card';
    const title = document.createElement('h3');
    title.textContent = bucket.charAt(0).toUpperCase() + bucket.slice(1);
    const count = document.createElement('span');
    count.textContent = `${payload.requirements.length} reqs`;
    title.appendChild(count);
    card.appendChild(title);

    if (!payload.requirements.length) {
      const empty = document.createElement('p');
      empty.className = 'empty';
      empty.textContent = 'No requirements extracted for this bucket.';
      card.appendChild(empty);
    } else {
      const list = document.createElement('ul');
      list.className = 'requirements-list';
      payload.requirements.forEach((req) => {
        const item = document.createElement('li');
        item.className = 'requirement';

        const header = document.createElement('div');
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.style.background = levelColors[req.level] || '#e0e7ff';
        badge.textContent = req.level;
        header.appendChild(badge);

        if (req.id) {
          const id = document.createElement('span');
          id.textContent = req.id;
          id.className = 'req-id';
          header.appendChild(id);
        }

        if (req.page_hint !== null && req.page_hint !== undefined) {
          const page = document.createElement('span');
          page.textContent = `page ${req.page_hint}`;
          page.className = 'page-hint';
          header.appendChild(page);
        }

        item.appendChild(header);

        const body = document.createElement('pre');
        body.textContent = req.text;
        item.appendChild(body);
        list.appendChild(item);
      });
      card.appendChild(list);
    }

    elements.results.appendChild(card);
  });
}

function renderTelemetry(meta) {
  if (!elements.telemetryBody || !elements.warnings) return;
  elements.telemetryBody.innerHTML = '';
  elements.warnings.textContent = '';
  if (!meta) return;
  meta.attempts.forEach((attempt) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${attempt.rung}</td>
      <td>${attempt.model}</td>
      <td>${attempt.parsed ? 'yes' : 'no'}</td>
      <td>${attempt.reason}</td>
      <td>${attempt.input_tokens_est}</td>
      <td>${attempt.response_bytes}</td>
    `;
    elements.telemetryBody.appendChild(row);
  });
  if (meta.warnings && meta.warnings.length) {
    elements.warnings.textContent = meta.warnings.join(' \u2022 ');
  }
}

function collectSelectedBuckets() {
  return Array.from(elements.bucketInputs)
    .filter((input) => input.checked)
    .map((input) => input.value);
}

function createBinding(viewModel, selector, render) {
  return viewModel.subscribe((state, prevState) => {
    const next = selector(state);
    const prev = prevState ? selector(prevState) : undefined;
    if (prevState && Object.is(next, prev)) return;
    render(next, state);
  });
}

const viewModel = createSpecSearchViewModel();

createBinding(viewModel, (state) => state.status, (status) => {
  if (elements.status) {
    elements.status.textContent = status || '';
  }
});

createBinding(viewModel, (state) => state.running, (running) => {
  if (elements.runButton) {
    elements.runButton.disabled = Boolean(running);
  }
});

createBinding(viewModel, (state) => state.results, (results) => {
  renderBuckets(results);
});

createBinding(viewModel, (state) => state.telemetry, (telemetry) => {
  renderTelemetry(telemetry);
});

function bindInputs() {
  if (elements.textarea) {
    viewModel.setText(elements.textarea.value);
    elements.textarea.addEventListener('input', (event) => {
      viewModel.setText(event.target.value);
    });
  }

  if (elements.documentId) {
    viewModel.setDocumentId(elements.documentId.value || null);
    elements.documentId.addEventListener('input', (event) => {
      viewModel.setDocumentId(event.target.value || null);
    });
  }

  if (elements.bucketInputs) {
    const updateBuckets = () => viewModel.setBuckets(collectSelectedBuckets());
    updateBuckets();
    elements.bucketInputs.forEach((input) => input.addEventListener('change', updateBuckets));
  }

  if (elements.runButton) {
    elements.runButton.addEventListener('click', () => {
      const { running } = viewModel.getState();
      if (!running) {
        viewModel.runSearch();
      }
    });
  }
}

bindInputs();
