// Lógica del sitio
"use strict";
document.documentElement.classList.add("js");
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

// Calcula la ruta base
const siteRoot = new URL("../", document.currentScript.src);

// Construye enlaces internos
const pageHref = (name) =>
  new URL(name === "index.html" ? name : `pages/${name}`, siteRoot).href;
const page = document.body.dataset.page;
const query = new URLSearchParams(location.search);
let session = { usuario: null, csrf: null };
let catalog = null;
let currentOrder = null;
let historyData = null;
let reportData = null;
const mailStates = {
  LOCAL: "Aviso guardado",
  PENDIENTE: "Pendiente de envío",
  ENVIADO: "Enviado",
  ERROR: "Requiere revisión",
  CANCELADO: "Envío cancelado",
};
let availabilityRequest = 0;
let manualAvailabilityRequest = 0;

// Da formato al dinero
const money = (value) =>
  new Intl.NumberFormat("es-EC", { style: "currency", currency: "USD" }).format(
    Number(value || 0),
  );

// Escapa texto peligroso
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );

// Da formato a fechas
const dates = (value) =>
  value
    ? new Intl.DateTimeFormat("es-EC", {
        dateStyle: "medium",
        timeZone: "America/Guayaquil",
      }).format(
        new Date(value.length === 10 ? `${value}T12:00:00-05:00` : value),
      )
    : "—";

// Da formato a horas
const times = (value) =>
  new Intl.DateTimeFormat("es-EC", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Guayaquil",
    hour12: false,
  }).format(new Date(value));
const kinds = {
  RESERVA: "Reserva de cancha",
  TORNEO: "Inscripción de torneo",
  ESCUELA: "Escuela Súper Chaca",
  MENSUALIDAD: "Mensualidad Súper Chaca",
};
const methods = {
  TRANSFERENCIA: "Transferencia bancaria",
  EFECTIVO: "Efectivo en cancha",
  TARJETA: "Tarjeta de crédito/débito",
  DEBITO: "Tarjeta de débito",
  CREDITO: "Tarjeta de crédito",
};
const events = {
  HORA: "Cancha por hora",
  CUMPLEANOS: "Cumpleaños",
  EVENTO: "Evento deportivo",
};
const expenseCategories = {
  RESERVAS: "Reservas",
  TORNEOS: "Torneos",
  SUPER_CHACA: "Súper Chaca",
};

