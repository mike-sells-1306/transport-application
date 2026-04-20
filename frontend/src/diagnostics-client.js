(function initDiagnosticsClient(globalScope) {
  const API_PATH = '/api/diagnostics/summary';

  async function fetchDiagnosticsSummary() {
    const response = await fetch(API_PATH, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });

    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok) {
      throw new Error(payload.error || `Diagnostics request failed (${response.status})`);
    }
    return payload;
  }

  globalScope.TransportDiagnosticsClient = {
    fetchDiagnosticsSummary,
  };
})(window);
