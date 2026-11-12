"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("assets/app.js", "utf8");
const wait = () => new Promise((resolve) => setImmediate(resolve));

async function main() {
  let currentUser = null;
  const classes = new Set();
  const windowHandlers = {};
  const documentHandlers = {};
  const span = { textContent: "Iniciar sesión" };
  const account = {
    href: "https://arenacastell.com/pages/iniciar_sesion.html",
    querySelector: (selector) => (selector === "span" ? span : null),
  };
  const historyLink = { hidden: true };
  const adminLink = { hidden: true };
  const document = {
    body: { dataset: { page: "reservas" } },
    currentScript: { src: "https://arenacastell.com/assets/app.js" },
    documentElement: {
      classList: {
        add: (...names) => names.forEach((name) => classes.add(name)),
        remove: (...names) => names.forEach((name) => classes.delete(name)),
      },
    },
    hidden: false,
    querySelector: (selector) => (selector === "[data-account-link]" ? account : null),
    querySelectorAll: (selector) => {
      if (selector === "[data-history-link]") return [historyLink];
      if (selector === "[data-admin-link]") return [adminLink];
      return [];
    },
    addEventListener: (name, callback) => { documentHandlers[name] = callback; },
    createElement: () => ({}),
  };
  const context = {
    console,
    document,
    window: { addEventListener: (name, callback) => { windowHandlers[name] = callback; } },
    location: {
      protocol: "https:",
      href: "https://arenacastell.com/pages/reservas.html",
      search: "",
    },
    fetch: async (url) => ({
      ok: true,
      status: 200,
      json: async () => url.endsWith("/session")
        ? { usuario: currentUser, csrf: "csrf-prueba" }
        : {
            hoy: "2026-11-12",
            limite: "2026-12-31",
            canchas: [],
            promocion_octubre: { desde: "2026-10-01", hasta: "2026-10-31" },
          },
    }),
    URL,
    URLSearchParams,
    Intl,
    Date,
    Blob,
    setTimeout,
    clearTimeout,
    confirm: () => false,
  };
  context.window.window = context.window;
  context.window.document = document;
  vm.createContext(context);
  vm.runInContext(source, context);
  await wait();
  await wait();

  assert.equal(historyLink.hidden, true);
  assert.equal(adminLink.hidden, true);
  assert.equal(span.textContent, "Iniciar sesión");
  assert.equal(classes.has("auth-pending"), false);

  currentUser = { nombre: "Administrador", rol: "ADMIN" };
  windowHandlers.pageshow({ persisted: true });
  await wait();
  await wait();
  assert.equal(historyLink.hidden, false);
  assert.equal(adminLink.hidden, false);
  assert.equal(span.textContent, "Mi cuenta");

  currentUser = null;
  windowHandlers.pageshow({ persisted: true });
  await wait();
  await wait();
  assert.equal(historyLink.hidden, true);
  assert.equal(adminLink.hidden, true);
  assert.equal(span.textContent, "Iniciar sesión");
  assert.match(account.href, /iniciar_sesion\.html\?next=/);
  assert.equal(typeof documentHandlers.visibilitychange, "function");
  console.log("Navegación y sesión verificadas.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
