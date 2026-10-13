"""Resultados de Copa Castell posteriores a la línea base pública de la fecha 6."""

from copy import deepcopy
from functools import lru_cache
import base64
import binascii
from io import BytesIO
import json
import re
import unicodedata
from datetime import date, time
from PIL import Image, ImageOps, UnidentifiedImageError

from db import ROOT
from models import ErrorValidacion
from services import HTTPError, exigir_administrador, numero, texto


def _normalizar(value):
    return "".join(c for c in unicodedata.normalize("NFD", value.casefold()) if not unicodedata.combining(c)).strip()


@lru_cache(maxsize=1)
def base():
    source = (ROOT / "assets/copa-castell-datos.js").read_text(encoding="utf8").strip()
    prefix = "window.CopaCastellData = "
    if not source.startswith(prefix) or not source.endswith(";"):
        raise RuntimeError("No se pudo leer la línea base de Copa Castell.")
    return json.loads(source[len(prefix):-1])


@lru_cache(maxsize=1)
def catalogo():
    data = base()
    fixtures = {}
    postponed = {}
    for match in data["matches"]:
        if match.get("status") in {"rescheduled", "suspended"}:
            key = f'{match["round"]}:{match["home"]}:{match["away"]}'
            fixtures[key] = {"id": key, **match}
            postponed[(match["home"], match["away"])] = key
    for day in data["upcoming"]["days"]:
        for time, home, away in day["matches"]:
            key = postponed.get((home, away)) or f'{data["upcoming"]["round"]}:{home}:{away}'
            if key in fixtures:
                fixtures[key] = {**fixtures[key], "date": day["date"], "time": time}
            else:
                fixtures[key] = {"id": key, "round": data["upcoming"]["round"],
                                 "home": home, "away": away, "date": day["date"],
                                 "time": time, "status": "scheduled"}
    players = {}
    for team in data["teams"]:
        country = team["country"]
        current = []
        baseline = [(index, p) for index, p in enumerate(data["scorers"]) if p["country"] == country]
        for index, player in baseline:
            current.append({"id": f"s:{index}", "name": player["name"],
                            "number": player["number"], "country": country})
        for index, player in enumerate(team["players"]):
            number = str(player.get("number") or "")
            same_name = any(_normalizar(p["name"]) == _normalizar(player["name"]) for _, p in baseline)
            same_number = number and sum(p.get("number") == number for p in team["players"]) == 1 \
                and any(p.get("number") == number for _, p in baseline)
            if not (same_name or same_number):
                current.append({"id": f"r:{country}:{index}", "name": player["name"],
                                "number": number, "country": country})
        players[country] = sorted(current, key=lambda p: (int(p["number"]) if p["number"].isdigit() else 999, p["name"]))
    return fixtures, players


ETAPAS = {"FASE1", "GRUPO_A", "GRUPO_B", "BRONCE", "ORO", "PLATA"}
PARTIDOS_GRUPO = {"A": 6, "B": 10, "BRONCE": 15}


def formato_actual(matches):
    """La nueva fase empieza en cero; solo sus finales alimentan sus tablas."""
    rules = base()["format"]
    groups = {}
    for code in ("A", "B", "BRONCE"):
        stage = "BRONCE" if code == "BRONCE" else f"GRUPO_{code}"
        games = [m for m in matches if m.get("stage") == stage]
        final = [m for m in games if m.get("status") in ("final", "finalizado")]
        bonus = rules["bonuses"] if code != "BRONCE" else {}
        rows = calcular_posiciones(final, {code: [[team] for team in rules["groups"][code]]}, bonus)[code]
        needed = PARTIDOS_GRUPO.get(code)
        complete = bool(rules.get("groupsConfirmed") and needed and len(games) == needed and len(final) == needed)
        groups[code] = {"teams": rules["groups"][code], "standings": rows,
                        "finished": len(final), "scheduled": len(games), "complete": complete}
    qualified = {"ORO": [], "PLATA": []}
    def unresolved_boundary(rows, left, right):
        # Un empate deportivo completo no se decide por orden alfabético.
        return all(rows[left][index] == rows[right][index] for index in (1, 8, 6, 7))
    ties = False
    if groups["A"]["complete"] and groups["B"]["complete"]:
        ties = (unresolved_boundary(groups["A"]["standings"], 1, 2)
                or unresolved_boundary(groups["B"]["standings"], 1, 2)
                or unresolved_boundary(groups["B"]["standings"], 3, 4))
    if groups["A"]["complete"] and groups["B"]["complete"] and not ties:
        for cup, positions in rules["qualification"].items():
            qualified[cup] = [groups[code]["standings"][position - 1][0]
                              for code in ("A", "B") for position in positions]
    return {"groups": groups, "groupsConfirmed": bool(rules.get("groupsConfirmed")), "qualified": qualified,
            "semifinalistsConfirmed": bool(qualified["ORO"] and qualified["PLATA"]),
            "tiePendingReview": bool(ties and groups["A"]["complete"] and groups["B"]["complete"]),
            "expectedMatches": PARTIDOS_GRUPO}


