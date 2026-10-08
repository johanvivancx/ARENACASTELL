// Formularios separados por actividad para la caja operativa de Copa Castell.
"use strict";
window.CopaCajaAdmin = async function ({$, $$, api, bindForm, esc, money, dates, showMessage, today}) {
  const root = $("#admin-copa-caja");
  if (!root) return;
  const week = $("#copa-week", root);
  const names = {DISPONIBLE: "Dinero disponible", BAR: "Bar", ENTRADAS: "Entradas", VOCALIAS: "Vocalías"};
  const descriptions = {APERTURA: "Saldo inicial", TRASPASO: "Caja entregada", INGRESO: "Ingreso", GASTO: "Gasto"};
  const areas = Object.keys(names);
  let active = "DISPONIBLE";
  let state = null;
  week.value = today;

  const showArea = (area) => {
    active = area;
    $$('[data-copa-area]', root).forEach((button) =>
      button.setAttribute("aria-pressed", String(button.dataset.copaArea === area)));
    $$('[data-copa-panel]', root).forEach((panel) =>
      panel.hidden = panel.dataset.copaPanel !== area);
    $("#copa-area-days-title", root).textContent = area === "DISPONIBLE"
      ? "Movimientos diarios de Disponible" : `Resumen diario · ${names[area]}`;
    $("#copa-area-history-title", root).textContent = `Historial de la semana · ${names[area]}`;
    if (state) renderArea();
  };

  const fillFixtures = () => {
    $$('[data-vocalia-fixture]', root).forEach((select) => {
      const old = select.value;
      select.innerHTML = `<option value="">${select.required ? "Selecciona un partido" : "Sin partido específico"}</option>` +
        state.partidos.map((item) => `<option value="${esc(item.id)}">${esc(dates(item.date))} · Fecha ${esc(item.round)} · ${esc(item.home)} vs. ${esc(item.away)}</option>`).join("");
      if (state.partidos.some((item) => item.id === old)) select.value = old;
    });
    fillTeams();
  };

  const fillTeams = () => {
    const fixtureId = $('[data-vocalia-fixture]', $("#caja-vocalia-ingreso-form", root)).value;
    const match = state?.partidos.find((item) => item.id === fixtureId);
    $("#caja-vocalia-equipo", root).innerHTML = match
      ? `<option value="">Selecciona el equipo</option>` + [match.home, match.away]
          .map((name) => `<option value="${esc(name)}">${esc(name)}</option>`).join("")
      : '<option value="">Primero selecciona un partido</option>';
    updateVocaliaDue();
  };

  const updateVocaliaDue = () => {
    const form = $("#caja-vocalia-ingreso-form", root);
    const fixtureId = $('[data-vocalia-fixture]', form).value;
    const team = $("#caja-vocalia-equipo", root).value;
    const due = state?.vocalias.find((item) => item.fixture_id === fixtureId && item.equipo === team);
    const amount = $('[name="monto"]', form);
    const pending = due ? Number(due.pendiente) : 10;
    amount.max = String(pending || 10);
    if (due && Number(amount.value) > pending && pending > 0) amount.value = String(pending);
    form.dataset.locked = due && pending <= 0 ? "true" : "false";
    $('[type="submit"]', form).disabled = form.dataset.locked === "true";
    $("#caja-vocalia-pendiente", root).textContent = !fixtureId || !team
      ? "Selecciona un partido y equipo para consultar lo pendiente."
      : due ? pending <= 0 ? "Este equipo ya completó los $10 de vocalía." :
        `Este equipo pagó ${money(due.pagado)}; le quedan ${money(due.pendiente)} de los $10.`
        : "Este partido no está en la semana seleccionada. El servidor comprobará lo ya pagado antes de guardar.";
  };

  const activeRows = () => state.movimientos.filter((item) =>
    active === "DISPONIBLE" ? item.cuenta === active
      : item.cuenta === active || item.destino === active || item.area === active);

  const renderArea = () => {
    const summary = $('[data-area-summary="' + active + '"]', root);
    let facts;
    if (active === "DISPONIBLE") {
      const rows = state.movimientos.filter((item) => item.cuenta === "DISPONIBLE" && !item.anulado_en);
      const sum = (kind) => rows.filter((item) => item.tipo === kind)
        .reduce((total, item) => total + Number(item.monto), 0);
      facts = [["Saldo actual", state.saldos.DISPONIBLE], ["Saldo inicial esta semana", sum("APERTURA")],
        ["Caja entregada esta semana", sum("TRASPASO")], ["Gastos pagados esta semana", sum("GASTO")]];
    } else {
      facts = [["Saldo actual en esta caja", state.saldos[active]],
        ...(active === "VOCALIAS" ? [["Esperado esta semana", state.vocalias_esperadas],
          ["Pendiente de cobrar", state.vocalias_pendientes]] : [["Caja entregada esta semana", state.caja_entregada[active]]]),
        ["Cobrado esta semana", state.ingresos[active]], ["Gastos atribuidos esta semana", state.gastos[active]]];
    }
    summary.innerHTML = facts.map(([label, value]) =>
      `<div><span>${esc(label)}</span><strong>${esc(money(value))}</strong></div>`).join("");

    $("#copa-caja-days", root).innerHTML = active === "DISPONIBLE"
      ? renderDisponibleDays() : renderActivityDays();
    const rows = activeRows();
    $("#copa-caja-history", root).innerHTML = rows.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Fecha</th><th>Movimiento</th><th>Sale de / entra a</th><th>Concepto</th><th>Monto</th><th></th></tr></thead><tbody>${rows.map((item) =>
          `<tr class="${item.anulado_en ? "copa-void" : ""}"><td>${esc(dates(item.fecha))}</td><td>${esc(descriptions[item.tipo])}${item.anulado_en ? " · Anulado" : ""}</td><td>${esc(names[item.cuenta])}${item.destino ? ` → ${esc(names[item.destino])}` : ""}${item.area && item.area !== item.cuenta ? ` · gasto de ${esc(names[item.area] || "la Copa")}` : ""}</td><td>${esc(item.concepto)}${item.equipo ? ` · ${esc(item.equipo)}` : ""}</td><td>${esc(money(item.monto))}</td><td>${item.anulado_en ? esc(item.motivo_anulacion) : `<button class="btn secondary" type="button" data-caja-void="${esc(item.id)}">Anular</button>`}</td></tr>`).join("")}</tbody></table>`
      : '<p class="small-text muted">Aún no hay movimientos de esta área en la semana seleccionada.</p>';
  };

  const renderDisponibleDays = () => {
    const rows = state.movimientos.filter((item) => item.cuenta === "DISPONIBLE" && !item.anulado_en);
    const days = {};
    rows.forEach((item) => {
      const day = days[item.fecha] ||= {APERTURA: 0, TRASPASO: 0, GASTO: 0};
      day[item.tipo] += Number(item.monto);
    });
    return Object.keys(days).length
      ? `<table class="copa-ledger-table"><thead><tr><th>Fecha</th><th>Saldo inicial</th><th>Caja entregada</th><th>Gastos desde Disponible</th></tr></thead><tbody>${Object.keys(days).sort().reverse().map((date) =>
          `<tr><td>${esc(dates(date))}</td><td>${esc(money(days[date].APERTURA))}</td><td>${esc(money(days[date].TRASPASO))}</td><td>${esc(money(days[date].GASTO))}</td></tr>`).join("")}</tbody></table>`
      : '<p class="small-text muted">Aún no hay movimientos de Disponible en esta semana.</p>';
  };

  const renderActivityDays = () => state.dias.length
    ? `<table class="copa-ledger-table"><thead><tr><th>Fecha</th>${active !== "VOCALIAS" ? "<th>Caja entregada</th>" : ""}<th>Cobrado</th><th>Gastado</th></tr></thead><tbody>${state.dias.map((item) =>
        `<tr><td>${esc(dates(item.fecha))}</td>${active !== "VOCALIAS" ? `<td>${esc(money(item[active].caja))}</td>` : ""}<td>${esc(money(item[active].ingreso))}</td><td>${esc(money(item[active].gasto))}</td></tr>`).join("")}</tbody></table>`
    : '<p class="small-text muted">Aún no hay registros diarios en esta semana.</p>';

  async function refresh() {
    state = await api(`/admin/copa-caja?semana=${encodeURIComponent(week.value)}`);
    $("#copa-week-caption", root).textContent = `Semana del ${dates(state.semana)} al ${dates(state.hasta)}. Los saldos de cada caja son acumulados; los importes semanales corresponden al período elegido.`;
    $("#copa-caja-total", root).textContent = `Total actual de las cuatro cajas: ${money(state.saldo_total)}`;
    $$('[data-area-balance]', root).forEach((item) =>
      item.textContent = `Saldo actual ${money(state.saldos[item.dataset.areaBalance])}`);
    $("#caja-apertura-form", root).hidden = state.saldo_inicial_registrado;
    fillFixtures();
    $("#copa-vocalias", root).innerHTML = state.vocalias.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Partido</th><th>Equipo</th><th>Esperado</th><th>Pagado</th><th>Pendiente</th></tr></thead><tbody>${state.vocalias.map((item) =>
          `<tr><td>${esc(item.fixture_id)}</td><td>${esc(item.equipo)}</td><td>${esc(money(item.esperado))}</td><td>${esc(money(item.pagado))}</td><td>${esc(money(item.pendiente))}</td></tr>`).join("")}</tbody></table>`
      : '<p class="small-text muted">No hay partidos programados en esta semana.</p>';
    renderArea();
  }

  $$('[data-copa-area]', root).forEach((button) =>
    button.addEventListener("click", () => showArea(button.dataset.copaArea)));
  $('[data-vocalia-fixture]', $("#caja-vocalia-ingreso-form", root))
    .addEventListener("change", fillTeams);
  $("#caja-vocalia-equipo", root).addEventListener("change", updateVocaliaDue);
  week.addEventListener("change", async () => {
    try { await refresh(); } catch (error) { showMessage(error.message); }
  });
  $("#copa-caja-history", root).addEventListener("click", async (event) => {
    const button = event.target.closest("[data-caja-void]");
    if (!button) return;
    const reason = prompt("Motivo de anulación (se conservará el historial):");
    if (reason === null) return;
    try {
      const result = await api(`/admin/copa-caja/${button.dataset.cajaVoid}/void`, {motivo: reason});
      await refresh();
      showMessage(result.message, "success");
    } catch (error) { showMessage(error.message); }
  });

  $$('.copa-caja-form', root).forEach((form) => {
    const dateInput = $('[name="fecha"]', form);
    dateInput.value = today;
    dateInput.max = today;
    bindForm(`#${form.id}`, async (data) => {
      const kind = form.dataset.cajaKind;
      const account = form.dataset.cajaAccount;
      const payload = {...data, tipo: kind, cuenta: account};
      if (kind === "GASTO" && account !== "DISPONIBLE") payload.area = account;
      if (account === "VOCALIAS" && kind === "INGRESO" && (!data.fixture_id || !data.equipo))
        throw new Error("Selecciona el partido y el equipo que pagó.");
      const title = form.querySelector("h4").textContent;
      if (!confirm(`${title}: ¿guardar ${money(data.monto)}? Revisa fecha y concepto antes de continuar.`)) return;
      const result = await api("/admin/copa-caja", payload);
      form.reset();
      dateInput.value = today;
      await refresh();
      showMessage(result.message, "success");
    });
  });
  showArea(active);
  await refresh();
};
