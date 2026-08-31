/* JavaScript sin frameworks. HTML semántico independiente + API Python local. */
"use strict";
document.documentElement.classList.add("js");
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
// La raíz se obtiene del script compartido: funciona por HTTP y al abrir el HTML.
const siteRoot = new URL("../", document.currentScript.src);
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
const money = (value) =>
  new Intl.NumberFormat("es-EC", { style: "currency", currency: "USD" }).format(
    Number(value || 0),
  );
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const dates = (value) =>
  value
    ? new Intl.DateTimeFormat("es-EC", {
        dateStyle: "medium",
        timeZone: "America/Guayaquil",
      }).format(
        new Date(value.length === 10 ? `${value}T12:00:00-05:00` : value),
      )
    : "—";
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
  DEBITO: "Tarjeta de débito",
  CREDITO: "Tarjeta de crédito",
};
const events = {
  HORA: "Cancha por hora",
  CUMPLEANOS: "Cumpleaños",
  EVENTO: "Evento deportivo",
};
const detailList = (pairs) =>
  `<dl>${pairs.map(([key, value]) => `<div><dt>${esc(key)}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>`;

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

function showMessage(text, type = "error") {
  const host = $("#form-message") || $("#connection-message");
  if (!host) return;
  host.hidden = false;
  host.className = `notice ${type}`;
  host.textContent = text;
  if (host.id === "form-message") host.focus();
}
function clearMessage() {
  if ($("#form-message")) $("#form-message").hidden = true;
}
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
function loginHref() {
  const next =
    page === "home" ? pageHref("index.html") + location.search : location.href;
  return `${pageHref("iniciar_sesion.html")}?next=${encodeURIComponent(next)}`;
}
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

function formData(form) {
  const data = Object.fromEntries(new FormData(form));
  $$("input[type=checkbox]", form).forEach(
    (input) => (data[input.name] = input.checked),
  );
  return data;
}
function bindForm(id, action) {
  const form = $(id);
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage();
    if (form.dataset.busy === "true") return;
    const submit = $("[type=submit]", form);
    const label = submit.textContent;
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
      submit.textContent = label;
    }
  });
}
function needUser() {
  if (!session.usuario) {
    const error = new Error(
      "Primero inicia sesión o crea tu cuenta usando el enlace sobre el formulario.",
    );
    error.status = 401;
    throw error;
  }
}
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
function initTournaments() {
  if (!catalog) return;
  const open = catalog.torneos.filter(
    (t) =>
      t.abierto && t.fecha_inicio > catalog.hoy && Number(t.disponibles) > 0,
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
        : !next.abierto || next.fecha_inicio <= catalog.hoy
          ? "Inscripciones cerradas"
          : "Cupos completos";
      if (available) {
        $("#pasochoa-next-link").href = `${pageHref("pagos_torneos.html")}?torneo=${next.id}`;
      }
    } else {
      $("#pasochoa-next-status").textContent = "Inscripciones aún no disponibles";
    }
  }
}
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
function initSchool() {
  $("#summary-total").textContent = money(50);
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
function orderPairs(order) {
  const pairs = [
    ["Servicio", kinds[order.tipo]],
    ["Detalle", order.descripcion],
    ["Estado", order.estado === "PAGADA" ? "Confirmado" : "Pendiente de pago"],
  ];
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
  if (page === "confirmation") {
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
$$("input[name=metodo]").forEach((input) =>
  input.addEventListener("change", () => {
    $("#method-info").textContent =
      input.value === "TRANSFERENCIA"
        ? "Se registrará transferencia bancaria como método de pago de esta operación."
        : "Se registrará la tarjeta seleccionada como método de pago. No ingreses números de tarjeta ni CVV en esta página.";
  }),
);
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
          const href = pageHref(paid ? "confirmacion.html" : "pagos.html");
          return `<article class="history-item"><div><span class="tag ${paid ? "good" : "gold"}">${paid ? "Confirmado" : "Pendiente de pago"}</span><h3>${esc(o.descripcion)}</h3><p>${esc(kinds[o.tipo])} · ${esc(dates(o.creado_en))}</p></div><div class="history-price"><strong>${esc(money(o.monto))}</strong><div class="actions"><a class="btn small secondary" href="${href}?orden=${o.id}">${paid ? "Ver comprobante" : "Continuar al pago"}</a>${o.equipo_id && paid ? `<a class="text-link" href="${pageHref("mi_equipo.html")}?equipo=${o.equipo_id}">Gestionar equipo</a>` : ""}</div></div></article>`;
        })
        .join("")
    : `<div class="empty-state"><h3>Aquí comienza tu historia.</h3><p>No tienes operaciones en esta sección.</p><a class="btn" href="${pageHref("reservas.html")}">Explorar reservas</a></div>`;
}
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
            `<article class="panel"><h3>${esc(sc.alumno)} · ${esc(sc.categoria)}</h3><p class="small-text muted">${esc(sc.estado)} · ${sc.cuotas_pagadas} mensualidades pagadas · Último período: ${esc(dates(sc.ultimo_periodo))}</p><span class="tag ${sc.mes_actual_pagado ? "good" : "gold"}">${sc.mes_actual_pagado ? "Mes actual pagado" : "Mes actual pendiente"}</span>${sc.estado === "ACTIVA" ? `<form method="post" data-renew="${sc.id}"><div class="form-grid"><div class="field"><label for="period-${sc.id}">Período a pagar</label><input id="period-${sc.id}" name="periodo" type="month" value="${catalog.hoy.slice(0, 7)}" min="${sc.fecha_inscripcion.slice(0, 7)}" max="${nextMonth(catalog.hoy)}" required></div></div><div class="form-actions"><button type="submit" class="btn small">Pagar mensualidad · $50</button></div></form>` : '<p class="small-text muted">Completa el pago inicial desde tu actividad para activar la inscripción.</p>'}</article>`,
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
function nextMonth(day) {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() + 1);
  return d.toISOString().slice(0, 7);
}
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
function table(headers, rows, caption) {
  if (!rows.length)
    return '<div class="empty-state"><p>No hay registros para mostrar.</p></div>';
  return `<div class="table-wrap" tabindex="0" role="region" aria-label="${esc(caption)}"><table><caption>${esc(caption)}</caption><thead><tr>${headers.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
async function loadReports(filters = {}) {
  needUser();
  reportData = await api(`/admin/reports?${new URLSearchParams(filters)}`);
  $("#admin-content").hidden = false;
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
    ],
    reportData.reservas.map((r) => [
      r.titular,
      r.email,
      r.telefono,
      r.cancha,
      dates(r.inicio),
      `${times(r.inicio)}–${times(r.fin)}`,
      events[r.tipo_evento],
      r.estado,
      r.estado_pago === "PAGADA" ? "Registrado" : r.estado_pago,
      money(r.monto),
    ]),
    "Todas las reservas de la cancha, confirmadas o pendientes.",
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
    ["Importes registrados", money(reportData.resumen.ingresos)],
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
    ["Fecha", "Titular", "Servicio", "Método", "Monto"],
    reportData.pagos.map((p) => [
      dates(p.pagado_en),
      p.nombre,
      p.descripcion,
      methods[p.metodo],
      money(p.monto),
    ]),
    "Pagos registrados en el rango seleccionado.",
  );
  $("#school-report").innerHTML = table(
    [
      "Alumno",
      "Categoría",
      "Representante",
      "Cuotas pagadas",
      "Total",
      "Mes actual",
    ],
    reportData.escuela.map((s) => [
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
  // Neutraliza fórmulas al abrir CSV en una hoja de cálculo.
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

async function initialize() {
  if (location.protocol === "file:") return;
  const results = await Promise.allSettled([api("/session"), api("/catalog")]);
  if (results[0].status === "fulfilled") {
    session = results[0].value;
    updateSessionUI();
  }
  if (results[1].status === "fulfilled") catalog = results[1].value;
  const failure = results.find((r) => r.status === "rejected");
  if (failure) {
    showMessage(failure.reason.message);
    return;
  }
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
    if (page === "admin") await loadReports();
  } catch (error) {
    showMessage(error.message);
  }
}
const boot = initialize();