def partidos(conn):
    """Une los partidos históricos programados con los añadidos desde administración."""
    fixtures = dict(catalogo()[0])
    for row in conn.execute(
        """SELECT id,fecha,etapa,local,visitante,dia,hora
           FROM copa_partidos_programados ORDER BY dia,hora,id"""
    ).fetchall():
        key = f'admin:{row["id"]}'
        fixtures[key] = {"id": key, "round": row["fecha"], "stage": row["etapa"], "home": row["local"],
                         "away": row["visitante"], "date": row["dia"].isoformat(),
                         "time": row["hora"].strftime("%H:%M"), "status": "scheduled"}
    return fixtures


def programar_partido(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    round_number = numero(data.get("round"), "Fecha del torneo", 7, 30)
    home, away = str(data.get("home", "")), str(data.get("away", ""))
    stage = str(data.get("stage", "FASE1"))
    if stage not in ETAPAS:
        raise ErrorValidacion("Selecciona una etapa válida de la Copa.")
    known = catalogo()[1]
    if home not in known or away not in known or home == away:
        raise ErrorValidacion("Selecciona dos selecciones distintas de la Copa Castell.")
    pools = base()["format"]["groups"]
    if stage in {"GRUPO_A", "GRUPO_B", "BRONCE"}:
        if not base()["format"].get("groupsConfirmed"):
            raise ErrorValidacion("Primero confirma y registra los grupos de la fase 2 antes de programar sus partidos.")
        pool = pools["BRONCE" if stage == "BRONCE" else stage[-1]]
        if home not in pool or away not in pool:
            raise ErrorValidacion("Los dos equipos deben pertenecer al grupo de la etapa seleccionada.")
    if stage in {"ORO", "PLATA"}:
        public = estado_publico(conn)
        if not public["format"]["semifinalistsConfirmed"]:
            raise ErrorValidacion("Termina primero las dos tablas de la nueva fase antes de programar finales.")
        if home not in public["format"]["qualified"][stage] or away not in public["format"]["qualified"][stage]:
            raise ErrorValidacion("Estos equipos no están clasificados para la copa seleccionada.")
    raw_date, raw_time = str(data.get("date", "")), str(data.get("time", ""))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date) or not re.fullmatch(r"\d{2}:\d{2}", raw_time):
        raise ErrorValidacion("Indica el día y la hora del partido.")
    try:
        day, start = date.fromisoformat(raw_date), time.fromisoformat(raw_time)
    except ValueError:
        raise ErrorValidacion("La fecha u hora del partido no es válida.") from None
    if any({f["home"], f["away"]} == {home, away} and
           (f["round"] == round_number or
            (stage in {"GRUPO_A", "GRUPO_B"} and f.get("stage") == stage))
           for f in partidos(conn).values()):
        raise ErrorValidacion("Ese encuentro ya está programado en la fecha seleccionada.")
    created = conn.execute(
        """INSERT INTO copa_partidos_programados(fecha,etapa,local,visitante,dia,hora,creado_por)
           VALUES(%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (fecha,local,visitante) DO NOTHING RETURNING id""",
        (round_number, stage, home, away, day, start, admin_uid),
    ).fetchone()
    if not created:
        raise ErrorValidacion("Ese partido ya fue programado.")
    return {"fixture_id": f'admin:{created["id"]}',
            "message": f'Partido de {stage} programado para la fecha {round_number}: {home}–{away}.'}


