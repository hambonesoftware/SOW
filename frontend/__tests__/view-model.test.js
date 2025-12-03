import { jest } from '@jest/globals';
import { createSpecSearchViewModel } from '../view-model.js';

describe('runSearch', () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  function buildJsonResponse(body, status = 200) {
    return {
      ok: status >= 200 && status < 300,
      status,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: jest.fn().mockResolvedValue(body),
    };
  }

  function buildTextResponse(text, status) {
    return {
      ok: status >= 200 && status < 300,
      status,
      headers: new Headers({ 'content-type': 'text/html' }),
      text: jest.fn().mockResolvedValue(text),
    };
  }

  function setSearchInputs(viewModel) {
    viewModel.setText('example spec text');
    viewModel.setBuckets(['one']);
  }

  test('successful JSON response populates results and telemetry with success status', async () => {
    const responseBody = { ok: true, data: [{ id: 1 }], meta: { latency_ms: 5 } };
    global.fetch = jest.fn().mockResolvedValue(buildJsonResponse(responseBody));

    const viewModel = createSpecSearchViewModel();
    setSearchInputs(viewModel);

    const result = await viewModel.runSearch();
    const state = viewModel.getState();

    expect(result).toEqual(responseBody);
    expect(state.results).toEqual(responseBody.data);
    expect(state.telemetry).toEqual(responseBody.meta);
    expect(state.status).toBe('Extraction complete.');
    expect(state.running).toBe(false);
  });

  test('500 response with HTML body reports a user-friendly failure', async () => {
    global.fetch = jest.fn().mockResolvedValue(buildTextResponse('<html>Server error</html>', 500));

    const viewModel = createSpecSearchViewModel();
    setSearchInputs(viewModel);

    await viewModel.runSearch();
    const state = viewModel.getState();

    expect(state.results).toBeNull();
    expect(state.telemetry).toBeNull();
    expect(state.status).toMatch(/Server error \(500\)/);
    expect(state.running).toBe(false);
  });

  test('non-JSON 400 response clears results, keeps running false, and reports error status', async () => {
    const successBody = { ok: true, data: [{ id: 'keep' }], meta: { trace_id: 'abc' } };
    const badRequestResponse = {
      ok: false,
      status: 400,
      headers: new Headers({ 'content-type': 'text/plain' }),
      text: jest.fn().mockResolvedValue('Bad request'),
    };

    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(buildJsonResponse(successBody))
      .mockResolvedValueOnce(badRequestResponse);

    const viewModel = createSpecSearchViewModel();
    setSearchInputs(viewModel);

    await viewModel.runSearch();
    setSearchInputs(viewModel);
    await viewModel.runSearch();

    const state = viewModel.getState();
    expect(state.results).toBeNull();
    expect(state.telemetry).toBeNull();
    expect(state.status).toContain('Request failed (400)');
    expect(state.running).toBe(false);
  });
});