// Construye listas de datos
const detailList = (pairs) =>
  `<dl>${pairs.map(([key, value]) => `<div><dt>${esc(key)}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>`;

// Habla con el servidor
async function api(path, data) {
  const options = {
    method: data === undefined ? "GET" : "POST",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  };
  if (data !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.headers["X-CSRF-Token"] = session.csrf || "";
    options.body = JSON.stringify(data);
  }
  let response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new Error(
      "No hay conexión con el servidor. Abre el proyecto mediante Python para guardar datos en PostgreSQL.",
    );
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(
      "Esta vista necesita el servidor Python del proyecto; consulta las instrucciones de inicio.",
    );
  }
  if (!response.ok) {
    const error = new Error(body.error || "No se pudo completar la operación.");
    error.status = response.status;
    throw error;
  }
  return body;
}

// Muestra mensajes visibles
function showMessage(text, type = "error") {
  const host = $("#form-message") || $("#connection-message");
  if (!host) return;
  host.hidden = false;
  host.className = `notice ${type}`;
  host.textContent = text;
  if (host.id === "form-message") host.focus();
}

// Limpia mensajes anteriores
function clearMessage() {
  if ($("#form-message")) $("#form-message").hidden = true;
}

// Valida el siguiente enlace
function safeNext(fallback = "mis_reservas_inscripciones.html") {
  const candidate = query.get("next");
  if (!candidate) return pageHref(fallback);
  try {
    const url = new URL(candidate, location.href);
    const relative = url.pathname.slice(siteRoot.pathname.length);
    const localPage =
      relative === "index.html" || /^pages\/[a-z_]+\.html$/.test(relative);
    return url.origin === siteRoot.origin &&
      url.pathname.startsWith(siteRoot.pathname) &&
      localPage
      ? url.href
      : pageHref(fallback);
  } catch {
    return pageHref(fallback);
  }
}

// Construye acceso seguro
function loginHref() {
  const next =
    page === "home" ? pageHref("index.html") + location.search : location.href;
  return `${pageHref("iniciar_sesion.html")}?next=${encodeURIComponent(next)}`;
}

// Actualiza el menú personal
function updateSessionUI() {
  const user = session.usuario;
  $$("[data-admin-link]").forEach((el) => (el.hidden = user?.rol !== "ADMIN"));
  $$("[data-history-link]").forEach((el) => (el.hidden = !user));
  const account = $("[data-account-link]");
  if (user && account) {
    account.href = pageHref("mi_perfil.html");
    $("span", account).textContent = "Mi cuenta";
  }
  if ($("#auth-gate")) $("#auth-gate").hidden = Boolean(user);
  $$("[data-login-link]").forEach((el) => (el.href = loginHref()));
  $$("[data-register-link]").forEach(
    (el) =>
      (el.href = loginHref().replace(
        "iniciar_sesion.html",
        "registrarse.html",
      )),
  );
  if (query.get("next") && ["login", "register"].includes(page))
    $$(".auth-foot a").forEach(
      (el) => (el.href += `?next=${encodeURIComponent(safeNext())}`),
    );
  $$("[data-profile]").forEach(
    (input) =>
      (input.value =
        user?.[input.dataset.profile] || "Inicia sesión para completar"),
  );
}

// Valida cédulas ecuatorianas
function validCedula(value) {
  if (
    !/^[0-9]{10}$/.test(value) ||
    +value.slice(0, 2) < 1 ||
    +value.slice(0, 2) > 24 ||
    +value[2] > 5
  )
    return false;
  const sum = [...value.slice(0, 9)].reduce((total, digit, index) => {
    let n = +digit * (index % 2 === 0 ? 2 : 1);
    return total + (n > 9 ? n - 9 : n);
  }, 0);
  return (10 - (sum % 10)) % 10 === +value[9];
}
$$("[data-cedula]").forEach((input) => {
  input.addEventListener("input", () => {
    input.setCustomValidity("");
    input.removeAttribute("aria-invalid");
  });
  input.addEventListener("change", () => {
    const invalid = input.value && !validCedula(input.value);
    input.setCustomValidity(
      invalid ? "Revisa la cédula ecuatoriana de 10 dígitos." : "",
    );
    input.setAttribute("aria-invalid", String(Boolean(invalid)));
  });
});
$$("[data-show-password]").forEach((button) =>
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.showPassword);
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    button.setAttribute("aria-pressed", String(visible));
    button.setAttribute(
      "aria-label",
      visible ? "Ocultar contraseña" : "Mostrar contraseña",
    );
  }),
);
if (page === "register" || page === "reset") {
  const input = $("#password");
  if (input) input.autocomplete = "new-password";
}
const menu = $(".menu-toggle");
menu?.addEventListener("click", () => {
  const expanded = menu.getAttribute("aria-expanded") !== "true";
  menu.setAttribute("aria-expanded", String(expanded));
  menu.setAttribute("aria-label", expanded ? "Cerrar menú" : "Abrir menú");
  $("#main-nav").classList.toggle("open", expanded);
});
document.addEventListener("keydown", (event) => {
  if (
    event.key === "Escape" &&
    menu?.getAttribute("aria-expanded") === "true"
  ) {
    menu.click();
    menu.focus();
  }
});
$$("[data-print]").forEach((button) =>
  button.addEventListener("click", () => window.print()),
);

// Lee datos del formulario
function formData(form) {
  const data = Object.fromEntries(new FormData(form));
  $$("input[type=checkbox]", form).forEach(
    (input) => (data[input.name] = input.checked),
  );
  return data;
}

// Conecta formularios con acciones
function bindForm(id, action) {
  const form = $(id);
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage();
    if (form.dataset.busy === "true") return;
    const submit = $("[type=submit]", form);
    const label = submit.innerHTML;
    form.dataset.busy = "true";
    submit.disabled = true;
    submit.textContent = "Procesando…";
    try {
      await boot;
      await action(formData(form), form);
    } catch (error) {
      showMessage(error.message);
      if (error.status === 401 && $("#auth-gate"))
        $("#auth-gate").hidden = false;
    } finally {
      form.dataset.busy = "false";
      submit.disabled = form.dataset.locked === "true";
      submit.innerHTML = label;
      if (form.id === "payment-form") renderPaymentMethod();
    }
  });
}

// Exige una sesion activa
function needUser() {
  if (!session.usuario) {
    const error = new Error(
      "Primero inicia sesión o crea tu cuenta usando el enlace sobre el formulario.",
    );
    error.status = 401;
    throw error;
  }
}

// Abre el paso de pago
function goPayment(result) {
  location.href = `${pageHref("pagos.html")}?orden=${encodeURIComponent(result.id)}`;
}

bindForm("#login-form", async (data) => {
  session = await api("/auth/login", data);
  location.href = safeNext();
});
bindForm("#register-form", async (data) => {
  session = await api("/auth/register", data);
  location.href = safeNext("mi_perfil.html");
});
bindForm("#forgot-form", async (data) => {
  const result = await api("/auth/forgot", data);
  showMessage(result.message, "success");
});
bindForm("#reset-form", async (data) => {
  data.token = new URLSearchParams(location.hash.slice(1)).get("token") || "";
  const result = await api("/auth/reset", data);
  showMessage(result.message, "success");
  $("#reset-form").hidden = true;
  history.replaceState(null, "", location.pathname);
});
bindForm("#profile-form", async (data) => {
  needUser();
  const result = await api("/profile", data);
  session = await api("/session");
  updateSessionUI();
  $("#password_actual").value = "";
  fillProfile();
  showMessage(result.message, "success");
});
$$("[data-logout]").forEach((button) =>
  button.addEventListener("click", async () => {
    try {
      await api("/auth/logout", {});
      location.href = pageHref("index.html");
    } catch (error) {
      showMessage(error.message);
    }
  }),
);
bindForm("#reservation-form", async (data) => {
  needUser();
  if (!data.hora)
    throw new Error("Selecciona una hora disponible antes de continuar.");
  goPayment(await api("/reservations", data));
});
bindForm("#tournament-form", async (data) => {
  needUser();
  const result = await api("/tournaments", data);
  location.href = `${pageHref("informacion_torneos_pago.html")}?orden=${encodeURIComponent(result.id)}`;
});
bindForm("#school-form", async (data) => {
  needUser();
  data.cedula = data.cedula_alumno;
  goPayment(await api("/school", data));
});
bindForm("#payment-form", async (data) => {
  needUser();
  if (!currentOrder)
    throw new Error("Abre el pago desde una operación de Mi actividad.");
  const result = await api(`/orders/${currentOrder.id}/pay`, data);
  location.href = `${pageHref("confirmacion.html")}?orden=${encodeURIComponent(result.id)}`;
});
bindForm("#player-form", async (data, form) => {
  needUser();
  await api(`/teams/${query.get("equipo")}/players`, data);
  form.reset();
  await loadTeam();
  showMessage("Jugador registrado.", "success");
});
bindForm("#report-filter", async (data) => {
  await loadReports(data);
});

// Resume la reserva elegida
function reservationSummary() {
  if (!catalog || !$("#reservation-form")) return;
  const court = catalog.canchas.find(
    (c) => String(c.id) === $("#cancha_id").value,
  );
  const type = $("#tipo_evento").value;
  const rate =
    court?.[
      {
        HORA: "tarifa_hora",
        EVENTO: "tarifa_evento",
        CUMPLEANOS: "tarifa_cumpleanos",
      }[type]
    ];
  const hour = $("input[name=hora]:checked")?.value;
  $("#summary-total").textContent = money(
    Number(rate) * Number($("#horas").value),
  );
  $("#summary-details").innerHTML = detailList([
    ["Servicio", events[type]],
    ["Día", dates($("#fecha").value)],
    ["Hora", hour || "Por seleccionar"],
    ["Duración", `${$("#horas").value} h`],
    ["Tarifa por hora", money(rate)],
  ]);
}

// Carga horarios disponibles
async function loadSlots() {
  if (!$("#fecha")?.value) return;
  const request = ++availabilityRequest;
  $("#time-slots").replaceChildren();
  $("#availability-status").textContent = "Consultando horarios…";
  reservationSummary();
  try {
    const slots = await api(
      `/availability?fecha=${encodeURIComponent($("#fecha").value)}&cancha=${$("#cancha_id").value}&horas=${$("#horas").value}`,
    );
    if (request !== availabilityRequest) return;
    $("#time-slots").innerHTML = slots.horarios
      .map(
        (slot) =>
          `<label class="slot"><input type="radio" name="hora" value="${esc(slot.hora)}" ${slot.disponible ? "required" : "disabled"} aria-label="${esc(slot.hora)} ${slot.disponible ? "disponible" : "no disponible"}"><span>${esc(slot.hora)}<small>${slot.disponible ? "Disponible" : "No disponible"}</small></span></label>`,
      )
      .join("");
    const count = slots.horarios.filter((slot) => slot.disponible).length;
    $("#availability-status").textContent = count
      ? `${count} horarios disponibles para la duración elegida.`
      : "No hay horarios disponibles. Prueba otro día o una duración menor.";
    $$("input[name=hora]").forEach((input) =>
      input.addEventListener("change", reservationSummary),
    );
  } catch (error) {
    if (request === availabilityRequest)
      $("#availability-status").textContent = error.message;
  }
}

// Calcula la duración elegida
function reservationDuration() {
  const birthday = $("#tipo_evento").value === "CUMPLEANOS";
  const duration = $("#horas");
  const previous = duration.value;
  duration.replaceChildren();
  const choices = birthday ? [3] : [1, 2, 3, 4, 5, 6];
  choices.forEach((hours) => {
    const option = document.createElement("option");
    option.value = String(hours);
    option.textContent = `${hours} ${hours === 1 ? "hora" : "horas"}`;
    duration.append(option);
  });
  duration.value = birthday ? "3" : (previous || "1");
  $("#duration-help").textContent = birthday
    ? "Paquete de 3 horas. Incluye decoración, parqueadero y servicio de bar. El consumo del bar se paga aparte."
    : "Elige de 1 a 6 horas consecutivas. Contamos con parqueadero y servicio de bar; el consumo se paga aparte.";
}

// Prepara el formulario reserva
function initReservation() {
  if (!catalog) return;
  $("#cancha_id").innerHTML = catalog.canchas
    .map((c) => `<option value="${c.id}">${esc(c.nombre)}</option>`)
    .join("");
  if (events[query.get("tipo")]) $("#tipo_evento").value = query.get("tipo");
  $("#fecha").min = catalog.hoy;
  $("#fecha").max = catalog.limite;
  $("#fecha").value = catalog.hoy;
  ["fecha", "cancha_id", "horas"].forEach((name) =>
    $(`#${name}`).addEventListener("change", loadSlots),
  );
  $("#tipo_evento").addEventListener("change", () => {
    reservationDuration();
    loadSlots();
  });
  reservationDuration();
  reservationSummary();
  return loadSlots();
}

// Resume la inscripción deportiva
function tournamentSummary() {
  const tournament = catalog?.torneos.find(
    (t) => String(t.id) === $("#torneo_id").value,
  );
  $("#summary-total").textContent = tournament ? money(tournament.costo) : "—";
  $("#summary-details").innerHTML = tournament
    ? detailList([
        ["Torneo", tournament.nombre],
        ["Inicio", dates(tournament.fecha_inicio)],
        ["Cupos disponibles", tournament.disponibles],
        ["Jugadores por equipo", `Hasta ${tournament.max_jugadores}`],
      ])
    : '<p class="small-text muted">No hay torneos abiertos.</p>';
}

