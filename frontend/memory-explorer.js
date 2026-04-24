document.addEventListener('DOMContentLoaded', () => {
  const body = document.getElementById('mx-body');
  const category = document.getElementById('mx-category');
  const query = document.getElementById('mx-query');
  const scope = document.getElementById('mx-scope');
  const dateFrom = document.getElementById('mx-date-from');
  const dateTo = document.getElementById('mx-date-to');
  const applyBtn = document.getElementById('mx-apply');
  const prevBtn = document.getElementById('mx-prev');
  const nextBtn = document.getElementById('mx-next');
  const page = document.getElementById('mx-page');

  const state = { offset: 0, limit: 50, total: 0 };

  async function apiFetch(url, options = {}) {
    const token = localStorage.getItem('ampai_token') || '';
    const headers = options.headers || {};
    headers['Authorization'] = `Bearer ${token}`;
    return fetch(url, { ...options, headers });
  }

  function fmtDate(v) {
    if (!v) return '-';
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? v : d.toLocaleString();
  }

  async function load() {
    const res = await apiFetch('/api/memory/explorer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query.value.trim(),
        category: category.value,
        owner_scope: scope.value,
        date_from: dateFrom.value ? `${dateFrom.value}T00:00:00Z` : '',
        date_to: dateTo.value ? `${dateTo.value}T23:59:59Z` : '',
        limit: state.limit,
        offset: state.offset,
      }),
    });
    if (!res.ok) {
      body.innerHTML = `<tr><td colspan="6">Failed to load explorer data</td></tr>`;
      return;
    }
    const data = await res.json();
    state.total = Number(data.total || 0);

    const categories = Object.keys(data.categories || {}).sort((a, b) => a.localeCompare(b));
    const selected = category.value;
    category.innerHTML = '<option value="">All</option>' + categories.map(c => `<option value="${c}">${c} (${data.categories[c]})</option>`).join('');
    category.value = selected;

    const rows = data.sessions || [];
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="6" style="text-align:center;">No memories found</td></tr>';
    } else {
      body.innerHTML = rows.map((s) => `
        <tr>
          <td>${s.session_id}</td>
          <td>${s.category || '-'}</td>
          <td>${s.owner || '-'}</td>
          <td>${s.visibility || '-'}</td>
          <td>${fmtDate(s.updated_at)}</td>
          <td><a class="btn" style="width:auto; padding:4px 8px;" href="index.html?session=${encodeURIComponent(s.session_id)}">Open</a></td>
        </tr>
      `).join('');
    }

    const start = state.total ? (state.offset + 1) : 0;
    const end = Math.min(state.offset + state.limit, state.total);
    page.textContent = `${start}-${end} of ${state.total}`;
    prevBtn.disabled = state.offset <= 0;
    nextBtn.disabled = (state.offset + state.limit) >= state.total;
  }

  applyBtn.addEventListener('click', () => {
    state.offset = 0;
    load();
  });
  prevBtn.addEventListener('click', () => {
    state.offset = Math.max(0, state.offset - state.limit);
    load();
  });
  nextBtn.addEventListener('click', () => {
    state.offset += state.limit;
    load();
  });

  load();
});
