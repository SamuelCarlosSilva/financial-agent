import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './design-system/tokens.css';
import './design-system/fonts';
import './design-system/global.css';
import { App } from './App';

const root = document.getElementById('root');
if (!root) throw new Error('Elemento #root não encontrado.');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