// Carga los torneos abiertos
function initTournaments() {
  if (!catalog) return;
  const open = catalog.torneos.filter(
    (t) =>
      t.abierto && t.fecha_inicio > catalog.hoy && Number(t.disponibles) > 0 &&
      (!t.inscripcion_desde || t.inscripcion_desde <= catalog.hoy) &&
      (!t.inscripcion_hasta || t.inscripcion_hasta >= catalog.hoy),
  );
  if ($("#torneo_id")) {
    $("#torneo_id").innerHTML =
      open
        .map((t) => `<option value="${t.id}">${esc(t.nombre)}</option>`)
        .join("") || '<option value="">Sin torneos disponibles</option>';
    const selected = open.find((t) => String(t.id) === query.get("torneo"));
    if (selected) $("#torneo_id").value = String(selected.id);
    $("#torneo_id").addEventListener("change", tournamentSummary);
    tournamentSummary();
    const form = $("#tournament-form");
    if (form) {
      form.dataset.locked = String(!open.length);
      form.querySelector("button[type=submit]").disabled = !open.length;
    }
  }
  const t = catalog.torneos.find(
    (item) => item.nombre === "Copa Castell · Mundial de Campeones",
  );
  if (t && $("#tournament-name")) {
    $("#tournament-name").textContent = t.nombre;
    $("#tournament-date").textContent = `Inicio: ${dates(t.fecha_inicio)}`;
    $("#tournament-price").textContent = `${money(t.costo)} / equipo`;
    $("#tournament-status").textContent = open.some((o) => o.id === t.id)
      ? `${t.disponibles} cupos disponibles`
      : t.fecha_inicio <= catalog.hoy
        ? "En juego · Inscripciones cerradas"
        : "Inscripciones cerradas";
  }
  if ($("#pasochoa-next-status")) {
    const next = catalog.torneos.find(
      (item) => item.nombre === "Pasochoa Cup · Sexta edición",
    );
    const available = next && open.some((item) => item.id === next.id);
    $("#pasochoa-next-link").hidden = !available;
    if (next) {
      $("#pasochoa-next-date").textContent = dates(next.fecha_inicio);
      $("#pasochoa-next-price").textContent = `${money(next.costo)} por equipo`;
      $("#pasochoa-next-capacity").textContent = `${next.cupos} equipos`;
      $("#pasochoa-next-players").textContent = `Hasta ${next.max_jugadores} jugadores`;
      $("#pasochoa-next-status").textContent = available
        ? `Inscripciones abiertas · ${next.disponibles} cupos disponibles`
        : !next.abierto || next.fecha_inicio <= catalog.hoy || (next.inscripcion_hasta && catalog.hoy > next.inscripcion_hasta)
          ? "Inscripciones cerradas"
          : next.inscripcion_desde && catalog.hoy < next.inscripcion_desde
            ? `Inscripciones del ${dates(next.inscripcion_desde)} al ${dates(next.inscripcion_hasta)}`
          : "Cupos completos";
      if (available) {
        $("#pasochoa-next-link").href = `${pageHref("pagos_torneos.html")}?torneo=${next.id}`;
      }
    } else {
      $("#pasochoa-next-status").textContent = "Inscripciones aún no disponibles";
    }
  }
}

// Busca el horario escolar
function schoolSchedule() {
  const group = $("#categoria").value;
  const schedule =
    catalog?.horarios_chaca.filter((h) => h.categoria === group) || [];
  $("#horario_id").innerHTML =
    '<option value="">Selecciona un horario</option>' +
    schedule
      .map(
        (h) =>
          `<option value="${h.id}">${esc(h.dias)} · ${esc(h.inicio.slice(0, 5))}–${esc(h.fin.slice(0, 5))}</option>`,
      )
      .join("");
}

// Prepara la inscripción escolar
function initSchool() {
  $("#summary-total").textContent = money(catalog.inscripcion_chaca || 65);
  $("#categoria").addEventListener("change", schoolSchedule);
  $("#nacimiento").max = catalog.hoy;
  $("#nacimiento").addEventListener("change", () => {
    if (!$("#nacimiento").value) return;
    const birth = $("#nacimiento").value.split("-").map(Number),
      today = catalog.hoy.split("-").map(Number);
    const age =
      today[0] -
      birth[0] -
      (today[1] < birth[1] || (today[1] === birth[1] && today[2] < birth[2])
        ? 1
        : 0);
    if (age >= 4 && age < 18) {
      const category = `Sub-${2 * (Math.floor(age / 2) + 1)}`;
      $("#categoria").value = category;
      $("#age-hint").textContent =
        `Edad de ingreso: ${age} años. Categoría correspondiente: ${category}.`;
    } else {
      $("#categoria").value = "";
      $("#age-hint").textContent = "La escuela admite alumnos de 4 a 17 años.";
    }
    schoolSchedule();
  });
  schoolSchedule();
}

// Ordena detalles visibles
function orderPairs(order) {
  const pairs = [
    ["Servicio", kinds[order.tipo]],
    ["Detalle", order.descripcion],
    ["Estado", order.estado === "PAGADA" ? "Confirmado" : "Pendiente de pago"],
  ];
  if (order.referencia_transferencia) pairs.push(["Referencia enviada", order.referencia_transferencia]);
  if (order.motivo_rechazo_transferencia) pairs.push(["Transferencia rechazada", order.motivo_rechazo_transferencia]);
  if (order.reserva)
    pairs.push(
      ["Modalidad", events[order.reserva.tipo_evento]],
      ["Fecha", dates(order.reserva.inicio)],
      [
        "Horario",
        `${times(order.reserva.inicio)} – ${times(order.reserva.fin)}`,
      ],
    );
  if (order.equipo) pairs.push(["Equipo", order.equipo.nombre]);
  if (order.escuela)
    pairs.push(
      ["Alumno", order.escuela.alumno],
      ["Categoría", order.escuela.categoria],
      [
        "Entrenamiento",
        `${order.escuela.dias}, ${order.escuela.inicio.slice(0, 5)}–${order.escuela.fin.slice(0, 5)}`,
      ],
      ["Período", dates(order.escuela.periodo)],
    );
  return pairs;
}

// Carga la operación actual
async function loadOrder() {
  needUser();
  const id = query.get("orden");
  if (!id)
    throw new Error(
      "No seleccionaste una operación. Abre una reserva o inscripción desde Mi actividad.",
    );
  currentOrder = await api(`/orders/${encodeURIComponent(id)}`);
  const pairs = orderPairs(currentOrder);
  if ($("#summary-total"))
    $("#summary-total").textContent = money(currentOrder.monto);
  if ($("#summary-details"))
    $("#summary-details").innerHTML = detailList(pairs);
  if ($("#order-details")) $("#order-details").innerHTML = detailList(pairs);
  if ($("#continue-payment"))
    $("#continue-payment").href =
      `${pageHref("pagos.html")}?orden=${encodeURIComponent(currentOrder.id)}`;
  if (page === "payment" && currentOrder.estado === "PAGADA") {
    location.replace(
      `${pageHref("confirmacion.html")}?orden=${currentOrder.id}`,
    );
    return;
  }
  if (page === "payment") {
    if (["EFECTIVO", "TRANSFERENCIA"].includes(currentOrder.metodo_previsto))
      $(`input[name="metodo"][value="${currentOrder.metodo_previsto}"]`).checked = true;
    $("#referencia_transferencia").value = currentOrder.referencia_transferencia || "";
    renderPaymentMethod();
  }
  if (page === "confirmation") {
    if (currentOrder.estado === "PENDIENTE" && ["EFECTIVO", "TRANSFERENCIA"].includes(currentOrder.metodo_previsto)) {
      const transfer = currentOrder.metodo_previsto === "TRANSFERENCIA";
      $(".success-seal").innerHTML = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></svg>';
      $("#confirmation-eyebrow").textContent = transfer ? "TRANSFERENCIA EN REVISIÓN" : "PAGO PRESENCIAL";
      $("#confirmation-title").textContent = transfer ? "Tu transferencia está pendiente de revisión" : "Tu pago en cancha está pendiente";
      $("#confirmation-description").textContent =
        transfer ? "Recibimos tu referencia. La administración debe comprobar el abono antes de confirmar tu reserva o inscripción."
        : "Elegiste pagar en efectivo al acercarte a Arena Castell. Todavía no se ha recibido ni registrado un pago.";
      $("#confirmation-notice").className = "notice warning";
      $("#confirmation-mail").textContent =
        "Contacta a la cancha para coordinar la revisión. La reserva o el cupo siguen sujetos a disponibilidad hasta que el administrador confirme el pago. El comprobante y el correo se generan después de aprobarlo.";
      $("#receipt-kind").textContent = "SOLICITUD PENDIENTE · NO ES UN COMPROBANTE DE PAGO";
      $("#receipt-details").innerHTML = detailList([
        ["Titular", session.usuario.nombre], ...pairs,
        ["Método elegido", methods[currentOrder.metodo_previsto]],
      ]) + `<div class="total"><span>Importe pendiente</span><strong>${esc(money(currentOrder.monto))}</strong></div>`;
      $("[data-print]").hidden = true;
      $("#change-payment").href = `${pageHref("pagos.html")}?orden=${encodeURIComponent(currentOrder.id)}`;
      $("#change-payment").hidden = false;
      $("#cash-contact").hidden = false;
      $("#confirmation-content").hidden = false;
      return;
    }
    if (currentOrder.estado !== "PAGADA")
      throw new Error(
        "Esta operación todavía no está pagada. Complétala desde Mi actividad para obtener el comprobante.",
      );
    const title = {
      RESERVA: "¡Gracias por tu reserva!",
      TORNEO: "¡Tu equipo ya está inscrito!",
      ESCUELA: "¡Bienvenido a Súper Chaca!",
      MENSUALIDAD: "¡Gracias por tu mensualidad!",
    }[currentOrder.tipo];
    $("#confirmation-title").textContent = title;
    $("#confirmation-description").textContent =
      currentOrder.tipo === "TORNEO"
        ? "Ahora completa tu lista de jugadores desde Mi actividad."
        : "Tu pago quedó registrado. Encontrarás todos los detalles en tu cuenta.";
    const mail = currentOrder.correo;
    $("#confirmation-mail").textContent =
      mail?.estado_envio === "ENVIADO"
        ? `Enviamos la confirmación y el comprobante a ${mail.destinatario}. Revisa también spam. Puedes consultarlos en Mi actividad.`
        : mail?.estado_envio === "PENDIENTE"
          ? `Tu confirmación está pendiente de envío a ${mail.destinatario}. La información y el comprobante ya están disponibles en Mi actividad.`
          : "La información y el comprobante están disponibles en Mi actividad. Si necesitas ayuda con el correo, comunícate con Arena Castell.";
    $("#receipt-details").innerHTML =
      detailList([
        ["Titular", session.usuario.nombre],
        ...pairs,
        ["Método", methods[currentOrder.pago.metodo]],
        ["Fecha de pago", dates(currentOrder.pago.pagado_en)],
        ["Referencia", currentOrder.pago.referencia],
      ]) +
      `<div class="total"><span>Total registrado</span><strong>${esc(money(currentOrder.monto))}</strong></div>`;
    $("#confirmation-content").hidden = false;
  }
}

