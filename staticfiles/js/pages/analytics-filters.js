// [data-autosubmit] change handling now lives globally in portal/shell.js.

document.addEventListener('submit', (e) => {
  const f = e.target;
  const msg = f && f.dataset ? f.dataset.confirm : null;
  if (msg && !window.confirm(msg)) e.preventDefault();
}, true);
