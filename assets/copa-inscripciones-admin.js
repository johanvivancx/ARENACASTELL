// Control de inscripciones y carnets, separado de las cajas operativas.
"use strict";
window.CopaInscripcionesAdmin = function ({$, api, bindForm, esc, money, dates, showMessage, today, closeMobileForm}) {
  const root = $("#admin-copa-caja");
  const panel = $('[data-copa-panel="INSCRIPCIONES"]', root);
  const form = $("#copa-inscripciones-pago-form", panel);
  const teamSelect = $("#copa-inscripciones-equipo", panel);
  const conceptSelect = $("#copa-inscripciones-concepto", panel);
  const dateInput = $("#copa-inscripciones-fecha", panel);
  const cashInput = $("#copa-inscripciones-efectivo", panel);
  const transferInput = $("#copa-inscripciones-transferencia", panel);
  const search = $("#copa-inscripciones-buscar", panel);
  const filter = $("#copa-inscripciones-filtro", panel);
  let state = null;
  dateInput.value = today;
  dateInput.max = today;

  const selected = () => state?.equipos.find((item) => item.equipo === teamSelect.value);
  const due = () => Number(selected()?.[conceptSelect.value.toLowerCase()]?.pendiente || 0);
  const total = () => (Math.round(Number(cashInput.value || 0) * 100) +
    Math.round(Number(transferInput.value || 0) * 100)) / 100;
  const updateForm = () => {
    const team = selected();
    const balance = due();
    $("#copa-inscripciones-total", panel).value = money(total());
    $("#copa-inscripciones-pago-aviso", panel).textContent = team
      ? `${team.equipo} · ${conceptSelect.value === "CARNETS" ? "carnets" : "inscripción"}: pendiente ${money(balance)}. Solo registra dinero que recibiste ahora.`
      : "Selecciona un equipo y un concepto para ver cuánto falta.";
    form.querySelector('[type="submit"]').disabled = !team || balance <= 0;
  };
  const line = (title, info) => {
    if (!Number(info.pendiente)) return `<div><span>${title}</span><strong class="good">Completo</strong><small>${info.completo_inicial ? "Según hoja; medio anterior sin clasificar" : `Cobrado en esta página: ${esc(money(info.cobrado_nuevo))}`}</small></div>`;
    return `<div><span>${title} · ${esc(money(info.esperado))}</span><strong>${esc(money(info.pendiente))} pendiente</strong><small>${Number(info.abono_inicial) ? `Abono anterior ${esc(money(info.abono_inicial))} · medio sin clasificar` : "Sin abono anterior"}${Number(info.cobrado_nuevo) ? ` · nuevo ${esc(money(info.cobrado_nuevo))}` : ""}</small></div>`;
  };
  const render = () => {
    if (!state) return;
    const initial = state.equipos.reduce((sum, item) => sum + Number(item.inscripcion.abono_inicial) + Number(item.carnets.abono_inicial), 0);
    $("#copa-inscripciones-resumen", panel).innerHTML = [
      ["Inscripciones pendientes", state.pendiente_inscripciones],
      ["Carnets pendientes", state.pendiente_carnets],
      ["Nuevos cobros en efectivo", state.cobrado_efectivo],
      ["Nuevos cobros por transferencia", state.cobrado_transferencia],
      ["Abonos anteriores con monto conocido · medio sin clasificar", initial],
    ].map(([label, value]) => `<div><span>${esc(label)}</span><strong>${esc(money(value))}</strong></div>`).join("");

    const query = search.value.trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const rows = state.equipos.filter((item) => {
      const pending = Number(item.inscripcion.pendiente) + Number(item.carnets.pendiente) > 0;
      const normalized = `${item.equipo} ${item.club}`.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
      return normalized.includes(query) && (filter.value === "TODOS" ||
        (filter.value === "PENDIENTES" ? pending : !pending));
    });
    $("#copa-inscripciones-filtrado", panel).textContent = `${rows.length} equipo${rows.length === 1 ? "" : "s"} en esta vista.`;
    $("#copa-inscripciones-equipos", panel).innerHTML = rows.length ? rows.map((item) =>
      `<article class="copa-inscripcion-card"><div class="copa-inscripcion-card-head"><div><small>${esc(item.equipo)}</small><h4>${esc(item.club)}</h4></div><button class="btn secondary small" type="button" data-copa-carnets="${esc(item.equipo)}">Ajustar cantidad</button></div><p>${esc(item.carnets_cantidad)} carnets × $0,50 = ${esc(money(item.carnets.esperado))}</p><div class="copa-inscripcion-estados">${line("Inscripción", item.inscripcion)}${line("Carnets", item.carnets)}</div>${item.nota ? `<p class="small-text muted">${esc(item.nota)}</p>` : ""}${Number(item.inscripcion.pendiente) || Number(item.carnets.pendiente) ? `<button class="btn small" type="button" data-copa-cobrar="${esc(item.equipo)}">Registrar cobro</button>` : ""}</article>`).join("")
      : '<p class="small-text muted">No hay equipos que coincidan con este filtro.</p>';

    const history = $("#copa-inscripciones-historial", panel);
    history.innerHTML = state.pagos.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Fecha</th><th>Equipo</th><th>Concepto</th><th>Efectivo</th><th>Transferencia</th><th>Total</th><th>Registrado por</th><th>Estado</th></tr></thead><tbody>${state.pagos.map((p) =>
          `<tr class="${p.anulado_en ? "copa-void" : ""}"><td>${esc(dates(p.fecha))}</td><td>${esc(p.equipo)}</td><td>${p.concepto === "CARNETS" ? "Carnets" : "Inscripción"}</td><td>${esc(money(p.efectivo))}</td><td>${esc(money(p.transferencia))}</td><td>${esc(money(p.monto))}</td><td>${esc(p.registrado_por_nombre)}</td><td>${p.anulado_en ? `Anulado por ${esc(p.anulado_por_nombre)}: ${esc(p.motivo_anulacion)}` : `<button class="btn secondary small" type="button" data-copa-inscripcion-void="${esc(p.id)}">Anular</button>`}</td></tr>`).join("")}</tbody></table>`
      : '<p class="small-text muted">Todavía no hay cobros nuevos. Los estados de la hoja se muestran arriba y no se duplican aquí.</p>';
    updateForm();
  };
  const refresh = async () => {
    state = await api("/admin/copa-inscripciones");
    const previous = teamSelect.value;
    teamSelect.innerHTML = '<option value="">Selecciona un equipo</option>' + state.equipos.map((item) =>
      `<option value="${esc(item.equipo)}">${esc(item.equipo)} · ${esc(item.club)}</option>`).join("");
    if (state.equipos.some((item) => item.equipo === previous)) teamSelect.value = previous;
    render();
  };
  [teamSelect, conceptSelect].forEach((input) => input.addEventListener("change", updateForm));
  [cashInput, transferInput].forEach((input) => input.addEventListener("input", updateForm));
  [search, filter].forEach((input) => input.addEventListener(input === search ? "input" : "change", render));
  $("#copa-inscripciones-equipos", panel).addEventListener("click", async (event) => {
    const collect = event.target.closest("[data-copa-cobrar]");
    if (collect) {
      teamSelect.value = collect.dataset.copaCobrar;
      conceptSelect.value = Number(selected()?.inscripcion.pendiente) ? "INSCRIPCION" : "CARNETS";
      updateForm();
      const disclosure = form.closest(".copa-form-disclosure");
      if (disclosure) disclosure.open = true;
      (disclosure || form).scrollIntoView({behavior: "smooth", block: "start"});
      return;
    }
    const adjust = event.target.closest("[data-copa-carnets]");
    if (!adjust) return;
    const team = state.equipos.find((item) => item.equipo === adjust.dataset.copaCarnets);
    if (!team) return;
    const entered = prompt(`Cantidad de carnets de ${team.equipo}. Cada uno cuesta $0,50.`, String(team.carnets_cantidad));
    if (entered === null) return;
    if (!/^\d{1,3}$/.test(entered.trim()) || Number(entered) > 100) {
      showMessage("Escribe una cantidad entre 0 y 100.");
      return;
    }
    if (!confirm(`¿Ajustar a ${entered} carnets el total de ${team.equipo}? Esto cambiará cuánto falta por cobrar.`)) return;
    try {
      const result = await api("/admin/copa-inscripciones/carnets", {equipo: team.equipo, cantidad: entered.trim()});
      await refresh();
      showMessage(result.message, "success");
    } catch (error) { showMessage(error.message); }
  });
  $("#copa-inscripciones-historial", panel).addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copa-inscripcion-void]");
    if (!button) return;
    const reason = prompt("Motivo de anulación (el registro quedará en el historial):");
    if (reason === null) return;
    if (!confirm("¿Anular este cobro? Dejará de contar como pagado.")) return;
    try {
      const result = await api(`/admin/copa-inscripciones/pagos/${button.dataset.copaInscripcionVoid}/void`, {motivo: reason});
      await refresh();
      showMessage(result.message, "success");
    } catch (error) { showMessage(error.message); }
  });
  bindForm("#copa-inscripciones-pago-form", async (data) => {
    const balance = due();
    const amount = total();
    if (!data.equipo || amount <= 0 || Math.round(amount * 100) > Math.round(balance * 100))
      throw new Error(`El cobro debe ser mayor que cero y no superar ${money(balance)} pendientes.`);
    if (!confirm(`¿Registrar ${money(amount)} de ${data.equipo} para ${data.concepto === "CARNETS" ? "carnets" : "inscripción"}? Efectivo ${money(data.efectivo)}, transferencia ${money(data.transferencia)}.`)) return;
    const result = await api("/admin/copa-inscripciones/pagos", data);
    cashInput.value = "0";
    transferInput.value = "0";
    await refresh();
    showMessage(result.message, "success");
    closeMobileForm(form);
  });
  return {refresh};
};
