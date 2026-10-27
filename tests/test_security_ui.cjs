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
  const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
  let html = fs.readFileSync(path.join(root, 'pages/admin.html'), 'utf8');
  html = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<link\b[^>]*rel="stylesheet"[^>]*>/gi, '');
  await page.setContent(html);
  await page.addStyleTag({ content: fs.readFileSync(path.join(root, 'assets/styles.css'), 'utf8') });
  await page.addStyleTag({ content: fs.readFileSync(path.join(root, 'assets/admin-sidebar.css'), 'utf8') });
  await page.evaluate(() => {
    document.querySelector('#admin-content').hidden = false;
    document.querySelectorAll('.admin-workspace-section').forEach((section) => { section.hidden = section.id !== 'admin-seguridad'; });
    document.querySelector('#security-overall').textContent = 'Protecciones activas';
    document.querySelector('#security-date').textContent = '26 oct 2026';
    document.querySelector('#security-controls').innerHTML = [
      ['Acceso administrativo', 'Cada operación vuelve a comprobar la sesión y el rol de administrador en el servidor.', 'PROTEGIDO'],
      ['Sesión y formularios', 'Cookies HttpOnly y SameSite, token CSRF y límite de intentos de acceso.', 'PROTEGIDO'],
      ['Tecnología PHP', 'Arena Castell usa Python; no contiene ni ejecuta archivos PHP.', 'NO APLICA'],
    ].map(([name, detail, status]) => `<article class="security-control"><div><h3>${name}</h3><p>${detail}</p></div><span class="security-badge">${status}</span></article>`).join('');
  });
  for (const viewport of [
    { width: 375, height: 812 }, { width: 844, height: 390 },
    { width: 768, height: 1024 }, { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    const result = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      buttonHeight: document.querySelector('#security-refresh').getBoundingClientRect().height,
      text: document.querySelector('#admin-seguridad').textContent.toLowerCase(),
    }));
    if (result.overflow || result.buttonHeight < 44) throw new Error(`Vista insegura en ${JSON.stringify(viewport)}: ${JSON.stringify(result)}`);
    if (['database_url', 'api_key', 'password'].some((term) => result.text.includes(term))) throw new Error('El panel muestra información sensible.');
  }
  console.log(JSON.stringify({ responsive: true, secretsVisible: false }));
  await browser.close();
})().catch((error) => { console.error(error); process.exitCode = 1; });
