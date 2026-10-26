const fs = require('fs');
const path = require('path');
const { chromium } = require('C:/Users/johan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--no-sandbox'],
  });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  let html = fs.readFileSync(path.join(root, 'pages/admin.html'), 'utf8');
  html = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<link\b[^>]*rel="stylesheet"[^>]*>/gi, '');
  await page.setContent(html);
  await page.addStyleTag({ content: fs.readFileSync(path.join(root, 'assets/styles.css'), 'utf8') });
  await page.addScriptTag({ content: fs.readFileSync(path.join(root, 'assets/copa-caja-admin.js'), 'utf8') });
  await page.evaluate(async () => {
    const $ = (selector, parent = document) => parent.querySelector(selector);
    const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
    let pending = 11;
    window.CopaInscripcionesAdmin = () => ({ render() {} });
    window.confirm = () => true;
    const state = () => ({
      semana: '2026-10-19', hasta: '2026-10-25',
      saldos: { DISPONIBLE: 0, BAR: 0, ENTRADAS: 0, VOCALIAS: 0 }, saldo_total: 0,
      saldo_inicial_registrado: false,
      ingresos: { BAR: 0, ENTRADAS: 0, VOCALIAS: 0 }, gastos: { BAR: 0, ENTRADAS: 0, VOCALIAS: 0, GENERAL: 0 },
      caja_entregada: { BAR: 0, ENTRADAS: 0 }, dias: [], movimientos: [], partidos: [],
      vocalias: [], vocalias_pendientes_lista: [], vocalias_pendientes: 0,
      vocalias_semana: { cobrado_efectivo: 0, cobrado_transferencia: 0, cobrado_sin_desglose: 0, cobrado: 0, gastado: 0, gastado_efectivo: 0, gastado_transferencia: 0, neto: 0 },
      vocalias_general: { cobrado_efectivo: 0, cobrado_transferencia: 0, cobrado_sin_desglose: 0, cobrado: 0, gastado: 0, neto: 0 },
      vocalias_saldos: { efectivo: 0, transferencia: 0, sin_desglose: 0, movimientos_sin_desglose: 0 },
      bar_deuda_pendiente: pending,
      bar_deudores: pending ? [{ nombre: 'Johan Vivanco', pendiente: pending, deudas: 2 }] : [],
      bar_deudas: [
        { id: 2, fecha: '2026-10-25', nombre: 'Johan Vivanco', concepto: 'Comida', monto: 5, abonado: 0, pendiente: 5, registrado_por_nombre: 'Admin', cobrada_en: null },
        { id: 1, fecha: '2026-10-24', nombre: 'Johan Vivanco', concepto: 'Bebidas', monto: 6, abonado: 0, pendiente: pending - 5, registrado_por_nombre: 'Admin', cobrada_en: null },
      ],
      bar_abonos: [],
    });
    const api = async (url, data) => {
      if (url === '/admin/copa-bar-deudas/abonos') {
        window.__payment = data;
        pending -= Number(data.monto);
        return { message: 'Abono registrado.' };
      }
      return state();
    };
    const bindForm = (selector, handler) => $(selector).addEventListener('submit', async (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(event.currentTarget));
      await handler(values);
    });
    await window.CopaCajaAdmin({
      $, $$, api, bindForm,
      esc: (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char])),
      money: (value) => `$${Number(value).toFixed(2).replace('.', ',')}`,
      dates: (value) => value,
      showMessage() {}, today: '2026-10-25', canResetVocalias: false,
    });
    $('[data-copa-area="BAR"]').click();
    let visible = $('#admin-copa-caja');
    while (visible) { visible.hidden = false; visible = visible.parentElement; }
  });
  const before = await page.evaluate(() => ({
    total: document.querySelector('#copa-bar-deuda-total').textContent,
    formCount: document.querySelectorAll('.copa-form-disclosure').length,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }));
  if (before.total !== 'TOTAL DEUDAS: $11,00' || before.formCount !== 12 || before.overflow) {
    throw new Error(`Vista inicial incorrecta: ${JSON.stringify(before)}`);
  }
  await page.screenshot({ path: path.resolve(root, '..', '..', 'output', 'bar-abonos-mobile.png'), fullPage: true });
  await page.locator('[data-bar-debtor-pay]').click();
  await page.screenshot({ path: path.resolve(root, '..', '..', 'output', 'bar-abonos-mobile-abierto.png'), fullPage: true });
  await page.locator('#caja-bar-abono-monto').fill('4');
  await page.locator('#caja-bar-abono-form button[type="submit"]').click();
  await page.waitForFunction(() => document.querySelector('#copa-bar-deuda-total').textContent === 'TOTAL DEUDAS: $7,00');
  const after = await page.evaluate(() => ({
    payment: window.__payment,
    total: document.querySelector('#copa-bar-deuda-total').textContent,
    paymentClosed: !document.querySelector('#caja-bar-abono-form').closest('details').open,
  }));
  if (after.payment.nombre !== 'Johan Vivanco' || after.payment.monto !== '4' || !after.paymentClosed) {
    throw new Error(`Registro de abono incorrecto: ${JSON.stringify(after)}`);
  }
  const responsive = [];
  for (const viewport of [{ width: 375, height: 812 }, { width: 844, height: 390 }]) {
    await page.setViewportSize(viewport);
    responsive.push({ ...viewport, overflow: await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth) });
  }
  if (responsive.some((view) => view.overflow)) throw new Error(`Desbordamiento adaptable: ${JSON.stringify(responsive)}`);
  console.log(JSON.stringify({ before, after, responsive }));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
