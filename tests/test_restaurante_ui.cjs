const fs = require('fs');
const path = require('path');
const { chromium } = require('C:/Users/johan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  let html = fs.readFileSync(path.join(root, 'pages/admin.html'), 'utf8');
  html = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<link\b[^>]*rel="stylesheet"[^>]*>/gi, '');
  html = html.replace('../assets/asadero-bj-logo.jpg', `data:image/jpeg;base64,${fs.readFileSync(path.join(root, 'assets/asadero-bj-logo.jpg')).toString('base64')}`);
  await page.setContent(html);
  await page.addStyleTag({ content: fs.readFileSync(path.join(root, 'assets/styles.css'), 'utf8') });
  await page.addStyleTag({ content: fs.readFileSync(path.join(root, 'assets/admin-sidebar.css'), 'utf8') });
  await page.addScriptTag({ content: fs.readFileSync(path.join(root, 'assets/restaurante-admin.js'), 'utf8') });
  await page.evaluate(async () => {
    const $ = (selector, parent = document) => parent.querySelector(selector);
    const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
    let pending = 13;
    window.confirm = () => true;
    const state = () => ({
      total_deudas: pending, cobrado_efectivo: 3, cobrado_transferencia: 2,
      deudores: pending ? [{ nombre: 'Johan Vivanco', pendiente: pending, deudas: 2 }] : [],
      deudas: [{ id: 1, fecha: '2026-10-25', nombre: 'Johan Vivanco', concepto: 'Almuerzo', monto: 13, abonado: 0, pendiente: pending, registrado_por_nombre: 'Admin' }],
      abonos: [],
    });
    const api = async (url, data) => {
      if (url === '/admin/restaurante-deudas/abonos') { window.__abono = data; pending -= Number(data.monto); return { message: 'Abono registrado.' }; }
      return state();
    };
    const bindForm = (selector, handler) => $(selector).addEventListener('submit', async (event) => {
      event.preventDefault();
      await handler(Object.fromEntries(new FormData(event.currentTarget)));
    });
    await window.RestauranteAdmin({ $, $$, api, bindForm,
      esc: (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char])),
      money: (value) => `$${Number(value).toFixed(2).replace('.', ',')}`, dates: (value) => value,
      showMessage() {}, today: '2026-10-26' });
    let visible = $('#admin-restaurante');
    while (visible) { visible.hidden = false; visible = visible.parentElement; }
  });
  const before = await page.evaluate(() => ({
    total: document.querySelector('#restaurante-total-pie').textContent,
    formsClosed: [...document.querySelectorAll('.restaurant-form-card')].every((item) => !item.open),
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }));
  if (before.total !== 'TOTAL DEUDAS: $13,00' || !before.formsClosed || before.overflow) throw new Error(`Vista inicial incorrecta: ${JSON.stringify(before)}`);
  await page.screenshot({ path: path.resolve(root, '..', '..', 'output', 'restaurante-deudores-mobile.png'), fullPage: true });
  await page.locator('[data-restaurante-abonar]').click();
  await page.locator('#restaurante-abono-monto').fill('4');
  await page.selectOption('#restaurante-abono-metodo', 'TRANSFERENCIA');
  await page.locator('#restaurante-abono-form button[type="submit"]').click();
  await page.waitForFunction(() => document.querySelector('#restaurante-total-pie').textContent === 'TOTAL DEUDAS: $9,00');
  const after = await page.evaluate(() => ({ abono: window.__abono, closed: !document.querySelector('#restaurante-abono-form').closest('details').open }));
  if (after.abono.metodo !== 'TRANSFERENCIA' || after.abono.monto !== '4' || !after.closed) throw new Error(`Abono incorrecto: ${JSON.stringify(after)}`);
  for (const viewport of [
    { width: 320, height: 700 }, { width: 375, height: 812 }, { width: 414, height: 896 },
    { width: 844, height: 390 }, { width: 768, height: 1024 }, { width: 1024, height: 768 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    if (overflow) throw new Error(`Desbordamiento en ${JSON.stringify(viewport)}`);
  }
  console.log(JSON.stringify({ before, after }));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