// Muestra el método elegido
function renderPaymentMethod() {
  const method = $('input[name="metodo"]:checked')?.value;
  if (!$("#method-info")) return;
  $("#transfer-details").hidden = method !== "TRANSFERENCIA";
  $("#referencia_transferencia").required = method === "TRANSFERENCIA";
  $("#referencia_transferencia").disabled = method !== "TRANSFERENCIA";
  const descriptions = {
    TRANSFERENCIA: "Solicita primero los datos bancarios vigentes por el canal oficial de la cancha. Tras transferir, escribe la referencia. La solicitud se confirma cuando la administración comprueba y aprueba el abono.",
    EFECTIVO: "Paga en efectivo al acercarte a la cancha. Tu solicitud seguirá pendiente y no bloqueará horarios ni cupos hasta registrar el cobro. Coordina tu llegada por WhatsApp antes del horario solicitado.",
  };
  $("#method-info").textContent = descriptions[method] || "Elige cómo deseas realizar el pago de tu operación.";
  if ($("#pay-button-label"))
    $("#pay-button-label").textContent = method === "EFECTIVO" ? "Elegir pago en cancha" : "Enviar a revisión";
}
$$("input[name=metodo]").forEach((input) => input.addEventListener("change", renderPaymentMethod));

// Completa el perfil guardado
function fillProfile() {
  const user = session.usuario;
  if (!user) return;
  ["nombre", "email", "cedula", "telefono"].forEach(
    (name) => ($(`#${name}`).value = user[name]),
  );
  $("#profile-name").textContent = user.nombre;
  $("#profile-email").textContent = user.email;
  $("#profile-initials").textContent = user.nombre
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();
}

// Dibuja el historial filtrado
function renderHistory(filter = "TODOS") {
  const rows = historyData.ordenes.filter(
    (o) =>
      filter === "TODOS" ||
      o.tipo === filter ||
      (filter === "ESCUELA" && o.tipo === "MENSUALIDAD"),
  );
  $("#history-list").innerHTML = rows.length
    ? rows
        .map((o) => {
          const paid = o.estado === "PAGADA";
          const cash = o.estado === "PENDIENTE" && o.metodo_previsto === "EFECTIVO";
          const transfer = o.estado === "PENDIENTE" && o.metodo_previsto === "TRANSFERENCIA";
          const href = pageHref(paid || cash || transfer ? "confirmacion.html" : "pagos.html");
          return `<article class="history-item"><div><span class="tag ${paid ? "good" : "gold"}">${paid ? "Confirmado" : transfer ? "Transferencia en revisión" : cash ? "Efectivo pendiente en cancha" : o.motivo_rechazo_transferencia ? "Transferencia rechazada" : "Pendiente de pago"}</span><h3>${esc(o.descripcion)}</h3><p>${esc(kinds[o.tipo])} · ${esc(dates(o.creado_en))}</p>${o.motivo_rechazo_transferencia ? `<p>${esc(o.motivo_rechazo_transferencia)}</p>` : ""}</div><div class="history-price"><strong>${esc(money(o.monto))}</strong><div class="actions"><a class="btn small secondary" href="${href}?orden=${o.id}">${paid ? "Ver comprobante" : transfer ? "Ver revisión" : cash ? "Ver pago en cancha" : "Continuar al pago"}</a>${o.equipo_id && paid ? `<a class="text-link" href="${pageHref("mi_equipo.html")}?equipo=${o.equipo_id}">Gestionar equipo</a>` : ""}</div></div></article>`;
        })
        .join("")
    : `<div class="empty-state"><h3>Aquí comienza tu historia.</h3><p>No tienes operaciones en esta sección.</p><a class="btn" href="${pageHref("reservas.html")}">Explorar reservas</a></div>`;
}

// Carga la actividad personal
async function loadHistory() {
  needUser();
  historyData = await api("/history");
  renderHistory();
  $$("[data-filter]").forEach((button) =>
    button.addEventListener("click", () => {
      $$("[data-filter]").forEach((b) =>
        b.setAttribute("aria-pressed", String(b === button)),
      );
      renderHistory(button.dataset.filter);
    }),
  );
  $("#school-list").innerHTML = historyData.escuela.length
    ? historyData.escuela
        .map(
          (sc) =>
            `<article class="panel"><h3>${esc(sc.alumno)} · ${esc(sc.categoria)}</h3><p class="small-text muted">${esc(sc.estado)} · ${sc.cuotas_pagadas} mensualidades pagadas · Último período: ${esc(dates(sc.ultimo_periodo))}</p><span class="tag ${sc.mes_actual_pagado ? "good" : "gold"}">${sc.mes_actual_pagado ? "Mes actual pagado" : "Mes actual pendiente"}</span>${sc.estado === "ACTIVA" ? `<form method="post" data-renew="${sc.id}"><div class="form-grid"><div class="field"><label for="period-${sc.id}">Período a pagar</label><input id="period-${sc.id}" name="periodo" type="month" value="${catalog.hoy.slice(0, 7)}" min="${sc.fecha_inscripcion.slice(0, 7)}" max="${nextMonth(catalog.hoy)}" required></div></div><div class="form-actions"><button type="submit" class="btn small">Pagar mensualidad · ${money(catalog.mensualidad || 30)}</button></div></form>` : '<p class="small-text muted">Completa el pago inicial desde tu actividad para activar la inscripción.</p>'}</article>`,
        )
        .join("")
    : `<p class="muted small-text">Aún no tienes alumnos inscritos. <a href="${pageHref("informacion_super_chaca.html")}">Inscribir a un alumno</a>.</p>`;
  $$("[data-renew]").forEach((form) =>
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = $("button", form);
      button.disabled = true;
      try {
        goPayment(
          await api(`/school/${form.dataset.renew}/renew`, formData(form)),
        );
      } catch (error) {
        showMessage(error.message);
      } finally {
        button.disabled = false;
      }
    }),
  );
  $("#mail-list").innerHTML = historyData.correos.length
    ? historyData.correos
        .map(
          (mail) =>
            `<details class="mail-item"><summary>${esc(mail.asunto)} · ${esc(dates(mail.creado_en))} · ${esc(mailStates[mail.estado_envio] || "Aviso guardado")}</summary><p>${esc(mail.cuerpo)}</p></details>`,
        )
        .join("")
    : '<p class="muted small-text">Los avisos aparecerán después de confirmar una operación.</p>';
}

// Calcula el siguiente período
function nextMonth(day) {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() + 1);
  return d.toISOString().slice(0, 7);
}

