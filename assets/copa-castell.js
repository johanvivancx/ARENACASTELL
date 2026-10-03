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
  if (upcoming && upcomingContainer) {
    const timeLabel = value => {
      const [hour, minute] = value.split(':').map(Number);
      return `${hour % 12 || 12}:${String(minute).padStart(2, '0')} ${hour >= 12 ? 'p. m.' : 'a. m.'}`;
    };
    for (const day of upcoming.days) {
      const dayCard = element('section');
      dayCard.className = 'mundial-upcoming-day';
      const heading = element('h4', day.label);
      dayCard.append(heading);
      const games = element('ol');
      games.className = 'mundial-upcoming-games';
      for (const [start, home, away] of day.matches) {
        const game = element('li');
        game.className = 'mundial-upcoming-game';
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
          if (country === home) matchup.append(element('span', 'vs'));
        }
        game.append(time, matchup);
        games.append(game);
      }
      dayCard.append(games);
      upcomingContainer.append(dayCard);
    }
    const rest = document.getElementById('mundial-proxima-descanso');
    if (rest && upcoming.bye) {
      rest.append(flag(upcoming.bye), element('strong', `Descansa ${upcoming.bye}`));
      const club = teams.get(upcoming.bye)?.club;
      if (club) rest.append(element('span', `(${club})`));
    }
  }
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
      card.append(element('span', `FECHA ${match.round} · FINALIZADO`), matchup);
      const score = element('p', `${match.homeGoals} – ${match.awayGoals}`);
      score.className = 'mundial-score';
      card.append(score);
      if (match.date) {
        const [year, month, day] = match.date.split('-');
        card.append(element('small', `${day}/${month}/${year}${match.time ? ' · ' + match.time : ''}`));
      }
      container.append(card);
    }
  };
  // Acumulados oficiales actualizados con las actas; el historial no vuelve a sumar resultados.
  const groups = document.getElementById('mundial-grupos');
  for (const [group, rows] of Object.entries(data.standings || {})) {
    const wrapper = element('div');
    wrapper.className = 'table-wrap mundial-standings';
    wrapper.tabIndex = 0;
    wrapper.setAttribute('role', 'region');
    wrapper.setAttribute('aria-label', `${group}: tabla de posiciones`);
    const table = element('table');
    table.append(element('caption', `${group} · Hasta la fecha ${data.throughRound}${data.partialRound ? " (parcial)" : ""}`));
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
    ['Egipto','92','Joseph Darío Sandoval Cantuña','egipto'],
    ['Colombia','5','Briones Carlos','colombia'],
    ['España','6','Maycol Vera','espana'],
    ['Noruega','10','Gregorio Arroyo','noruega'],
    ['Ecuador','9','Elvis Loachamin','ecuador'],
    ['Japón','9','Jhon Ñato','japon']
  ];
  for (const [country, number, name, file] of awards) {
    const card = element('figure');
    card.className = 'mundial-mvp-card';
    const link = element('a');
    link.href = `../assets/mvp-fecha5/${file}.jpeg`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.setAttribute('aria-label', `Ver foto completa de ${name} (nueva pestaña)`);
    const photo = element('img');
    photo.src = link.href;
    photo.alt = `${name}, jugador del partido de ${country}, fecha 5`;
    photo.loading = 'lazy';
    photo.width = 960;
    photo.height = 1280;
    link.append(photo);
    const caption = element('figcaption');
    caption.append(element('small', 'JUGADOR DEL PARTIDO · FECHA 5'), element('h4', `#${number} ${name}`));
    const selection = element('p');
    selection.className = 'mundial-player-identity';
    selection.append(flag(country), element('span', country));
    caption.append(selection);
    card.append(link, caption);
    document.getElementById('mundial-mvp').append(card);
  }
  round.addEventListener('change', matches);
  filter.addEventListener('change', scorers);
  matches();
  scorers();
})();
