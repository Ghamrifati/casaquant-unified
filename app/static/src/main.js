/**
 * CasaQuant Unified v3 — Frontend entry point
 * Vanilla ES6, no build step. Served directly by FastAPI static files.
 */

const API_BASE = '/api';

async function healthCheck() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    console.log('[CasaQuant]', data);
    return data;
  } catch (e) {
    console.error('[CasaQuant] API unreachable:', e);
    return { status: 'error' };
  }
}

document.addEventListener('DOMContentLoaded', () => {
  healthCheck();
});