def _resultados(conn):
    results = conn.execute(
        """SELECT fixture_id,goles_local,goles_visitante,estado,revision,actualizado_en
           FROM copa_resultados ORDER BY actualizado_en,fixture_id"""
    ).fetchall()
    goals = conn.execute(
        """SELECT fixture_id,equipo,jugador_clave,jugador_nombre,dorsal,goles
           FROM copa_goles ORDER BY fixture_id,equipo,jugador_clave"""
    ).fetchall()
    by_match = {row["fixture_id"]: [] for row in results}
    for goal in goals:
        by_match[goal["fixture_id"]].append(goal)
    return results, by_match


def jugadores_del_partido(conn):
    """Combina los destacados incluidos en el sitio con las fotos publicadas después."""
    awards = {row["fixture_id"]: dict(row) for row in base().get("mvps", [])}
    fixtures = partidos(conn)
    for row in conn.execute(
        """SELECT id,fixture_id,equipo,jugador_clave,jugador_nombre,dorsal,actualizado_en
           FROM copa_mvp ORDER BY actualizado_en,id"""
    ).fetchall():
        fixture = fixtures.get(row["fixture_id"])
        if not fixture:
            continue
        awards[row["fixture_id"]] = {
            "fixture_id": row["fixture_id"], "round": fixture["round"],
            "country": row["equipo"], "player_id": row["jugador_clave"],
            "name": row["jugador_nombre"], "number": row["dorsal"],
            "photo_url": f'/api/copa-mvp/photos/{row["id"]}?v={int(row["actualizado_en"].timestamp() * 1_000_000)}',
        }
    return sorted(awards.values(), key=lambda award: (-award["round"], award["fixture_id"]))


def foto_jugador_del_partido(conn, photo_id):
    row = conn.execute("SELECT foto FROM copa_mvp WHERE id=%s", (photo_id,)).fetchone()
    if not row:
        raise HTTPError(404, "Foto no encontrada.")
    return bytes(row["foto"])


