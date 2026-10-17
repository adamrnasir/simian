// Apply the saved theme before styles load to avoid a flash on navigation.
(() => {
  const preference = window.matchMedia('(prefers-color-scheme: dark)');
  let savedTheme;
  try { savedTheme = localStorage.getItem('theme'); } catch {}
  if (savedTheme !== 'light' && savedTheme !== 'dark') savedTheme = null;

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#080909' : '#f5f4f0';
    const button = document.querySelector('.theme-toggle');
    if (button) button.setAttribute('aria-pressed', String(theme === 'dark'));
  }

  applyTheme(savedTheme || (preference.matches ? 'dark' : 'light'));
  preference.addEventListener('change', event => {
    if (!savedTheme) applyTheme(event.matches ? 'dark' : 'light');
  });
  // Delegated so the button works as soon as it is parsed; it stays visible
  // across navigation instead of waiting for the deferred scripts.
  document.addEventListener('click', event => {
    if (!event.target.closest?.('.theme-toggle')) return;
    savedTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(savedTheme);
    try { localStorage.setItem('theme', savedTheme); } catch {}
  });
  document.addEventListener('DOMContentLoaded', () => {
    const button = document.querySelector('.theme-toggle');
    button.hidden = false;
    button.setAttribute('aria-pressed', String(document.documentElement.dataset.theme === 'dark'));
  });
})();