// Carga jugadores del equipo
async function loadTeam() {
  needUser();
  const id = query.get("equipo");
  if (!id) throw new Error("Selecciona tu equipo desde Mi actividad.");
  const team = await api(`/teams/${encodeURIComponent(id)}`);
  $("#team-title").textContent = `${team.nombre} · ${team.torneo}`;
  $("#roster-count").textContent =
    `${team.jugadores.length} de ${team.max_jugadores} jugadores`;
  $("#roster").innerHTML = team.jugadores.length
    ? `<div class="table-wrap"><table><caption>Jugadores inscritos en tu equipo</caption><thead><tr><th scope="col">N.º</th><th scope="col">Jugador</th><th scope="col">Acción</th></tr></thead><tbody>${team.jugadores.map((p) => `<tr><td>${p.posicion}</td><td>${esc(p.nombre)}<small>${esc(p.cedula)}</small></td><td><button class="btn small danger" type="button" data-remove="${p.id}" data-name="${esc(p.nombre)}">Retirar</button></td></tr>`).join("")}</tbody></table></div>`
    : '<p class="muted small-text">Todavía no hay jugadores. Registra el primero con el formulario.</p>';
  const locked =
    team.jugadores.length >= team.max_jugadores ||
    team.estado !== "CONFIRMADO" ||
    team.fecha_inicio <= catalog.hoy;
  $("#player-form").dataset.locked = String(locked);
  $("#player-form button[type=submit]").disabled = locked;
  $$("[data-remove]").forEach((button) =>
    button.addEventListener("click", async () => {
      if (
        !confirm(
          `¿Retirar a ${button.dataset.name} de la lista? Podrás volver a registrarlo antes del inicio del torneo.`,
        )
      )
        return;
      button.disabled = true;
      try {
        await api(`/teams/${team.id}/remove`, {
          jugador_id: button.dataset.remove,
        });
        await loadTeam();
      } catch (error) {
        showMessage(error.message);
        button.disabled = false;
      }
    }),
  );
}

// Construye tablas accesibles
function table(headers, rows, caption) {
  if (!rows.length)
    return '<div class="empty-state"><p>No hay registros para mostrar.</p></div>';
  return `<div class="table-wrap" tabindex="0" role="region" aria-label="${esc(caption)}"><table><caption>${esc(caption)}</caption><thead><tr>${headers.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

// Prepara reservas recibidas por WhatsApp o en la cancha
function initManualReservation() {
  const form = $("#manual-reservation-form");
  if (!form || !catalog) return;
  $("#manual-cancha").innerHTML = catalog.canchas
    .map((court) => `<option value="${court.id}">${esc(court.nombre)}</option>`)
    .join("");
  $("#manual-fecha").min = catalog.hoy;
  $("#manual-fecha").max = catalog.limite;
  $("#manual-fecha").value = catalog.hoy;
  const suggestAmount = () => {
    const court = catalog.canchas.find((item) => String(item.id) === $("#manual-cancha").value);
    const rateKey = {
      HORA: "tarifa_hora",
      EVENTO: "tarifa_evento",
      CUMPLEANOS: "tarifa_cumpleanos",
    }[$("#manual-tipo").value];
    const total = Number(court?.[rateKey]) * Number($("#manual-horas").value);
    $("#manual-monto").value = Number.isFinite(total) && total > 0 ? total.toFixed(2) : "";
  };
  suggestAmount();
  $("#manual-reservation-toggle").addEventListener("click", () => {
    form.hidden = !form.hidden;
    $("#manual-reservation-toggle").setAttribute("aria-expanded", String(!form.hidden));
    if (!form.hidden) {
      $("#manual-cliente").focus();
      loadManualSlots();
    }
  });
  $("#manual-fecha").addEventListener("change", loadManualSlots);
  ["manual-cancha", "manual-horas"].forEach((id) =>
    $(`#${id}`).addEventListener("change", () => {
      suggestAmount();
      loadManualSlots();
    }),
  );
  const updateDuration = () => {
    const duration = $("#manual-horas");
    const previous = duration.value;
    const choices = $("#manual-tipo").value === "CUMPLEANOS" ? [3] : [1, 2, 3, 4, 5, 6];
    duration.innerHTML = choices
      .map((hours) => `<option value="${hours}">${hours} ${hours === 1 ? "hora" : "horas"}</option>`)
      .join("");
    duration.value = choices.includes(Number(previous)) ? previous : String(choices[0]);
  };
  $("#manual-tipo").addEventListener("change", () => {
    updateDuration();
    suggestAmount();
    loadManualSlots();
  });
  bindForm("#manual-reservation-form", async (data) => {
    needUser();
    if (session.usuario.rol !== "ADMIN") throw new Error("Solo administración puede registrar reservas manuales.");
    if (!confirm(`¿Registrar la reserva de ${data.cliente} el ${dates(data.fecha)} a las ${data.hora} por ${data.horas} hora(s), con ${money(Number(data.monto))} por recibir? El horario quedará ocupado y el cobro pendiente.`)) return;
    const result = await api("/admin/reservations", data);
    await loadReports();
    form.reset();
    updateDuration();
    $("#manual-horas").value = "1";
    $("#manual-fecha").value = catalog.hoy;
    suggestAmount();
    await loadManualSlots();
    showMessage(result.message, "success");
  });
}

async function loadManualSlots() {
  const date = $("#manual-fecha")?.value;
  if (!date) return;
  const request = ++manualAvailabilityRequest;
  const select = $("#manual-hora");
  const selected = select.value;
  select.innerHTML = '<option value="">Consultando horarios…</option>';
  $("#manual-availability").textContent = "Consultando horarios disponibles…";
  try {
    const result = await api(
      `/availability?fecha=${encodeURIComponent(date)}&cancha=${encodeURIComponent($("#manual-cancha").value)}&horas=${encodeURIComponent($("#manual-horas").value)}`,
    );
    if (request !== manualAvailabilityRequest) return;
    const available = result.horarios.filter((slot) => slot.disponible);
    select.innerHTML = '<option value="">Selecciona una hora</option>' + available
      .map((slot) => `<option value="${esc(slot.hora)}">${esc(slot.hora)}</option>`)
      .join("");
    if (available.some((slot) => slot.hora === selected)) select.value = selected;
    $("#manual-availability").textContent = available.length
      ? `${available.length} horarios disponibles. Se comprobará otra vez al guardar.`
      : "No hay horarios libres para esa fecha y duración.";
  } catch (error) {
    if (request !== manualAvailabilityRequest) return;
    select.innerHTML = '<option value="">No se pudieron cargar horarios</option>';
    $("#manual-availability").textContent = error.message;
  }
}

// Prepara el registro administrativo de salidas de dinero.
function initExpenses() {
  const form = $("#expense-form");
  if (!form || !catalog) return;
  $("#expense-date").max = catalog.hoy;
  $("#expense-date").value = catalog.hoy;
  $("#expense-toggle").addEventListener("click", () => {
    form.hidden = !form.hidden;
    $("#expense-toggle").setAttribute("aria-expanded", String(!form.hidden));
    if (!form.hidden) $("#expense-category").focus();
  });
  bindForm("#expense-form", async (data) => {
    needUser();
    if (session.usuario.rol !== "ADMIN") throw new Error("Solo administración puede registrar gastos.");
    if (!confirm(`¿Registrar un gasto de ${money(data.monto)} en ${expenseCategories[data.categoria]} por “${data.concepto}”? Se descontará de ese saldo.`)) return;
    const result = await api("/admin/expenses", data);
    await loadReports();
    form.reset();
    $("#expense-date").value = catalog.hoy;
    showMessage(result.message, "success");
  });
}

