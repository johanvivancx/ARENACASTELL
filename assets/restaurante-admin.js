"use strict";

window.RestauranteAdmin = async function ({$, $$, api, bindForm, esc, money, dates, showMessage, today}) {
  const root = $("#admin-restaurante");
  if (!root) return;
  const debtForm = $("#restaurante-deuda-form", root);
  const paymentForm = $("#restaurante-abono-form", root);
  const paymentName = $("#restaurante-abono-nombre", root);
  const paymentAmount = $("#restaurante-abono-monto", root);
  const search = $("#restaurante-buscar", root);
  const mobile = window.matchMedia("(max-width: 720px)");
  let state = null;

  const key = (value) => String(value || "").trim().replace(/\s+/g, " ").toLocaleLowerCase("es");
  const searchKey = (value) => key(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const syncDisclosures = () => $$(".restaurant-form-card", root).forEach((item) => { item.open = !mobile.matches; });
  const closeMobile = (form) => {
    if (!mobile.matches) return;
    const details = form.closest("details");
    details.open = false;
    $("summary", details).focus();
  };
  syncDisclosures();
  mobile.addEventListener("change", syncDisclosures);

  const updateDebtHint = () => {
    const typed = $("[name=nombre]", debtForm).value;
    const person = state?.deudores.find((item) => key(item.nombre) === key(typed));
    $("#restaurante-deuda-aviso", root).textContent = person
      ? `${person.nombre} ya debe ${money(person.pendiente)}. La nueva cuenta se sumará a ese total.`
      : "Si la persona ya debe, usa el mismo nombre para reunir sus cuentas.";
  };

  const updatePaymentHint = () => {
    const person = state?.deudores.find((item) => key(item.nombre) === key(paymentName.value));
    $("#restaurante-abono-aviso", root).textContent = person
      ? `${person.nombre} debe ${money(person.pendiente)} en total.`
      : "Selecciona una persona para ver cuánto debe.";
    paymentAmount.max = person ? Number(person.pendiente).toFixed(2) : "";
  };

  const render = () => {
    $("#restaurante-total-deudas", root).textContent = money(state.total_deudas);
    $("#restaurante-total-efectivo", root).textContent = money(state.cobrado_efectivo);
    $("#restaurante-total-transferencia", root).textContent = money(state.cobrado_transferencia);
    $("#restaurante-total-pie", root).textContent = `TOTAL DEUDAS: ${money(state.total_deudas)}`;
    const selected = paymentName.value;
    paymentName.innerHTML = '<option value="">Selecciona una persona</option>' + state.deudores.map((item) =>
      `<option value="${esc(item.nombre)}">${esc(item.nombre)} · debe ${esc(money(item.pendiente))}</option>`).join("");
    if (state.deudores.some((item) => key(item.nombre) === key(selected))) paymentName.value = selected;
    $("#restaurante-nombres", root).innerHTML = [...new Map(state.deudas.map((item) => [key(item.nombre), item.nombre])).values()]
      .map((name) => `<option value="${esc(name)}"></option>`).join("");
    const query = searchKey(search.value);
    const people = state.deudores.filter((item) => searchKey(item.nombre).includes(query));
    const debts = state.deudas.filter((item) => searchKey(item.nombre).includes(query));
    const payments = state.abonos.filter((item) => searchKey(item.nombre).includes(query));
    $("#restaurante-deudores", root).innerHTML = people.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Persona</th><th>Cuentas pendientes</th><th>Total que debe</th><th>Acción</th></tr></thead><tbody>${people.map((item) =>
          `<tr><td>${esc(item.nombre)}</td><td>${esc(item.deudas)}</td><td><strong>${esc(money(item.pendiente))}</strong></td><td><button class="btn" type="button" data-restaurante-abonar="${esc(item.nombre)}">Registrar abono</button></td></tr>`).join("")}</tbody></table>`
      : '<p class="small-text muted">No hay deudores pendientes que coincidan con la búsqueda.</p>';
    $("#restaurante-deudas", root).innerHTML = debts.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Fecha</th><th>Persona</th><th>Detalle</th><th>Monto original</th><th>Abonado</th><th>Pendiente</th><th>Registrado por</th></tr></thead><tbody>${debts.map((item) =>
          `<tr><td>${esc(dates(item.fecha))}</td><td>${esc(item.nombre)}</td><td>${esc(item.concepto)}</td><td>${esc(money(item.monto))}</td><td>${esc(money(item.abonado))}</td><td><strong>${esc(money(item.pendiente))}</strong></td><td>${esc(item.registrado_por_nombre)}</td></tr>`).join("")}</tbody></table>`
      : '<p class="small-text muted">Todavía no hay deudas registradas.</p>';
    $("#restaurante-abonos", root).innerHTML = payments.length
      ? `<table class="copa-ledger-table"><thead><tr><th>Fecha</th><th>Persona</th><th>Monto</th><th>Forma de pago</th><th>Registrado por</th></tr></thead><tbody>${payments.map((item) =>
          `<tr><td>${esc(dates(item.fecha))}</td><td>${esc(item.nombre)}</td><td><strong>${esc(money(item.monto))}</strong></td><td>${item.metodo === "EFECTIVO" ? "Efectivo" : "Transferencia"}</td><td>${esc(item.registrado_por_nombre)}</td></tr>`).join("")}</tbody></table>`
      : '<p class="small-text muted">Todavía no hay abonos registrados.</p>';
    updateDebtHint();
    updatePaymentHint();
  };

  const refresh = async () => {
    state = await api("/admin/restaurante-deudas");
    render();
  };

  [debtForm, paymentForm].forEach((form) => {
    const input = $("[name=fecha]", form);
    input.value = today;
    input.max = today;
  });
  $("[name=nombre]", debtForm).addEventListener("input", updateDebtHint);
  paymentName.addEventListener("change", updatePaymentHint);
  search.addEventListener("input", render);
  $("#restaurante-deudores", root).addEventListener("click", (event) => {
    const button = event.target.closest("[data-restaurante-abonar]");
    if (!button) return;
    paymentName.value = button.dataset.restauranteAbonar;
    paymentForm.closest("details").open = true;
    updatePaymentHint();
    paymentAmount.focus();
    paymentForm.scrollIntoView({behavior: "smooth", block: "center"});
  });
  bindForm("#restaurante-deuda-form", async (data) => {
    if (!confirm(`¿Registrar que ${data.nombre} debe ${money(data.monto)} en el restaurante?`)) return;
    const result = await api("/admin/restaurante-deudas", data);
    debtForm.reset();
    $("[name=fecha]", debtForm).value = today;
    await refresh();
    showMessage(result.message, "success");
    closeMobile(debtForm);
  });
  bindForm("#restaurante-abono-form", async (data) => {
    const person = state.deudores.find((item) => key(item.nombre) === key(data.nombre));
    if (!person) throw new Error("Selecciona una persona con deuda pendiente.");
    const method = data.metodo === "EFECTIVO" ? "efectivo" : "transferencia";
    if (!confirm(`¿Registrar un abono de ${money(data.monto)} de ${person.nombre} pagado por ${method}?`)) return;
    const result = await api("/admin/restaurante-deudas/abonos", data);
    paymentForm.reset();
    $("[name=fecha]", paymentForm).value = today;
    await refresh();
    showMessage(result.message, "success");
    closeMobile(paymentForm);
  });
  await refresh();
};
