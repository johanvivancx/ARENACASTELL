// Esta sección pública funciona también sin iniciar sesión ni conectar la base.
(() => {
  const data = window.CopaCastellData;
  const round = document.getElementById('mundial-fecha');
  if (!data || !round) return;
  const filter = document.getElementById('mundial-equipo-filtro');
  const element = (tag, text) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const teams = new Map(data.teams.map(team => [team.country, team]));
  const readableName = name => name === name.toLocaleUpperCase('es')
    ? name.toLocaleLowerCase('es').replace(/(^|\s)(\p{L})/gu, (_, space, letter) => space + letter.toLocaleUpperCase('es'))
    : name;
  const flags = {'Argentina':'ar','Brasil':'br','Cabo Verde':'cv','Colombia':'co','Ecuador':'ec','Egipto':'eg','Francia':'fr','Alemania':'de','Japón':'jp','Marruecos':'ma','Noruega':'no','Portugal':'pt','España':'es','Uruguay':'uy','Venezuela':'ve'};
  const stageLabels = {FASE1: 'Primera fase', GRUPO_A: 'Fase 2 · Grupo 1',
    GRUPO_B: 'Fase 2 · Grupo 2', BRONCE: 'Copa Bronce · grupo único', ORO: 'Copa Oro', PLATA: 'Copa Plata'};
  const flag = country => {
    const image = element('img');
    image.src = `../assets/banderas/${flags[country]}.png`;
    image.alt = '';
    image.className = 'mundial-flag';
    image.width = 48;
    image.height = 32;
    return image;
  };
  const upcoming = data.upcoming;
  const upcomingContainer = document.getElementById('mundial-proxima-partidos');
  const renderUpcoming = () => {
    if (!upcomingContainer) return;
    upcomingContainer.replaceChildren();
    const future = (data.matches || []).filter(match =>
      match.date && match.time && ['scheduled', 'rescheduled', 'live'].includes(match.status));
    future.sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`));
    const days = [];
    for (const match of future) {
      let day = days.find(item => item.date === match.date);
      if (!day) {
        day = {date: match.date, label: new Date(`${match.date}T12:00:00`).toLocaleDateString('es-EC',
          {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'}), matches: []};
        days.push(day);
      }
      day.matches.push(match);
    }
    const title = document.getElementById('proxima-fecha-title');
    if (title) title.textContent = days.length
      ? `Próximos partidos · Fecha ${Math.max(...future.map(match => match.round))}`
      : 'Próximos partidos';
    const timeLabel = value => {
      const [hour, minute] = value.split(':').map(Number);
      return `${hour % 12 || 12}:${String(minute).padStart(2, '0')} ${hour >= 12 ? 'p. m.' : 'a. m.'}`;
    };
    for (const day of days) {
      const dayCard = element('section');
      dayCard.className = 'mundial-upcoming-day';
      const heading = element('h4', day.label);
      dayCard.append(heading);
      const games = element('ol');
      games.className = 'mundial-upcoming-games';
      for (const match of day.matches) {
        const {home, away} = match;
        const start = match.time;
        const game = element('li');
        game.className = 'mundial-upcoming-game';
        if (match?.status === 'live') game.classList.add('is-live');
        const time = element('time', timeLabel(start));
        time.dateTime = `${day.date}T${start}:00-05:00`;
        const matchup = element('div');
        matchup.className = 'mundial-upcoming-matchup';
        for (const country of [home, away]) {
          const side = element('div');
          side.className = 'mundial-upcoming-team';
          const names = element('span');
          names.append(element('strong', country), element('small', teams.get(country)?.club || ''));
          side.append(flag(country), names);
          matchup.append(side);
          if (country === home) matchup.append(element('span', match?.status === 'live' ? `${match.homeGoals} – ${match.awayGoals}` : 'vs'));
        }
        game.append(time, matchup);
        if (match.stage && match.stage !== 'FASE1') game.append(element('small', stageLabels[match.stage] || match.stage));
        if (match?.status === 'live') game.append(element('strong', 'EN JUEGO'));
        games.append(game);
      }
      if (games.children.length) {
        dayCard.append(games);
        upcomingContainer.append(dayCard);
      }
    }
    if (!future.length) upcomingContainer.append(element('p', 'No hay partidos pendientes programados. Consulta los marcadores en Resultados.'));
    const rest = document.getElementById('mundial-proxima-descanso');
    if (rest) rest.hidden = !future.length || !upcoming?.bye || future.some(match => match.round !== upcoming.round);
    if (rest && upcoming.bye && !rest.children.length) {
      const byes = Array.isArray(upcoming.bye) ? upcoming.bye : [upcoming.bye];
      rest.append(element('strong', byes.length > 1 ? 'Descansan:' : 'Descansa:'));
      for (const country of byes) {
        const club = teams.get(country)?.club;
        rest.append(flag(country), element('span', `${country}${club ? ` (${club})` : ''}`));
      }
    }
  };
  renderUpcoming();
  const matches = () => {
    const container = document.getElementById('mundial-partidos');
    container.replaceChildren();
    const selected = data.matches.filter(match => match.round === Number(round.value));
    if (!selected.length) {
      container.append(element('p', 'Los resultados de esta fecha todavía no están publicados.'));
      return;
    }
    for (const match of selected) {
      const card = element('article');
      card.className = 'mundial-match';
      const matchup = element('div');
      matchup.className = 'mundial-matchup';
      for (const country of [match.home, match.away]) {
        const side = element('div');
        side.className = 'mundial-side';
        side.append(flag(country), element('h4', country), element('small', teams.get(country).club));
        matchup.append(side);
      }
      const suspended = match.status === 'suspended';
      const pending = match.status === 'rescheduled' || match.status === 'scheduled';
      const live = match.status === 'live';
      if (live) card.classList.add('is-live');
      card.append(element('span', `FECHA ${match.round} · ${stageLabels[match.stage || 'FASE1']} · ${live ? 'EN JUEGO' : pending ? 'PENDIENTE' : suspended ? 'SUSPENDIDO' : 'FINALIZADO'}`), matchup);
      const score = element('p', pending ? 'Pendiente de jugar' : suspended ? 'Esperando decisión' : `${match.homeGoals} – ${match.awayGoals}`);
      score.className = suspended || pending ? 'mundial-match-status' : 'mundial-score';
      card.append(score);
      if (live && match.updatedAt) card.append(element('small', `Marcador actualizado a las ${new Date(match.updatedAt).toLocaleTimeString('es-EC', {timeZone: 'America/Guayaquil', hour: '2-digit', minute: '2-digit'})}`));
      if (match.goleadores_pendientes) card.append(element('small', `${match.goleadores_pendientes} goles por atribuir a jugadores`));
      if (match.date) {
        const [year, month, day] = match.date.split('-');
        card.append(element('small', `${day}/${month}/${year}${match.time ? ' · ' + match.time : ''}`));
      }
      container.append(card);
    }
  };
  // La API suma partidos nuevos a los acumulados oficiales de la fecha 6.
  const groups = document.getElementById('mundial-grupos');
  const renderStandings = () => {
    groups.replaceChildren();
    for (const [group, rows] of Object.entries(data.standings || {})) {
    const wrapper = element('div');
    wrapper.className = 'table-wrap mundial-standings';
    wrapper.tabIndex = 0;
    wrapper.setAttribute('role', 'region');
    wrapper.setAttribute('aria-label', `${group}: tabla de posiciones`);
    const table = element('table');
    table.append(element('caption', `${group.toUpperCase()} - FASE 1 FINALIZADA · GRUPOS DEFINIDOS`));
    const head = element('thead');
    const titles = element('tr');
    ['#', 'Selección / equipo', 'Pts', 'PJ', 'DG', 'PG', 'PE', 'PP', 'GF', 'GC'].forEach((label, index) => {
      const cell = element('th', label);
      cell.scope = 'col';
      if (index > 4) cell.className = 'mundial-extra-stat';
      titles.append(cell);
    });
    head.append(titles);
    table.append(head);
    const body = element('tbody');
    for (const [country, pts, pj, pg, pe, pp, gf, gc, dg, position] of rows) {
      const row = element('tr');
      row.append(element('td', position));
      const team = element('th');
      team.scope = 'row';
      const identity = element('span');
      identity.className = 'mundial-player-identity';
      const names = element('span');
      names.append(element('strong', country), element('small', teams.get(country).club));
      identity.append(flag(country), names);
      team.append(identity);
      row.append(team);
      [pts, pj, dg > 0 ? `+${dg}` : dg, pg, pe, pp, gf, gc].forEach((value, index) => {
        const cell = element('td', value);
        cell.dataset.stat = ['Puntos', 'Jugados', 'Dif. goles', 'Ganados', 'Empatados', 'Perdidos', 'Goles a favor', 'Goles en contra'][index];
        if (index === 0) cell.className = 'mundial-points';
        if (index > 2) cell.className = 'mundial-extra-stat';
        row.append(cell);
      });
      body.append(row);
    }
    table.append(body);
    wrapper.append(table);
      groups.append(wrapper);
    }
  };
  const renderFormat = () => {
    const format = data.format;
    if (!format?.groups) return;
    const labels = {A: 'Fase 2 · Grupo 1', B: 'Fase 2 · Grupo 2', BRONCE: 'Copa Bronce · grupo único'};
    const codes = {A: ['A1', 'B2', 'A3', 'B4'],
      B: ['B1', 'A2', 'B3', 'A4', 'B5'],
      BRONCE: ['A5', 'A6', 'A7', 'B6', 'B7', 'B8']};
    const groupHost = document.getElementById('copa-format-groups');
    const tablesHost = document.getElementById('copa-format-standings');
    const cupsHost = document.getElementById('copa-format-cups');
    if (!groupHost || !tablesHost || !cupsHost) return;
    const liveHost = document.getElementById('copa-format-live');
    if (liveHost) liveHost.hidden = !format.groupsConfirmed;
    groupHost.replaceChildren();
    tablesHost.replaceChildren();
    cupsHost.replaceChildren();
    if (!format.groupsConfirmed) return;
    for (const code of ['A', 'B', 'BRONCE']) {
      const group = format.groups[code];
      const countries = Array.isArray(group) ? group : group.teams;
      const card = element('article');
      card.className = `copa-format-group copa-format-${code.toLowerCase()}`;
      card.append(element('h4', labels[code]));
      const list = element('ol');
      countries.forEach((country, index) => {
        const item = element('li');
        item.append(element('b', codes[code][index]), flag(country));
        const name = element('span');
        name.append(element('strong', country), element('small', teams.get(country)?.club || ''));
        item.append(name);
        list.append(item);
      });
      card.append(list);
      card.append(element('p', code === 'A' ? 'Todos contra todos · 3 fechas.'
        : code === 'B' ? 'Todos contra todos · 4 partidos por equipo; calendario por anunciar.'
          : 'Todos contra todos · 5 fechas.'));
      groupHost.append(card);
      if (Array.isArray(group) || group.standings) {
        const initial = Array.isArray(group);
        const rows = initial ? group.map(country => [country, Number(format.bonuses?.[country] || 0), 0, 0, 0, 0, 0, 0, 0, 0]) : group.standings;
        if (initial) rows.sort((a, b) => b[1] - a[1]).forEach((row, index) => { row[9] = index + 1; });
        const finished = initial ? 0 : group.finished;
        const wrap = element('div');
        wrap.className = 'table-wrap copa-format-table';
        wrap.tabIndex = 0;
        wrap.setAttribute('role', 'region');
        wrap.setAttribute('aria-label', `Tabla de ${labels[code]}`);
        const table = element('table');
        table.append(element('caption', `${labels[code]} · ${finished} partido${finished === 1 ? '' : 's'} finalizado${finished === 1 ? '' : 's'}${!initial && group.complete ? ' · fase completa' : ''}`));
        const thead = element('thead');
        const headers = element('tr');
        ['Puesto', 'Equipo', 'Pts', 'PJ', 'DG', 'GF', 'GC'].forEach(label => { const th = element('th', label); th.scope = 'col'; headers.append(th); });
        thead.append(headers);
        table.append(thead);
        const tbody = element('tbody');
        rows.forEach(row => {
          const tr = element('tr');
          tr.append(element('td', row[2] === 0 && row[1] === 0 ? '—' : row[9] || '—'));
          const identity = element('td');
          identity.append(flag(row[0]), element('span', `${row[0]} · ${teams.get(row[0])?.club || ''}`));
          const bonus = Number(format.bonuses?.[row[0]] || 0);
          tr.append(identity, element('td', row[1]), element('td', row[2]), element('td', row[8] > 0 ? `+${row[8]}` : row[8]),
            element('td', row[6]), element('td', row[7]));
          if (bonus) tr.classList.add('has-bonus');
          tbody.append(tr);
        });
        table.append(tbody);
        wrap.append(table);
        tablesHost.append(wrap);
      }
    }
    const confirmed = format.semifinalistsConfirmed;
    cupsHost.hidden = !confirmed;
    const status = document.getElementById('copa-format-status');
    if (status) {
      status.textContent = confirmed
        ? 'La nueva fase terminó: los clasificados para Oro y Plata ya se pueden anunciar.'
        : format.tiePendingReview
          ? 'La nueva fase terminó con un empate que requiere revisión de la organización antes de anunciar semifinalistas.'
          : '';
      status.hidden = !status.textContent;
    }
    for (const cup of ['ORO', 'PLATA']) {
      const card = element('article');
      card.className = `copa-format-cup copa-format-${cup.toLowerCase()}`;
      card.append(element('h4', `Copa ${cup === 'ORO' ? 'Oro' : 'Plata'}`));
      const qualified = confirmed ? format.qualified[cup] : [];
      card.append(element('p', qualified.length
        ? `Clasificados: ${qualified.join(' · ')}`
        : 'Clasificados por definir después de jugar la nueva fase.'));
      cupsHost.append(card);
    }
  };
  const scorers = () => {
    const body = document.getElementById('mundial-goleadores-filas');
    body.replaceChildren();
    data.scorers.slice(0, 20).forEach((player, index) => {
      if (filter.value && filter.value !== player.country) return;
      const row = element('tr');
      const club = teams.get(player.country)?.club || '';
      row.append(element('td', `#${index + 1}`));
      const name = element('td');
      const identity = element('span');
      identity.className = 'mundial-player-identity';
      identity.append(flag(player.country), element('span', player.name));
      name.append(identity);
      row.append(name);
      for (const [label, value] of [['Equipo', `${player.country} · ${club}`], ['Dorsal', player.number], ['Goles', player.goals]]) {
        const cell = element('td', value);
        cell.dataset.label = label;
        row.append(cell);
      }
      body.append(row);
    });
    if (!body.children.length) {
      const row = element('tr');
      const cell = element('td', 'Esta selección no tiene jugadores en el Top 20 actual.');
      cell.colSpan = 5;
      row.append(cell);
      body.append(row);
    }
  };
  for (const team of data.teams) {
    const option = element('option', `${team.country} · ${team.club}`);
    option.value = team.country;
    filter.append(option);
    const details = element('details');
    details.dataset.search = `${team.country} ${team.club} ${team.players.map(player => player.name).join(' ')}`;
    const summary = element('summary');
    const heading = element('span');
    heading.className = 'mundial-team-heading';
    heading.append(element('strong', team.country), element('span', team.club), element('small', `${team.players.length} jugadores · Ver plantilla`));
    const arrow = element('span', '+');
    arrow.className = 'mundial-team-arrow';
    arrow.setAttribute('aria-hidden', 'true');
    summary.append(flag(team.country), heading, arrow);
    details.append(summary);
    const list = element('ul');
    for (const player of team.players) {
      const item = element('li');
      const number = element('span', player.number ? `#${player.number}` : '');
      number.className = 'mundial-number';
      item.append(number, element('span', readableName(player.name)));
      list.append(item);
    }
    details.append(list);
    document.getElementById('mundial-plantillas').append(details);
  }
  const search = document.getElementById('mundial-buscar-equipo');
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es');
  search.addEventListener('input', () => {
    let visible = 0;
    for (const card of document.querySelectorAll('.mundial-rosters details')) {
      card.hidden = !normalize(card.dataset.search).includes(normalize(search.value.trim()));
      if (!card.hidden) visible++;
    }
    document.getElementById('mundial-busqueda-estado').textContent = visible === 1 ? '1 selección disponible' : visible ? `${visible} selecciones disponibles` : 'No se encontraron equipos o jugadores con ese nombre.';
  });
  const awards = [
    ['Marruecos','9','Juan Diego Bustillos Paucar','marruecos'],
    ['Japón','13','Sebastián Taipe','japon'],
    ['Ecuador','9','Elvis Loachamin','ecuador'],
    ['Noruega','9','Romario Betancourt','noruega'],
    ['Egipto','88','Kleber Sebastián Aulestia Ramos','egipto'],
    ['Francia','7','Abdías Méndez','francia']
  ];
  const renderAward = (container, {country, number, name, photo_url, round}) => {
    const card = element('figure');
    card.className = 'mundial-mvp-card';
    const link = element('a');
    link.href = photo_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.setAttribute('aria-label', `Ver foto completa de ${name} (nueva pestaña)`);
    const photo = element('img');
    photo.src = link.href;
    photo.alt = `${name}, jugador del partido de ${country}, fecha ${round}`;
    photo.loading = 'lazy';
    photo.width = 960;
    photo.height = 1280;
    link.append(photo);
    const caption = element('figcaption');
    caption.append(element('small', `JUGADOR DEL PARTIDO · FECHA ${round}`), element('h4', `${number ? `#${number} ` : ''}${name}`));
    const selection = element('p');
    selection.className = 'mundial-player-identity';
    selection.append(flag(country), element('span', country));
    caption.append(selection);
    card.append(link, caption);
    container.append(card);
  };
  const renderAwards = () => {
    const current = document.getElementById('mundial-mvp');
    current.replaceChildren();
    for (const award of data.mvps || []) renderAward(current, award);
  };
  for (const [country, number, name, file] of awards) {
    renderAward(document.getElementById('mundial-mvp-history'),
      {country, number, name, photo_url: `../assets/mvp-fecha6/${file}.jpeg`, round: 6});
  }
  renderAwards();
  round.addEventListener('change', matches);
  round.addEventListener('change', () => { round.dataset.touched = 'true'; });
  filter.addEventListener('change', scorers);
  renderStandings();
  renderFormat();
  matches();
  scorers();
  let refreshing = false;
  const refresh = async () => {
    if (refreshing) return;
    refreshing = true;
    try {
      const response = await fetch('/api/copa-castell', {cache: 'no-store'});
      if (!response.ok) return;
      const live = await response.json();
      Object.assign(data, live);
      const rounds = [...new Set(live.matches.map(match => match.round))].sort((a, b) => a - b);
      for (const value of rounds) {
        if (![...round.options].some(option => Number(option.value) === value))
          round.append(new Option(`Fecha ${value}`, String(value)));
      }
      if (!round.dataset.touched) round.value = String(Math.max(...rounds));
      document.getElementById('posiciones-actualizacion').textContent = `Primera fase: ${live.firstPhaseNote}. Estas tablas se conservan como historial; arriba está la clasificación vigente de la fase 2.`;
      document.getElementById('goleadores-actualizacion').textContent = live.goleadoresPendientes
        ? `Top 20 actualizado. Hay ${live.goleadoresPendientes} goles de partidos publicados aún sin atribuir a jugadores.`
        : 'Top 20 actualizado con los goleadores registrados de todos los partidos publicados.';
      document.getElementById('goleadores-caption').textContent = `Top 20 de goleadores · fecha ${live.throughRound}`;
      renderStandings();
      renderFormat();
      matches();
      renderUpcoming();
      scorers();
      renderAwards();
    } catch {
      // Conserva la información histórica cuando el servicio no está disponible.
    } finally {
      refreshing = false;
    }
  };
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 15000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