// Publica marcadores de Copa Castell sin editar el archivo de estadísticas.
async function initCopaResults() {
  const form = $("#copa-result-form");
  if (!form) return;
  let schedule = await api("/admin/copa-fixtures");
  const fixtureSelect = $("#copa-fixture");
  const goalsHost = $("#copa-goal-rows");
  const selectedFixture = () => schedule.fixtures.find((m) => m.id === fixtureSelect.value);
  const addGoalRow = (country, goal = null) => {
    const row = document.createElement("div");
    row.className = "copa-goal-row";
    row.dataset.country = country;
    const players = schedule.players[country] || [];
    const known = goal && players.some((p) => p.id === goal.jugador_clave);
    row.innerHTML = `<div class="field"><label>Goleador · ${esc(country)}<select class="copa-player" required><option value="">Selecciona jugador</option>${players.map((p) => `<option value="${esc(p.id)}">${p.number ? `#${esc(p.number)} · ` : ""}${esc(p.name)}</option>`).join("")}<option value="new">Jugador no listado</option></select></label></div><div class="field"><label>Goles<input class="copa-goal-count" type="number" min="1" max="99" step="1" required value="${goal ? esc(goal.goles) : 1}" /></label></div><button class="btn secondary" type="button" data-copa-remove>Quitar</button><div class="copa-new-player form-grid" hidden><div class="field"><label>Nombre completo<input class="copa-new-name" type="text" maxlength="100" /></label></div><div class="field"><label>Dorsal (opcional)<input class="copa-new-number" type="text" inputmode="numeric" maxlength="3" /></label></div></div>`;
    const selector = $(".copa-player", row);
    const toggleNew = () => {
      const custom = selector.value === "new";
      $(".copa-new-player", row).hidden = !custom;
      $(".copa-new-name", row).required = custom;
    };
    selector.addEventListener("change", toggleNew);
    $("[data-copa-remove]", row).addEventListener("click", () => row.remove());
    if (goal) {
      selector.value = known ? goal.jugador_clave : "new";
      if (!known) {
        $(".copa-new-name", row).value = goal.jugador_nombre;
        $(".copa-new-number", row).value = goal.dorsal;
      }
    }
    toggleNew();
    goalsHost.append(row);
  };
  const renderFixture = () => {
    const fixture = selectedFixture();
    if (!fixture) return;
    $("#copa-home-label").textContent = `Goles de ${fixture.home}`;
    $("#copa-away-label").textContent = `Goles de ${fixture.away}`;
    $("#copa-home-goals").value = fixture.result?.homeGoals ?? "";
    $("#copa-away-goals").value = fixture.result?.awayGoals ?? "";
    $("#copa-revision").value = fixture.result?.revision ?? 0;
    $('[data-copa-add="home"]').textContent = `Añadir goleador · ${fixture.home}`;
    $('[data-copa-add="away"]').textContent = `Añadir goleador · ${fixture.away}`;
    goalsHost.replaceChildren();
    for (const goal of fixture.result?.goals || []) addGoalRow(goal.equipo, goal);
    $("#copa-result-status").textContent = fixture.result
      ? `Publicado: ${fixture.result.homeGoals}–${fixture.result.awayGoals}. Puedes corregir el marcador y los goleadores; se reemplazará el registro anterior.`
      : "Sin resultado publicado. El partido no suma puntos ni goles todavía.";
  };
  const fillSchedule = (selected) => {
    fixtureSelect.innerHTML = schedule.fixtures
      .slice().sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`))
      .map((m) => `<option value="${esc(m.id)}">${esc(m.date)} · ${esc(m.time)} · Fecha ${m.round} · ${esc(m.home)} vs. ${esc(m.away)}${m.result ? ` · ${m.result.homeGoals}–${m.result.awayGoals}` : " · pendiente"}</option>`)
      .join("");
    if (selected && schedule.fixtures.some((m) => m.id === selected)) fixtureSelect.value = selected;
    renderFixture();
  };
  fillSchedule();
  form.hidden = false;
  fixtureSelect.addEventListener("change", renderFixture);
  $$('[data-copa-add]', form).forEach((button) => button.addEventListener("click", () => {
    const fixture = selectedFixture();
    if (fixture) addGoalRow(fixture[button.dataset.copaAdd]);
  }));
  bindForm("#copa-result-form", async (data) => {
    const fixture = selectedFixture();
    if (!fixture) throw new Error("Selecciona un partido.");
    const goals = $$(".copa-goal-row", goalsHost).map((row) => {
      const playerId = $(".copa-player", row).value;
      return {country: row.dataset.country, playerId,
        goals: $(".copa-goal-count", row).value,
        ...(playerId === "new" ? {name: $(".copa-new-name", row).value,
          number: $(".copa-new-number", row).value} : {})};
    });
    if (goals.some((g) => !g.playerId)) throw new Error("Selecciona el jugador de cada gol que agregaste.");
    const totals = Object.fromEntries([fixture.home, fixture.away].map((country) =>
      [country, goals.filter((g) => g.country === country).reduce((sum, g) => sum + Number(g.goals), 0)]));
    if (totals[fixture.home] > Number(data.homeGoals) || totals[fixture.away] > Number(data.awayGoals))
      throw new Error("Los goles de los jugadores superan el marcador.");
    const missing = Number(data.homeGoals) + Number(data.awayGoals) - totals[fixture.home] - totals[fixture.away];
    if (!confirm(`¿Publicar ${fixture.home} ${data.homeGoals}–${data.awayGoals} ${fixture.away}? ${missing ? `Quedarán ${missing} goles por atribuir a jugadores.` : "La tabla y los goleadores se actualizarán."}`)) return;
    const result = await api("/admin/copa-results", {...data, goals});
    schedule = await api("/admin/copa-fixtures");
    fillSchedule(fixture.id);
    showMessage(result.message, "success");
  });
}

// Presenta formularios de caja separados por actividad.
async function initCopaCaja() {
  await window.CopaCajaAdmin({$, $$, api, bindForm, esc, money, dates, showMessage, today: catalog.hoy});
}

// Agrupa las tareas relacionadas sin alterar sus formularios ni reportes.
function initAdminWorkspace() {
  const menu = $(".admin-section-nav");
  if (!menu) return;
  const intro = $("#admin-menu-heading");
  const moreTools = $(".admin-more-tools");
  const toolbar = $("#admin-panel-toolbar");
  const groupNav = $("#admin-group-nav");
  const overview = $("#admin-resumen");
  const panels = $$(".admin-workspace-section", $("#admin-content"))
    .filter((section) => section !== overview);
  const groups = {
    "admin-copa": {title: "Resultados de Copa Castell", tabs: [["admin-copa", "Resultados"]]},
    "admin-copa-caja": {title: "Copa Castell · Movimientos", tabs: [["admin-copa-caja", "Movimientos"]]},
    "admin-reservas": {title: "Reservas", tabs: [["admin-reservas", "Reservas realizadas"], ["admin-cobros", "Pendientes por cobrar"], ["admin-ocupacion", "Ocupación"]]},
    "admin-finanzas": {title: "Ingresos y gastos", tabs: [["admin-finanzas", "Saldos y gastos"], ["admin-reportes", "Operaciones"], ["admin-pagos", "Auditoría de pagos"]]},
    "admin-escuela": {title: "Súper Chaca", tabs: [["admin-escuela", "Mensualidades"]]},
    "admin-correos": {title: "Envío de correos", tabs: [["admin-correos", "Correos"]]},
    "admin-limpieza": {title: "Vaciar datos de prueba", tabs: [["admin-limpieza", "Limpieza"]]},
  };
  const openPanel = (id) => {
    const panel = panels.find((section) => section.id === id);
    if (!panel) return;
    const group = Object.values(groups).find(({tabs}) => tabs.some(([tabId]) => tabId === id));
    if (!group) return;
    intro.hidden = true;
    menu.hidden = true;
    moreTools.hidden = true;
    overview.hidden = true;
    toolbar.hidden = false;
    panels.forEach((section) => { section.hidden = section !== panel; });
    $("#admin-current-panel").textContent = group.title;
    groupNav.replaceChildren();
    groupNav.hidden = group.tabs.length < 2;
    group.tabs.forEach(([tabId, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.setAttribute("aria-pressed", String(tabId === id));
      button.addEventListener("click", () => openPanel(tabId));
      groupNav.append(button);
    });
    toolbar.scrollIntoView({behavior: "smooth", block: "start"});
  };
  const showMenu = () => {
    intro.hidden = false;
    menu.hidden = false;
    moreTools.hidden = false;
    overview.hidden = false;
    toolbar.hidden = true;
    groupNav.hidden = true;
    panels.forEach((section) => { section.hidden = true; });
    intro.scrollIntoView({behavior: "smooth", block: "start"});
  };
  $$('[data-admin-target]', $("#admin-content")).forEach((button) => {
    button.addEventListener("click", () => openPanel(button.dataset.adminTarget));
  });
  $("#admin-back-to-menu").addEventListener("click", showMenu);
  const deepLink = location.hash.slice(1);
  if (panels.some((section) => section.id === deepLink)) openPanel(deepLink);
}

// Permite revisar cantidades antes de reiniciar los datos operativos de prueba.
function initAdminReset() {
  const form = $("#admin-reset-form");
  if (!form) return;
  const previewHost = $("#reset-preview");
  const labels = {
    clientes: "Cuentas de clientes", ordenes: "Órdenes", reservas: "Reservas",
    pagos: "Pagos", gastos: "Gastos", equipos: "Equipos", jugadores: "Jugadores",
    inscripciones: "Inscripciones", mensualidades: "Mensualidades", correos: "Correos guardados",
  };
  let expected = null;
  const loadPreview = async () => {
    needUser();
    const result = await api("/admin/test-data-preview");
    expected = result.resumen;
    previewHost.innerHTML = `<dl>${Object.entries(labels).map(([key, label]) =>
      `<div><dt>${esc(label)}</dt><dd>${esc(expected[key])}</dd></div>`).join("")}</dl>`;
    form.hidden = !Object.values(expected).some(Number);
  };
  $("#reset-preview-button").addEventListener("click", async () => {
    try { await loadPreview(); } catch (error) { showMessage(error.message); }
  });
  bindForm("#admin-reset-form", async (data) => {
    if (!expected) throw new Error("Revisa primero los registros que se eliminarán.");
    if (!confirm("Esta acción eliminará permanentemente los datos operativos de prueba y las cuentas de clientes. Se conservarán los administradores, la configuración y Copa Castell. ¿Continuar?")) return;
    try {
      const result = await api("/admin/test-data-reset", {...data, resumen: expected});
      form.reset();
      await loadReports();
      await loadPreview();
      showMessage(result.message, "success");
    } finally {
      $("#reset-password").value = "";
    }
  });
}

// Carga reportes administrativos
async function loadReports(filters = {}) {
  needUser();
  reportData = await api(`/admin/reports?${new URLSearchParams(filters)}`);
  $("#admin-content").hidden = false;
  const finance = reportData.finanzas;
  $("#finance-stats").innerHTML = [
    ["RESERVAS", "Reservas"],
    ["TORNEOS", "Torneos"],
    ["SUPER_CHACA", "Súper Chaca"],
    ["GENERAL", "Total general"],
  ].map(([key, title]) => {
    const values = finance[key];
    const school = key === "SUPER_CHACA"
      ? `<p>Inscripciones: ${esc(money(values.inscripciones))} · Mensualidades: ${esc(money(values.mensualidades))}</p>`
      : "";
    return `<div class="stat"><span>${esc(title)}</span><p>Ingresó: ${esc(money(values.ingresos))}</p><p>Gastos: ${esc(money(values.gastos))}</p><strong class="${Number(values.saldo) < 0 ? "finance-negative" : ""}">Saldo: ${esc(money(values.saldo))}</strong>${school}</div>`;
  }).join("");
  $("#expenses-report").innerHTML = table(
    ["Fecha", "Sale de", "Concepto", "Monto", "Registrado por", "Estado"],
    reportData.gastos.map((g) => [
      dates(g.fecha_gasto),
      expenseCategories[g.categoria],
      g.concepto,
      money(g.monto),
      g.registrado_por,
      g.anulado_en ? `Anulado: ${g.motivo_anulacion}` : "Activo",
    ]),
    "Gastos registrados, incluidos los anulados para auditoría.",
  );
  const activeExpenses = reportData.gastos.filter((g) => !g.anulado_en);
  $("#expenses-actions").innerHTML = activeExpenses.length
    ? `<details class="panel"><summary>Corregir gastos registrados</summary><p class="small-text muted">La anulación conserva el registro original y devuelve el monto al saldo calculado.</p>${activeExpenses.map((g) => `<article class="cash-item"><div><h3>${esc(g.concepto)}</h3><p>${esc(expenseCategories[g.categoria])} · ${esc(dates(g.fecha_gasto))} · ${esc(money(g.monto))}</p></div><button class="btn secondary" type="button" data-void-expense="${esc(g.id)}">Anular gasto</button></article>`).join("")}</details>`
    : "";
  $$('[data-void-expense]', $("#expenses-actions")).forEach((button) =>
    button.addEventListener("click", async () => {
      const expense = activeExpenses.find((g) => String(g.id) === button.dataset.voidExpense);
      if (!expense) return;
      const reason = prompt(`Motivo para anular “${expense.concepto}” (${money(expense.monto)}):`);
      if (reason === null) return;
      if (reason.trim().length < 3 || reason.trim().length > 250) {
        showMessage("Escribe un motivo de 3 a 250 caracteres.");
        return;
      }
      if (!confirm("¿Confirmas la anulación? El registro permanecerá visible y el saldo se recalculará.")) return;
      button.disabled = true;
      try {
        const result = await api(`/admin/expenses/${encodeURIComponent(expense.id)}/void`, {motivo: reason.trim()});
        await loadReports();
        showMessage(result.message, "success");
      } catch (error) {
        showMessage(error.message);
        button.disabled = false;
      }
    }),
  );
  const transferHost = $("#transfer-report");
  const transfers = reportData.transferencias_pendientes || [];
  transferHost.innerHTML = transfers.length
    ? transfers.map((o) => `<article class="cash-item"><div><h3>${esc(o.titular)}</h3><p>${esc(o.descripcion)}</p><p>Referencia: ${esc(o.referencia_transferencia)}</p><strong>${esc(money(o.monto))} · Pendiente de revisión</strong></div><div class="actions"><button class="btn" type="button" data-transfer-action="approve-transfer" data-order="${esc(o.id)}">Aprobar abono recibido</button><button class="btn secondary" type="button" data-transfer-action="reject-transfer" data-order="${esc(o.id)}">Rechazar</button></div></article>`).join("")
    : '<p class="muted">No hay transferencias pendientes de revisión.</p>';
  $$('[data-transfer-action]', transferHost).forEach((button) => button.addEventListener('click', async () => {
    const order = transfers.find((o) => o.id === button.dataset.order);
    if (!order) return;
    const action = button.dataset.transferAction;
    const data = {revision: order.revision_pago};
    if (action === "approve-transfer") {
      if (!confirm(`¿Comprobaste en tu banco el abono de ${money(order.monto)} de ${order.titular}, referencia ${order.referencia_transferencia}? Solo aprueba si recibiste el dinero. Se volverá a revisar la disponibilidad.`)) return;
    } else {
      const reason = prompt("Escribe el motivo del rechazo. El cliente podrá verlo en su actividad.");
      if (reason === null) return;
      data.motivo = reason.trim();
      if (data.motivo.length < 3 || data.motivo.length > 250) {
        showMessage("Escribe un motivo de 3 a 250 caracteres.");
        return;
      }
    }
    button.disabled = true;
    try {
      const result = await api(`/admin/orders/${encodeURIComponent(order.id)}/${action}`, data);
      await loadReports(filters);
      showMessage(result.message, "success");
    } catch (error) {
      showMessage(error.message);
      button.disabled = false;
    }
  }));
  const cashHost = $("#cash-report");
  cashHost.innerHTML = reportData.efectivo_pendiente.length
    ? reportData.efectivo_pendiente.map((o) => `<article class="cash-item"><div><h3>${o.descripcion.startsWith("Reserva manual · ") ? "Reserva manual" : esc(o.titular)}</h3><p>${esc(o.descripcion)}</p><strong>${esc(money(o.monto))} · Efectivo pendiente</strong></div><button class="btn" type="button" data-collect-cash="${esc(o.id)}">Registrar efectivo recibido</button></article>`).join("")
    : '<p class="muted">No hay pagos en efectivo pendientes.</p>';
  $$('[data-collect-cash]', cashHost).forEach((button) => button.addEventListener('click', async () => {
    const order = reportData.efectivo_pendiente.find((o) => o.id === button.dataset.collectCash);
    if (!order || !confirm(`¿Confirmas que ya recibiste ${money(order.monto)} en efectivo por ${order.descripcion}? Se volverá a comprobar la disponibilidad antes de confirmar la operación.`)) return;
    button.disabled = true;
    try {
      const result = await api(`/admin/orders/${encodeURIComponent(order.id)}/collect-cash`, {});
      await loadReports(filters);
      showMessage(result.message, "success");
    } catch (error) {
      showMessage(error.message);
      button.disabled = false;
    }
  }));
  $("#email-report").innerHTML = table(
    ["Asunto", "Destinatario", "Estado", "Intentos", "Último resultado"],
    reportData.correos.map((mail) => [
      mail.asunto,
      mail.destinatario || "Registro anterior",
      mailStates[mail.estado_envio],
      mail.intentos,
      mail.ultimo_error || "—",
    ]),
  );
  const savedReceipts = reportData.correos.filter(
    (mail) => mail.estado_envio === "LOCAL" && mail.asunto === "Confirmación Arena Castell",
  );
  const receiptControls = $("#saved-receipt-controls");
  receiptControls.hidden = !savedReceipts.length;
  if (savedReceipts.length) {
    $("#saved-receipt-select").innerHTML = savedReceipts.map((mail) =>
      `<option value="${esc(mail.id)}">${esc(mail.destinatario || "Sin destinatario")} · ${esc(dates(mail.creado_en))} · #${esc(mail.id)}</option>`,
    ).join("");
    $("#queue-saved-receipt").onclick = async () => {
      const selected = $("#saved-receipt-select").value;
      if (!selected || !confirm("¿Poner este comprobante en cola de envío? Comprueba que el destinatario es correcto.")) return;
      const button = $("#queue-saved-receipt");
      button.disabled = true;
      try {
        const result = await api(`/admin/emails/${encodeURIComponent(selected)}/queue-receipt`, {});
        await loadReports(filters);
        showMessage(result.message, "success");
      } catch (error) {
        showMessage(error.message);
        button.disabled = false;
      }
    };
  }
  $("#reservations-report").innerHTML = table(
    [
      "Titular",
      "Correo",
      "Celular",
      "Cancha",
      "Fecha",
      "Horario",
      "Tipo",
      "Reserva",
      "Pago",
      "Valor",
      "Origen / contacto",
    ],
    reportData.reservas.map((r) => [
      r.manual ? "Administración" : r.titular,
      r.manual ? "—" : r.email,
      r.manual ? "—" : r.telefono,
      r.cancha,
      dates(r.inicio),
      `${times(r.inicio)}–${times(r.fin)}`,
      events[r.tipo_evento],
      r.estado,
      r.estado_pago === "PAGADA" ? "Registrado" : r.estado_pago,
      money(r.monto),
      r.manual ? r.detalle : "Web",
    ]),
    "Todas las reservas de la cancha, confirmadas o pendientes.",
  );
  const manualPending = reportData.reservas.filter(
    (r) => r.manual && r.estado === "CONFIRMADA" && r.estado_pago === "PENDIENTE",
  );
  $("#manual-reservation-corrections").hidden = !manualPending.length;
  $("#manual-reservation-actions").innerHTML = manualPending
    .map((r) => `<article class="cash-item"><div><h3>${esc(r.detalle)}</h3><p>${esc(dates(r.inicio))} · ${esc(times(r.inicio))}–${esc(times(r.fin))}</p></div><button class="btn secondary" type="button" data-cancel-manual="${esc(r.orden_id)}">Anular y liberar horario</button></article>`)
    .join("");
  $$('[data-cancel-manual]', $("#manual-reservation-actions")).forEach((button) =>
    button.addEventListener("click", async () => {
      const reservation = manualPending.find((r) => r.orden_id === button.dataset.cancelManual);
      if (!reservation || !confirm(`¿Anular la reserva manual de ${reservation.detalle}? El horario volverá a estar disponible.`)) return;
      button.disabled = true;
      try {
        const result = await api(`/admin/reservations/${encodeURIComponent(reservation.orden_id)}/cancel`, {});
        await loadReports();
        showMessage(result.message, "success");
      } catch (error) {
        showMessage(error.message);
        button.disabled = false;
      }
    }),
  );
  $("#operations-report").innerHTML = table(
    ["Fecha", "Titular", "Correo", "Servicio", "Detalle", "Estado", "Valor"],
    reportData.operaciones.map((o) => [
      dates(o.creado_en),
      o.titular,
      o.email,
      kinds[o.tipo],
      o.descripcion,
      o.estado,
      money(o.monto),
    ]),
    "Reservas, inscripciones y mensualidades de todos los clientes.",
  );
  $("#admin-stats").innerHTML = [
    ["Pagos registrados", reportData.resumen.pagos],
    ["Reservas pagadas", reportData.resumen.reservas],
    ["Equipos inscritos", reportData.resumen.equipos],
  ]
    .map(
      ([label, value]) =>
        `<div class="stat"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`,
    )
    .join("");
  $("#payments-report").innerHTML = table(
    ["Fecha", "Titular", "Servicio", "Método", "Monto", "Estado"],
    reportData.pagos.map((p) => [
      dates(p.pagado_en),
      p.nombre,
      p.descripcion,
      methods[p.metodo],
      money(p.monto),
      p.simulado ? "Simulado" : "Confirmado",
    ]),
    "Pagos registrados en el rango seleccionado.",
  );
  const schoolRows = [...reportData.escuela].sort((a, b) =>
    Number(a.mes_actual_pagado) - Number(b.mes_actual_pagado) ||
    a.alumno.localeCompare(b.alumno, "es"));
  const schoolPaid = schoolRows.filter((row) => row.mes_actual_pagado).length;
  $("#school-admin-stats").innerHTML = [
    ["Alumnos registrados", schoolRows.length],
    ["Al día este mes", schoolPaid],
    ["Pendientes este mes", schoolRows.length - schoolPaid],
    ["Total pagado", money(schoolRows.reduce((sum, row) => sum + Number(row.total_pagado || 0), 0))],
  ].map(([label, value]) => `<div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join("");
  $("#school-report").innerHTML = table(
    [
      "Alumno",
      "Categoría",
      "Representante",
      "Cuotas pagadas",
      "Total",
      "Mes actual",
    ],
    schoolRows.map((s) => [
      s.alumno,
      s.categoria,
      s.representante,
      s.cuotas_pagadas,
      money(s.total_pagado),
      s.mes_actual_pagado ? "Pagado" : "Pendiente",
    ]),
    "Control completo de mensualidades de Súper Chaca.",
  );
  $("#occupancy-report").innerHTML = table(
    ["Cancha", "Mes", "Reservas", "Horas", "Importe registrado"],
    reportData.ocupacion.map((r) => [
      r.nombre,
      dates(r.mes),
      r.reservas,
      Number(r.horas).toFixed(1),
      money(r.ingresos_simulados),
    ]),
    "Ocupación mensual por cancha.",
  );
}
$("#export-report")?.addEventListener("click", () => {
  if (!reportData) return;
  const rows = [
    [
      "Fecha",
      "Titular",
      "Correo",
      "Servicio",
      "Método",
      "Monto USD",
      "Referencia",
    ],
    ...reportData.pagos.map((p) => [
      p.pagado_en,
      p.nombre,
      p.email,
      p.descripcion,
      methods[p.metodo],
      p.monto,
      p.referencia,
    ]),
  ];
  // Evita fórmulas en CSV
  const safe = (value) => {
    let text = String(value ?? "");
    if (/^[=+@\-\t\r\n]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  };
  const blob = new Blob(
    ["\uFEFF" + rows.map((row) => row.map(safe).join(",")).join("\r\n")],
    { type: "text/csv;charset=utf-8" },
  );
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = "arena-castell-pagos.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

// Inicia la página actual
async function initialize() {
  if (location.protocol === "file:") return;
  const results = await Promise.allSettled([api("/session"), api("/catalog")]);
  if (results[0].status === "fulfilled") {
    session = results[0].value;
    updateSessionUI();
  }
  if (results[1].status === "fulfilled") catalog = results[1].value;
  const failure = results.find((r) => r.status === "rejected");
  if (failure) return;
  $$("[data-price]").forEach((el) => {
    const value = catalog.canchas[0]?.[el.dataset.price];
    if (value) el.innerHTML = `${esc(money(value))}<small> / hora</small>`;
  });
  if ($("#birthday-package-total") && catalog.canchas[0])
    $("#birthday-package-total").textContent =
      `${money(Number(catalog.canchas[0].tarifa_cumpleanos) * 3)} por las 3 horas`;
  try {
    if (page === "reserva-form") await initReservation();
    if (page === "torneos" || page === "torneo-form") initTournaments();
    if (page === "escuela-form") initSchool();
    if (["payment", "confirmation", "torneo-review"].includes(page))
      await loadOrder();
    if (page === "profile") fillProfile();
    if (page === "history") await loadHistory();
    if (page === "team") await loadTeam();
    if (page === "admin") {
      await loadReports();
      initAdminWorkspace();
      initAdminReset();
      initManualReservation();
      initExpenses();
      await initCopaResults();
      await initCopaCaja();
    }
  } catch (error) {
    showMessage(error.message);
  }
}
const boot = initialize();
