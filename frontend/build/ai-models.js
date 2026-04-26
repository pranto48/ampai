import React from 'https://esm.sh/react@18.3.1';
import { createRoot } from 'https://esm.sh/react-dom@18.3.1/client';
import { renderPageShell } from './page-shell.js';

const rootEl = document.getElementById('root');
if (rootEl) {
  createRoot(rootEl).render(renderPageShell({
    title: 'AmpAI AI Models',
    description: 'Model page rendered from frontend/build/ai-models.js',
    spaRoute: '/index.html#/models'
  }));
}
