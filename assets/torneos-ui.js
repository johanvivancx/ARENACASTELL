/* Una sola vista de la Copa a la vez; los apartados pausados siguen ocultos sin JavaScript. */
(() => {
  const root = document.querySelector('#mundial-campeones');
  if (!root) return;

  // Las pestañas pausadas permanecen en el HTML, pero ni el menú ni un enlace directo las activan.
  const links = [...root.querySelectorAll('[data-copa-tab]')].filter((link) => !link.hidden);
  const panels = links.map((link) => document.getElementById(link.dataset.copaTab));
  if (panels.some((panel) => !panel)) return;

  const show = (id) => {
    if (!panels.some((panel) => panel.id === id)) return false;
    panels.forEach((panel) => { panel.hidden = panel.id !== id; });
    links.forEach((link) => {
      const active = link.dataset.copaTab === id;
      link.classList.toggle('is-active', active);
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    return true;
  };

  show(location.hash.slice(1)) || show('mundial-resultados');
  document.addEventListener('click', (event) => {
    const anchor = event.target.closest('a[href^="#mundial-"]');
    if (anchor) show(anchor.hash.slice(1));
  });
  window.addEventListener('hashchange', () => show(location.hash.slice(1)));
})();
