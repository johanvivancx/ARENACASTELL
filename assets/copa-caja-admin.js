// Formularios separados por actividad para la caja operativa de Copa Castell.
"use strict";
window.CopaCajaAdmin = async function ({$, $$, api, bindForm, esc, money, dates, showMessage, today, canResetVocalias}) {
  const root = $("#admin-copa-caja");
  if (!root) return;
  const inscriptions = window.CopaInscripcionesAdmin({$, $$, api, bindForm, esc, money, dates, showMessage, today});
  const week = $("#copa-week", root);
  const names = {DISPONIBLE: "Dinero disponible", BAR: "Bar", ENTRADAS: "Entradas", VOCALIAS: "Vocalías"};
  const descriptions = {APERTURA: "Saldo inicial", TRASPASO: "Caja entregada", INGRESO: "Ingreso", GASTO: "Gasto"};
  const areas = Object.keys(names);
  let active = "DISPONIBLE";
  let state = null;
  let resetPreview = null;
  week.value = today;

  const showArea = (area) => {
    active = area;
    const separate = area === "INSCRIPCIONES";
    $$('[data-copa-area]', root).forEach((button) =>
      button.setAttribute("aria-pressed", String(button.dataset.copaArea === area)));
    $$('[data-copa-panel]', root).forEach((panel) =>
      panel.hidden = panel.dataset.copaPanel !== area);
    $(".copa-week-picker", root).hidden = separate;
    $("#copa-week-caption", root).hidden = separate;
    $("#copa-caja-total", root).hidden = separate;
    $(".copa-area-records", root).hidden = separate;
    $("#copa-caja-history", root).hidden = separate;
    if (separate) {
      inscriptions.refresh().catch((error) => showMessage(error.message));
      return;
    }
    $("#copa-area-days-title", root).textContent = area === "DISPONIBLE"
      ? "Movimientos diarios de Disponible" : `Resumen diario · ${names[area]}`;
    $("#copa-area-history-title", root).textContent = `Historial de la semana · ${names[area]}`;
    if (state) renderArea();
  };

  const fillFixtures = () => {
    const pendingIds = new Set(state.vocalias_pendientes_lista.map((item) => item.fixture_id));
    const thisWeek = state.partidos.filter((item) => item.date >= state.semana && item.date <= state.hasta);
    $$('[data-vocalia-fixture]', root).forEach((select) => {
      const old = select.value;
      const items = select.required ? thisWeek.filter((item) => pendingIds.has(item.id)) : thisWeek;
      select.innerHTML = `<option value="">${select.required ? "Selecciona un partido" : "Sin partido específico"}</option>` +
        items.map((item) => `<option value="${esc(item.id)}">${esc(dates(item.date))} · Fecha ${esc(item.round)} · ${esc(item.home)} vs. ${esc(item.away)}</option>`).join("");
      if (items.some((item) => item.id === old)) select.value = old;
    });
    fillTeams();
  };

  const fillTeams = () => {
    const fixtureId = $('[data-vocalia-fixture]', $("#caja-vocalia-ingreso-form", root)).value;
    const match = state?.partidos.find((item) => item.id === fixtureId);
    $("#caja-vocalia-equipo", root).innerHTML = match
      ? `<option value="">Selecciona el equipo</option>` + state.vocalias_pendientes_lista
          .filter((item) => item.fixture_id === fixtureId).map((item) => item.equipo)
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

  const syncVocaliaTotal = (form) => {
    const cash = Number($('[name="monto_efectivo"]', form).value || 0);
    const transfer = Number($('[name="monto_transferencia"]', form).value || 0);
    $('[name="monto"]', form).value = ((Math.round(cash * 100) + Math.round(transfer * 100)) / 100).toFixed(2);
  };

  const activeRows = () => state.movimientos.filter((item) =>
    active === "DISPONIBLE" ? item.cuenta === active
      : item.cuenta === active || item.destino === active || item.area === active);

  const debtKey = (name) => String(name || "").trim().replace(/\s+/g, " ").toLocaleLowerCase("es");
  const debtSearch = (name) => debtKey(name).normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const debtorName = $("#caja-bar-deuda-nombre", root);
  const debtFilter = $("#copa-bar-deuda-buscar", root);
  const updateDebtorHint = () => {
    const person = state?.bar_deudores.find((item) => debtKey(item.nombre) === debtKey(debtorName.value));
    $("#copa-bar-deuda-persona-aviso", root).textContent = person
      ? `${person.nombre} ya tiene ${person.deudas} ${person.deudas === 1 ? "fiado pendiente" : "fiados pendientes"} por ${money(person.pendiente)}. La nueva deuda se sumará a ese total.`
      : "Si ya debe, elige su nombre de la lista; la nueva compra se sumará a su total pendiente.";
  };

  const renderBarDebts = () => {
    const query = debtSearch(debtFilter.value);
    const people = state.bar_deudores.filter((item) => debtSearch(item.nombre).includes(query));
    const rows = state.bar_deudas.filter((item) => debtSearch(item.nombre).includes(query));
    const names = [...new Map(state.bar_deudas.map((item) => [debtKey(item.nombre), item.nombre])).values()];
    $("#copa-bar-nombres", root).innerHTML = names.map((name) => `<option value="${esc(name)}"></option>`).join("");
    $("#copa-bar-deuda-total", root).textContent = `Total pendiente por cobrar: ${money(state.bar_deuda_pendiente)}. Las deudas no están incluidas en el saldo del bar.`;
    const filteredTotal = people.reduce((total, item) => total + Number(item.pendiente), 0);
    $("#copa-bar-deuda-filtrado", root).textContent = query
      ? `Coincidencias: ${people.length} ${people.length === 1 ? "persona" : "personas"} con ${money(filteredTotal)} pendiente. Los fiados ya cobrados aparecen abajo, pero no suman.`
      : "Pendiente agrupado por persona. Cada compra conserva su detalle y se cobra por separado.";
    $("#copa-bar-deudores", root).innerHTML = people.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Persona</th><th>Fiados pendientes</th><th>Total que debe</th><th>Acciones</th></tr></thead><tbody>${people.map((item) =>
          `<tr><td>${esc(item.nombre)}</td><td>${esc(item.deudas)}</td><td><strong>${esc(money(item.pendiente))}</strong></td><td><button class="btn secondary" type="button" data-bar-debtor-view="${esc(item.nombre)}">Ver detalle</button> <button class="btn secondary" type="button" data-bar-debtor-use="${esc(item.nombre)}">Añadir deuda</button></td></tr>`).join("")}</tbody></table>`
      : '<p class="small-text muted">No hay personas con deudas pendientes que coincidan con la búsqueda.</p>';
    $("#copa-bar-deudas", root).innerHTML = rows.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Fecha</th><th>Persona</th><th>Qué debe</th><th>Monto</th><th>Registrado por</th><th>Estado</th></tr></thead><tbody>${rows.map((item) =>
          `<tr><td>${esc(dates(item.fecha))}</td><td>${esc(item.nombre)}</td><td>${esc(item.concepto)}</td><td>${esc(money(item.monto))}</td><td>${esc(item.registrado_por_nombre)}</td><td><div class="copa-debt-actions">${item.cobrada_en ? `<span>Cobrada por ${esc(item.cobrada_por_nombre)}</span>` : `<button class="btn secondary" type="button" data-bar-debt-collect="${esc(item.id)}">Registrar cobro</button>`}<button class="btn danger" type="button" data-bar-debt-void="${esc(item.id)}" aria-label="Eliminar fiado de ${esc(item.nombre)} por ${esc(money(item.monto))}">Eliminar fiado</button></div></td></tr>`).join("")}</tbody></table>`
      : '<p class="small-text muted">No hay fiados que coincidan con la búsqueda.</p>';
    updateDebtorHint();
  };

  const renderArea = () => {
    const summary = $('[data-area-summary="' + active + '"]', root);
    summary.hidden = active === "VOCALIAS";
    $("#copa-vocalia-resumen", root).hidden = active !== "VOCALIAS";
    let facts;
    if (active === "DISPONIBLE") {
      const rows = state.movimientos.filter((item) => item.cuenta === "DISPONIBLE" && !item.anulado_en);
      const sum = (kind) => rows.filter((item) => item.tipo === kind)
        .reduce((total, item) => total + Number(item.monto), 0);
      facts = [["Saldo actual", state.saldos.DISPONIBLE], ["Saldo inicial esta semana", sum("APERTURA")],
        ["Caja entregada esta semana", sum("TRASPASO")], ["Gastos pagados esta semana", sum("GASTO")]];
    } else {
      facts = active === "VOCALIAS" ? [] : [
        ["Saldo actual en esta caja", state.saldos[active]],
        ["Caja entregada esta semana", state.caja_entregada[active]],
        ["Cobrado esta semana", state.ingresos[active]],
        ["Gastos atribuidos esta semana", state.gastos[active]]];
    }
    summary.innerHTML = facts.map(([label, value]) =>
      `<div><span>${esc(label)}</span><strong>${esc(money(value))}</strong></div>`).join("");
    if (active === "VOCALIAS") {
      const card = (title, subtitle, facts) => `<section class="copa-week-card"><h4>${esc(title)}</h4><p>${esc(subtitle)}</p><dl>${facts.map(([label, value]) =>
        `<div><dt>${esc(label)}</dt><dd>${esc(money(value))}</dd></div>`).join("")}</dl></section>`;
      const current = state.vocalias_semana;
      const all = state.vocalias_general;
      $("#copa-vocalia-resumen", root).innerHTML =
        card(`Semana del ${dates(state.semana)} al ${dates(state.hasta)}`,
          "Cobros y gastos según la fecha en que se registraron.", [
            ["Cobrado en efectivo", current.cobrado_efectivo],
            ["Cobrado por transferencia", current.cobrado_transferencia],
            ...(Number(current.cobrado_sin_desglose) ? [["Cobros sin medio clasificado", current.cobrado_sin_desglose]] : []),
            ["Total cobrado", current.cobrado], ["Gastos de la semana", current.gastado],
            ["Efectivo restante de la semana", Number(current.cobrado_efectivo) - Number(current.gastado_efectivo)],
            ["Transferencias restantes de la semana", Number(current.cobrado_transferencia) - Number(current.gastado_transferencia)],
            ["Resultado de la semana", current.neto]]) +
        card("Todas las semanas", "Acumulado histórico; no cambia al elegir otra semana.", [
            ["Cobrado en efectivo", all.cobrado_efectivo],
            ["Cobrado por transferencia", all.cobrado_transferencia],
            ...(Number(all.cobrado_sin_desglose) ? [["Cobros sin medio clasificado", all.cobrado_sin_desglose]] : []),
            ["Total cobrado", all.cobrado], ["Gastos acumulados", all.gastado],
            ["Disponible en efectivo", state.vocalias_saldos.efectivo],
            ["Disponible en transferencias", state.vocalias_saldos.transferencia],
            ...(Number(state.vocalias_saldos.sin_desglose) ? [["Saldo sin medio clasificado", state.vocalias_saldos.sin_desglose]] : []),
            ["Saldo total actual", all.neto]]);
      const notice = $("#copa-vocalia-desglose-aviso", root);
      notice.hidden = !state.vocalias_saldos.movimientos_sin_desglose;
      notice.textContent = "Hay movimientos anteriores sin medio de pago. Los importes de efectivo y transferencia son solo los identificados; clasifica esos movimientos en el historial para conocer los saldos exactos. El total sí incluye todos los movimientos.";
    }

    $("#copa-caja-days", root).innerHTML = active === "DISPONIBLE"
      ? renderDisponibleDays() : renderActivityDays();
    const rows = activeRows();
    $("#copa-caja-history", root).innerHTML = rows.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Fecha</th><th>Movimiento</th><th>Sale de / entra a</th><th>Concepto</th><th>Monto</th><th>Registrado por</th><th>Estado</th></tr></thead><tbody>${rows.map((item) =>
          `<tr class="${item.anulado_en ? "copa-void" : ""}"><td>${esc(dates(item.fecha))}</td><td>${esc(descriptions[item.tipo])}${item.anulado_en ? " · Anulado" : ""}</td><td>${esc(names[item.cuenta])}${item.destino ? ` → ${esc(names[item.destino])}` : ""}${item.area && item.area !== item.cuenta ? ` · gasto de ${esc(names[item.area] || "la Copa")}` : ""}</td><td>${esc(item.concepto)}${item.equipo ? ` · ${esc(item.equipo)}` : ""}${item.cuenta === "VOCALIAS" && ["INGRESO", "GASTO"].includes(item.tipo) && item.monto_efectivo !== null ? ` · efectivo ${esc(money(item.monto_efectivo))}, transferencia ${esc(money(item.monto_transferencia))}` : ""}</td><td>${esc(money(item.monto))}</td><td>${esc(item.registrado_por_nombre)}</td><td>${item.anulado_en ? `Anulado por ${esc(item.anulado_por_nombre)}: ${esc(item.motivo_anulacion)}` : `${item.cuenta === "VOCALIAS" && ["INGRESO", "GASTO"].includes(item.tipo) && item.monto_efectivo === null ? `<button class="btn secondary" type="button" data-caja-split="${esc(item.id)}">Clasificar medio</button> ` : ""}<button class="btn secondary" type="button" data-caja-void="${esc(item.id)}">Anular</button>`}</td></tr>`).join("")}</tbody></table>`
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
    $("#copa-vocalias-pendiente-total", root).textContent = `Por cobrar de los partidos de esta semana: ${money(state.vocalias_pendientes)}.`;
    $("#copa-vocalias", root).innerHTML = state.vocalias_pendientes_lista.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Partido</th><th>Equipo pendiente</th><th>Pagado</th><th>Falta cobrar</th></tr></thead><tbody>${state.vocalias_pendientes_lista.map((item) => {
          const fixture = state.partidos.find((match) => match.id === item.fixture_id);
          return `<tr><td>${fixture ? `${esc(dates(fixture.date))} · ${esc(fixture.home)} vs. ${esc(fixture.away)}` : esc(item.fixture_id)}</td><td>${esc(item.equipo)}</td><td>${esc(money(item.pagado))}</td><td><strong>${esc(money(item.pendiente))}</strong></td></tr>`;
        }).join("")}</tbody></table>`
      : '<p class="small-text muted">No hay vocalías pendientes de los partidos de esta semana. Los cobros anteriores siguen en el historial.</p>';
    renderBarDebts();
    if (active !== "INSCRIPCIONES") renderArea();
  }

  $$('[data-copa-area]', root).forEach((button) =>
    button.addEventListener("click", () => showArea(button.dataset.copaArea)));
  $('[data-vocalia-fixture]', $("#caja-vocalia-ingreso-form", root))
    .addEventListener("change", fillTeams);
  $("#caja-vocalia-equipo", root).addEventListener("change", updateVocaliaDue);
  ["#caja-vocalia-ingreso-form", "#caja-vocalia-gasto-form"].forEach((selector) => {
    const form = $(selector, root);
    $$('[name="monto_efectivo"], [name="monto_transferencia"]', form)
      .forEach((input) => input.addEventListener("input", () => syncVocaliaTotal(form)));
  });
  $("#copa-bar-deudas", root).addEventListener("click", async (event) => {
    const remove = event.target.closest("[data-bar-debt-void]");
    if (remove) {
      const item = state.bar_deudas.find((row) => String(row.id) === remove.dataset.barDebtVoid);
      if (!item) return;
      const motivo = prompt(`Motivo para eliminar el fiado de ${item.nombre} (${item.concepto}, ${money(item.monto)}):`, "Registro duplicado");
      if (motivo === null) return;
      if (motivo.trim().length < 3) { showMessage("Escribe un motivo de al menos 3 caracteres."); return; }
      const consequence = item.cobrada_en
        ? "También se anulará el ingreso de caja asociado a este cobro."
        : "Se restará del pendiente de esta persona; la caja no cambiará.";
      if (!confirm(`¿Eliminar solo este fiado de ${item.nombre} por ${money(item.monto)}? ${consequence} Los otros fiados no cambiarán.`)) return;
      try {
        const result = await api(`/admin/copa-bar-deudas/${item.id}/void`, {motivo: motivo.trim()});
        await refresh();
        showMessage(result.message, "success");
      } catch (error) { showMessage(error.message); }
      return;
    }
    const button = event.target.closest("[data-bar-debt-collect]");
    if (!button || !confirm("¿Ya recibiste el importe completo? Se sumará una sola vez al bar.")) return;
    try {
      const result = await api(`/admin/copa-bar-deudas/${button.dataset.barDebtCollect}/collect`, {fecha: today});
      await refresh();
      showMessage(result.message, "success");
    } catch (error) { showMessage(error.message); }
  });
  debtFilter.addEventListener("input", renderBarDebts);
  debtorName.addEventListener("input", updateDebtorHint);
  $("#copa-bar-deudores", root).addEventListener("click", (event) => {
    const view = event.target.closest("[data-bar-debtor-view]");
    const use = event.target.closest("[data-bar-debtor-use]");
    if (view) { debtFilter.value = view.dataset.barDebtorView; renderBarDebts(); }
    if (use) { debtorName.value = use.dataset.barDebtorUse; updateDebtorHint(); debtorName.focus(); }
  });
  week.addEventListener("change", async () => {
    try { await refresh(); } catch (error) { showMessage(error.message); }
  });
  $$('[data-copa-week-shift]', root).forEach((button) => button.addEventListener("click", () => {
    const date = new Date(`${week.value || today}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() + Number(button.dataset.copaWeekShift));
    week.value = date.toISOString().slice(0, 10);
    week.dispatchEvent(new Event("change"));
  }));
  $("#copa-week-current", root).addEventListener("click", () => {
    week.value = today;
    week.dispatchEvent(new Event("change"));
  });
  $("#copa-caja-history", root).addEventListener("click", async (event) => {
    const splitButton = event.target.closest("[data-caja-split]");
    if (splitButton) {
      const row = state.movimientos.find((item) => String(item.id) === splitButton.dataset.cajaSplit);
      if (!row) return;
      const entered = prompt(`¿Cuánto de ${money(row.monto)} fue en efectivo? El resto se asignará a transferencia.`, "0.00");
      if (entered === null) return;
      const cash = Number(entered.replace(",", "."));
      const total = Number(row.monto);
      if (!Number.isFinite(cash) || cash < 0 || Math.round(cash * 100) > Math.round(total * 100) || !/^\d+(?:[.,]\d{1,2})?$/.test(entered.trim())) {
        showMessage("Escribe un importe en efectivo válido, entre $0 y el total del movimiento.");
        return;
      }
      const transfer = (Math.round(total * 100) - Math.round(cash * 100)) / 100;
      if (!confirm(`Clasificar ${money(cash)} en efectivo y ${money(transfer)} por transferencia. El total original no cambiará. ¿Continuar?`)) return;
      try {
        const result = await api(`/admin/copa-caja/${row.id}/split`, {monto_efectivo: cash.toFixed(2), monto_transferencia: transfer.toFixed(2)});
        await refresh();
        showMessage(result.message, "success");
      } catch (error) { showMessage(error.message); }
      return;
    }
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

  const resetSection = $("#copa-vocalias-limpieza", root);
  resetSection.hidden = !canResetVocalias;
  if (canResetVocalias) {
    const resetForm = $("#copa-vocalias-reset-form", root);
    const previewText = $("#copa-vocalias-preview-text", root);
    $("#copa-vocalias-preview", root).addEventListener("click", async () => {
      resetPreview = null;
      resetForm.hidden = true;
      try {
        resetPreview = await api("/admin/copa-caja/vocalias/reset-preview");
        previewText.textContent = `Se borrarían ${resetPreview.total} movimientos de Vocalías: ${resetPreview.activos} activos y ${resetPreview.anulados} anulados, de todas las fechas. Ninguna otra cuenta se borrará.`;
        resetForm.hidden = resetPreview.total === 0;
      } catch (error) { showMessage(error.message); }
    });
    resetForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!resetPreview) return;
      const confirmation = $('[name="confirmacion"]', resetForm).value;
      if (confirmation !== "BORRAR VOCALIAS") {
        showMessage("Escribe BORRAR VOCALIAS exactamente.");
        return;
      }
      if (!confirm(`Se eliminarán permanentemente ${resetPreview.total} movimientos de Vocalías, incluidos ${resetPreview.anulados} anulados. ¿Confirmas el borrado solo de Vocalías?`)) return;
      try {
        const result = await api("/admin/copa-caja/vocalias/reset", {
          confirmacion: confirmation,
          password: $('[name="password"]', resetForm).value,
          resumen: resetPreview,
        });
        resetForm.reset();
        resetForm.hidden = true;
        resetPreview = null;
        previewText.textContent = result.message;
        await refresh();
        showMessage(result.message, "success");
      } catch (error) { showMessage(error.message); }
    });
  }

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
      if (account === "VOCALIAS" && ["INGRESO", "GASTO"].includes(kind)) {
        syncVocaliaTotal(form);
        payload.monto = $('[name="monto"]', form).value;
        if (Number(payload.monto) <= 0 || (kind === "INGRESO" && Number(payload.monto) > Number($('[name="monto"]', form).max)))
          throw new Error("El efectivo y la transferencia deben sumar más de $0 y no superar lo pendiente del equipo.");
      }
      const title = form.querySelector("h4").textContent;
      if (!confirm(`${title}: ¿guardar ${money(payload.monto)}? Revisa fecha y concepto antes de continuar.`)) return;
      const result = await api("/admin/copa-caja", payload);
      form.reset();
      dateInput.value = today;
      if (account === "VOCALIAS" && ["INGRESO", "GASTO"].includes(kind)) syncVocaliaTotal(form);
      await refresh();
      showMessage(result.message, "success");
    });
  });
  const debtForm = $("#caja-bar-deuda-form", root);
  $('[name="fecha"]', debtForm).value = today;
  $('[name="fecha"]', debtForm).max = today;
  bindForm("#caja-bar-deuda-form", async (data) => {
    if (!confirm(`¿Anotar deuda de ${data.nombre} por ${money(data.monto)}? No se sumará como venta cobrada.`)) return;
    const result = await api("/admin/copa-bar-deudas", data);
    debtForm.reset();
    $('[name="fecha"]', debtForm).value = today;
    await refresh();
    showMessage(result.message, "success");
  });
  showArea(active);
  await refresh();
};
