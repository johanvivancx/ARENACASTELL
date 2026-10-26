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
  await page.setContent(`<!doctype html><html lang="es"><body><main id="admin-copa-caja">
    <section data-copa-panel="INSCRIPCIONES">
      <form id="copa-inscripciones-pago-form"><select id="copa-inscripciones-equipo"></select><select id="copa-inscripciones-concepto"><option value="INSCRIPCION">Inscripción</option><option value="CARNETS">Carnets</option></select><input id="copa-inscripciones-fecha" name="fecha" type="date"><input id="copa-inscripciones-efectivo" value="0"><input id="copa-inscripciones-transferencia" value="0"><output id="copa-inscripciones-total"></output><p id="copa-inscripciones-pago-aviso"></p><button type="submit">Guardar</button></form>
      <input id="copa-inscripciones-buscar"><select id="copa-inscripciones-filtro"><option value="TODOS">Todos</option></select>
      <div id="copa-inscripciones-resumen"></div><p id="copa-inscripciones-filtrado"></p><div id="copa-inscripciones-equipos"></div><div id="copa-inscripciones-historial" class="copa-ledger-scroll"></div>
    </section></main></body></html>`);
  await page.addStyleTag({ content: fs.readFileSync(path.join(root, 'assets/styles.css'), 'utf8') });
  await page.addScriptTag({ content: fs.readFileSync(path.join(root, 'assets/copa-inscripciones-admin.js'), 'utf8') });
  await page.evaluate(async () => {
    const $ = (selector, parent = document) => parent.querySelector(selector);
    const info = (agreement, previous, current) => ({ esperado: agreement ? 25 : 7, abono_inicial: previous, completo_inicial: agreement, cobrado_nuevo: current, pendiente: 0, acuerdo: agreement });
    const state = {
      equipos: [{ equipo: 'Colombia', club: 'Fruta Sí', carnets_cantidad: 14,
        nota: 'Inscripción completa por acuerdo, sin cobro. Carnets: $3 anteriores + $6,50 en efectivo el 23/10/2026; total recibido $9,50. Carnets completos.',
        inscripcion: info(true, 0, 0), carnets: info(false, 3, 6.5) }],
      pagos: [{ id: 1, fecha: '2026-10-23', equipo: 'Colombia', concepto: 'CARNETS', efectivo: 6.5, transferencia: 0, monto: 6.5, registrado_por_nombre: 'Admin', anulado_en: null }],
      pendiente_inscripciones: 0, pendiente_carnets: 0, cobrado_efectivo: 6.5, cobrado_transferencia: 0,
    };
    const module = window.CopaInscripcionesAdmin({
      $, api: async () => state, bindForm() {}, esc: (value) => String(value ?? ''),
      money: (value) => `$${Number(value).toFixed(2).replace('.', ',')}`, dates: (value) => value,
      showMessage() {}, today: '2026-10-25', closeMobileForm() {},
    });
    await module.refresh();
  });
  const result = await page.evaluate(() => ({
    card: document.querySelector('#copa-inscripciones-equipos').innerText,
    history: document.querySelector('#copa-inscripciones-historial').innerText,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }));
  if (!result.card.includes('Completo (acuerdo)') || !result.card.includes('Carnets\nCompleto') ||
      !result.card.includes('$6,50') || !result.history.includes('2026-10-23') || result.overflow) {
    throw new Error(`Estado de Colombia incorrecto: ${JSON.stringify(result)}`);
  }
  console.log(JSON.stringify(result));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