def guardar_jugador_del_partido(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    fixtures, players = partidos(conn), catalogo()[1]
    fixture = fixtures.get(str(data.get("fixture_id", "")))
    if not fixture:
        raise ErrorValidacion("Selecciona un partido programado.")
    if not conn.execute("SELECT 1 FROM copa_resultados WHERE fixture_id=%s AND estado='FINALIZADO'", (fixture["id"],)).fetchone():
        raise ErrorValidacion("Publica primero el resultado final de este partido.")
    country = str(data.get("country", ""))
    if country not in (fixture["home"], fixture["away"]):
        raise ErrorValidacion("Selecciona una de las dos selecciones del partido.")
    player = next((p for p in players[country] if p["id"] == str(data.get("player_id", ""))), None)
    if not player:
        raise ErrorValidacion("Selecciona un jugador de la plantilla de esa selección.")
    encoded = data.get("image")
    if not isinstance(encoded, str) or len(encoded) > 8_000_000:
        raise ErrorValidacion("Selecciona una foto JPG, PNG o WebP de hasta 5 MB.")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not 1 <= len(raw) <= 5_000_000:
            raise ValueError("Tamaño no permitido")
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 24_000_000:
                raise ValueError("Formato o dimensiones no permitidos")
            photo = ImageOps.exif_transpose(source).convert("RGB")
            photo.thumbnail((1600, 2000), Image.Resampling.LANCZOS)
            output = BytesIO()
            photo.save(output, format="JPEG", quality=82, optimize=True)
        jpeg = output.getvalue()
        if len(jpeg) > 2_097_152:
            raise ValueError("Foto procesada demasiado grande")
    except (ValueError, binascii.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise ErrorValidacion("La foto no es válida. Usa JPG, PNG o WebP de hasta 5 MB.") from None
    conn.execute(
        """INSERT INTO copa_mvp(fixture_id,equipo,jugador_clave,jugador_nombre,dorsal,foto,registrado_por)
           VALUES(%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (fixture_id) DO UPDATE SET
             equipo=EXCLUDED.equipo,jugador_clave=EXCLUDED.jugador_clave,
             jugador_nombre=EXCLUDED.jugador_nombre,dorsal=EXCLUDED.dorsal,
             foto=EXCLUDED.foto,registrado_por=EXCLUDED.registrado_por,
             actualizado_en=current_timestamp""",
        (fixture["id"], country, player["id"], player["name"], player["number"], jpeg, admin_uid),
    )
    return {"message": f'Jugador del partido publicado: {player["name"]} · {country}.'}


def calcular_posiciones(matches, groups, bonuses=None):
    """Recalcula desde cero; no arrastra puntos de tablas guardadas anteriormente."""
    standings = {
        group: [[row[0], 0, 0, 0, 0, 0, 0, 0, 0, 0] for row in rows]
        for group, rows in groups.items()
    }
    lookup = {row[0]: row for rows in standings.values() for row in rows}
    for match in matches:
        if match.get("status") not in (None, "final", "finalizado"):
            continue
        home, away = match.get("homeGoals"), match.get("awayGoals")
        if type(home) is not int or type(away) is not int or home < 0 or away < 0:
            continue
        for country, scored, received in ((match["home"], home, away),
                                          (match["away"], away, home)):
            row = lookup.get(country)
            if row is None:
                continue
            row[2] += 1
            row[3] += scored > received
            row[4] += scored == received
            row[5] += scored < received
            row[6] += scored
            row[7] += received
    for rows in standings.values():
        for row in rows:
            row[1] = row[3] * 3 + row[4] + (bonuses or {}).get(row[0], 0)
            row[8] = row[6] - row[7]
        # Nombre solo estabiliza la presentación; no es un desempate deportivo.
        rows.sort(key=lambda row: (-row[1], -row[8], -row[6], _normalizar(row[0])))
        for position, row in enumerate(rows, 1):
            row[9] = position
    return standings


def estado_publico(conn):
    data = base()
    fixtures = partidos(conn)
    results, goals = _resultados(conn)
    by_id = {row["fixture_id"]: row for row in results}
    matches = deepcopy(data["matches"])
    for match in matches:
        key = f'{match["round"]}:{match["home"]}:{match["away"]}'
        if key in fixtures:
            match["id"] = key
    for key, fixture in fixtures.items():
        if not any(m.get("id") == key for m in matches):
            matches.append(deepcopy(fixture))
    for match in matches:
        match.setdefault("stage", "FASE1")
    scorers = deepcopy(data["scorers"])
    added_scorers = {}
    pending = 0
    for match in matches:
        result = by_id.get(match.get("id"))
        if not result:
            continue
        home, away = result["goles_local"], result["goles_visitante"]
        finished = result["estado"] == "FINALIZADO"
        match.update({"homeGoals": home, "awayGoals": away, "status": "final" if finished else "live",
                      "revision": result["revision"], "updatedAt": result["actualizado_en"].isoformat()})
        if not finished:
            continue
        scored_goals = goals.get(match["id"], [])
        missing = home + away - sum(g["goles"] for g in scored_goals)
        match["goleadores_pendientes"] = missing
        pending += missing
        for goal in scored_goals:
            key = goal["jugador_clave"]
            if key.startswith("s:"):
                scorers[int(key[2:])]["goals"] += goal["goles"]
            else:
                if key not in added_scorers:
                    added_scorers[key] = {"name": goal["jugador_nombre"], "number": goal["dorsal"],
                                          "country": goal["equipo"], "goals": 0}
                added_scorers[key]["goals"] += goal["goles"]
    standings = calcular_posiciones([m for m in matches if m["stage"] == "FASE1"], data["standings"])
    current_format = formato_actual(matches)
    scorers.extend(added_scorers.values())
    scorers.sort(key=lambda row: -row["goals"])
    round_seven = [f for f in fixtures.values() if f["round"] == 7]
    finished_seven = sum(by_id.get(f["id"], {}).get("estado") == "FINALIZADO" for f in round_seven)
    live_seven = sum(by_id.get(f["id"], {}).get("estado") == "EN_JUEGO" for f in round_seven)
    postponed = [f for f in fixtures.values() if f["round"] == 6]
    finished_postponed = sum(by_id.get(f["id"], {}).get("estado") == "FINALIZADO" for f in postponed)
    live_postponed = sum(by_id.get(f["id"], {}).get("estado") == "EN_JUEGO" for f in postponed)
    through_round = 7 if finished_seven or live_seven else 6
    if through_round == 7:
        note = f"Fecha 7: {finished_seven} de {len(round_seven)} partidos finalizados"
        if live_seven:
            note += f"; {live_seven} en juego"
        partial = finished_seven < len(round_seven) or finished_postponed < len(postponed)
        if finished_postponed < len(postponed):
            note += "; Alemania–Venezuela de la fecha 6 " + ("en juego" if live_postponed else "pendiente")
    else:
        partial = finished_postponed < len(postponed)
        note = ("Alemania–Venezuela de la fecha 6 en juego" if live_postponed else data["roundNote"]) if partial else "Fecha 6 completa"
    first_phase_round, first_phase_note = through_round, note
    later = [f for f in fixtures.values() if f["round"] > 7 and
             by_id.get(f["id"], {}).get("estado") in {"EN_JUEGO", "FINALIZADO"}]
    if later:
        through_round = max(f["round"] for f in later)
        current = [f for f in fixtures.values() if f["round"] == through_round]
        finished = sum(by_id.get(f["id"], {}).get("estado") == "FINALIZADO" for f in current)
        live = sum(by_id.get(f["id"], {}).get("estado") == "EN_JUEGO" for f in current)
        partial = finished < len(current)
        note = f"Fecha {through_round}: {finished} de {len(current)} partidos finalizados"
        if live:
            note += f"; {live} en juego"
    return {"matches": matches, "standings": standings, "format": current_format, "scorers": scorers,
            "mvps": jugadores_del_partido(conn),
            "firstPhaseRound": first_phase_round, "firstPhaseNote": first_phase_note,
            "throughRound": through_round, "partialRound": partial, "roundNote": note,
            "goleadoresPendientes": pending, "updatedAt": max((r["actualizado_en"] for r in results), default=None)}


def panel_admin(conn, admin_uid):
    exigir_administrador(conn, admin_uid)
    fixtures, players = partidos(conn), catalogo()[1]
    results, goals = _resultados(conn)
    by_id = {row["fixture_id"]: row for row in results}
    authors = {row["fixture_id"]: row["nombre"] for row in conn.execute(
        """SELECT r.fixture_id,u.nombre FROM copa_resultados r
           JOIN usuarios u ON u.id=r.registrado_por"""
    ).fetchall()}
    schedule = []
    for key, fixture in fixtures.items():
        result = by_id.get(key)
        schedule.append({**fixture, "result": {
            "homeGoals": result["goles_local"], "awayGoals": result["goles_visitante"],
            "status": result["estado"],
            "revision": result["revision"],
            "registrado_por": authors.get(key),
            "goals": [dict(row) for row in goals[key]],
        } if result else None})
    format_matches = [
        {**fixture, "status": ("final" if fixture["result"]["status"] == "FINALIZADO"
                               else "live") if fixture["result"] else "scheduled",
         "homeGoals": fixture["result"]["homeGoals"] if fixture["result"] else None,
         "awayGoals": fixture["result"]["awayGoals"] if fixture["result"] else None}
        for fixture in schedule
    ]
    return {"fixtures": schedule, "players": players, "mvps": jugadores_del_partido(conn),
            "format": formato_actual(format_matches)}


def guardar_resultado(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    fixtures, players = partidos(conn), catalogo()[1]
    fixture = fixtures.get(str(data.get("fixture_id", "")))
    if not fixture:
        raise ErrorValidacion("Selecciona un partido programado de Copa Castell.")
    home = numero(data.get("homeGoals"), "Goles del local", 0, 99)
    away = numero(data.get("awayGoals"), "Goles del visitante", 0, 99)
    status = str(data.get("estado", "FINALIZADO"))
    if status not in {"EN_JUEGO", "FINALIZADO"}:
        raise ErrorValidacion("Selecciona un estado válido para el partido.")
    revision = numero(data.get("revision", 0), "Versión del resultado", 0, 1000000)
    raw_goals = data.get("goals", [])
    if not isinstance(raw_goals, list) or len(raw_goals) > 50:
        raise ErrorValidacion("La lista de goleadores no es válida.")
    goal_rows = {}
    totals = {fixture["home"]: 0, fixture["away"]: 0}
    for item in raw_goals:
        if not isinstance(item, dict):
            raise ErrorValidacion("Revisa los goleadores del partido.")
        country = str(item.get("country", ""))
        if country not in totals:
            raise ErrorValidacion("Un goleador no pertenece a este partido.")
        count = numero(item.get("goals"), "Goles del jugador", 1, 99)
        identifier = str(item.get("playerId", ""))
        if identifier == "new":
            name = texto(item.get("name"), "Nombre del jugador", 3, 100)
            number = str(item.get("number", "")).strip()
            if number and (not number.isdecimal() or len(number) > 3):
                raise ErrorValidacion("El dorsal debe tener hasta tres dígitos.")
            if any(_normalizar(p["name"]) == _normalizar(name) and p["number"] == number
                   for p in players[country]):
                raise ErrorValidacion("Ese jugador ya está en la lista; selecciónalo allí.")
            if number and sum(p["number"] == number for p in players[country]) == 1:
                raise ErrorValidacion("Ese dorsal ya tiene un jugador en la lista; selecciónalo allí.")
            identifier = f"n:{country}:{_normalizar(name)}:{number}"
        else:
            player = next((p for p in players[country] if p["id"] == identifier), None)
            if not player:
                raise ErrorValidacion("Selecciona un jugador de la plantilla correcta.")
            name, number = player["name"], player["number"]
        if identifier in goal_rows:
            raise ErrorValidacion("Cada jugador debe aparecer una sola vez; suma sus goles en su fila.")
        goal_rows[identifier] = (country, name, number, count)
        totals[country] += count
    if totals[fixture["home"]] > home or totals[fixture["away"]] > away:
        raise ErrorValidacion("Los goles asignados a jugadores superan el marcador.")
    # La versión evita que dos administradores sobrescriban cambios ajenos sin aviso.
    if revision == 0:
        conn.execute(
            """INSERT INTO copa_resultados(fixture_id,fecha,local,visitante,goles_local,goles_visitante,estado,registrado_por)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (fixture_id) DO NOTHING""",
            (fixture["id"], fixture["round"], fixture["home"], fixture["away"], home, away, status, admin_uid),
        )
    current = conn.execute(
        "SELECT revision,estado FROM copa_resultados WHERE fixture_id=%s FOR UPDATE", (fixture["id"],)
    ).fetchone()
    if not current or current["revision"] != revision:
        raise HTTPError(409, "Este resultado cambió mientras lo editabas. Recarga el partido antes de guardar.")
    if current["estado"] == "FINALIZADO" and status == "EN_JUEGO":
        raise ErrorValidacion("Un partido finalizado no puede volver a estar en juego.")
    updated = conn.execute(
        """UPDATE copa_resultados SET goles_local=%s,goles_visitante=%s,
           estado=%s,revision=revision+1,registrado_por=%s,actualizado_en=current_timestamp
           WHERE fixture_id=%s RETURNING revision""",
        (home, away, status, admin_uid, fixture["id"]),
    ).fetchone()
    conn.execute("DELETE FROM copa_goles WHERE fixture_id=%s", (fixture["id"],))
    for identifier, (country, name, number, count) in goal_rows.items():
        conn.execute(
            """INSERT INTO copa_goles(fixture_id,equipo,jugador_clave,jugador_nombre,dorsal,goles)
               VALUES(%s,%s,%s,%s,%s,%s)""",
            (fixture["id"], country, identifier, name, number, count),
        )
    missing = home + away - sum(totals.values())
    return {"fixture_id": fixture["id"], "revision": updated["revision"], "estado": status,
            "goleadores_pendientes": missing,
            "message": ("Marcador en vivo actualizado. La tabla y los goleadores se actualizarán al finalizar."
                        if status == "EN_JUEGO" else "Resultado final publicado. " +
                        (f"Quedan {missing} goles sin atribuir a jugadores." if missing else "Posiciones y goleadores actualizados."))}
