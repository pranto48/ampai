import React from 'https://esm.sh/react@18.3.1';

const styles = {
  body: { margin: 0, fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif', background: 'radial-gradient(circle at top, #1e1b4b 0%, #020617 60%)', color: '#e2e8f0', minHeight: '100vh' },
  shell: { minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 20 },
  card: { width: '100%', maxWidth: 520, borderRadius: 14, border: '1px solid rgba(148,163,184,.25)', background: 'rgba(15,23,42,.88)', boxShadow: '0 24px 60px rgba(0,0,0,.45)', padding: 20 },
  code: { background: '#0f172a', borderRadius: 6, padding: '2px 6px' },
  row: { display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 16 },
  link: { border: 0, borderRadius: 8, padding: '10px 12px', textDecoration: 'none', color: '#fff', background: '#4f46e5', fontWeight: 600, cursor: 'pointer' },
};

export function renderPageShell({ title, description, spaRoute }) {
  const username = localStorage.getItem('ampai_username') || 'guest';
  const role = localStorage.getItem('ampai_role') || 'user';
  return React.createElement('div', { style: styles.body },
    React.createElement('div', { style: styles.shell },
      React.createElement('div', { style: styles.card },
        React.createElement('h1', null, title),
        React.createElement('p', null, description),
        React.createElement('p', null, 'Current user: ', React.createElement('code', { style: styles.code }, username), ` (${role})`),
        React.createElement('div', { style: styles.row },
          React.createElement('a', { href: spaRoute, style: styles.link }, 'Open SPA Route'),
          React.createElement('a', { href: '/index.html', style: { ...styles.link, background: '#334155' } }, 'Open React Login')
        )
      )
    )
  );
}
