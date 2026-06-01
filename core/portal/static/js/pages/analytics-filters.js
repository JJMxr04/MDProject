document.addEventListener('change', (e) => {
  const el = e.target;
  if (el.matches('[data-autosubmit]') && el.form) {
    el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit();
  }
});

document.addEventListener('submit', (e) => {
  const f = e.target;
  const msg = f && f.dataset ? f.dataset.confirm : null;
  if (msg && !window.confirm(msg)) e.preventDefault();
}, true);
