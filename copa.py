"""Resultados de Copa Castell posteriores a la línea base pública de la fecha 6."""

from copy import deepcopy
from functools import lru_cache
import json
import unicodedata

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


def _resultados(conn):
    results = conn.execute(
        """SELECT fixture_id,goles_local,goles_visitante,revision,actualizado_en
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


def calcular_posiciones(matches, groups):
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
            row = lookup[country]
            row[2] += 1
            row[3] += scored > received
            row[4] += scored == received
            row[5] += scored < received
            row[6] += scored
            row[7] += received
    for rows in standings.values():
        for row in rows:
            row[1] = row[3] * 3 + row[4]
            row[8] = row[6] - row[7]
        # Nombre solo estabiliza la presentación; no es un desempate deportivo.
        rows.sort(key=lambda row: (-row[1], -row[8], -row[6], _normalizar(row[0])))
        for position, row in enumerate(rows, 1):
            row[9] = position
    return standings


def estado_publico(conn):
    data = base()
    fixtures, _ = catalogo()
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
    scorers = deepcopy(data["scorers"])
    added_scorers = {}
    pending = 0
    for match in matches:
        result = by_id.get(match.get("id"))
        if not result:
            continue
        home, away = result["goles_local"], result["goles_visitante"]
        match.update({"homeGoals": home, "awayGoals": away, "status": "final",
                      "revision": result["revision"]})
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
    standings = calcular_posiciones(matches, data["standings"])
    scorers.extend(added_scorers.values())
    scorers.sort(key=lambda row: -row["goals"])
    round_seven = [f for f in fixtures.values() if f["round"] == 7]
    finished_seven = sum(f["id"] in by_id for f in round_seven)
    postponed = [f for f in fixtures.values() if f["round"] == 6]
    finished_postponed = sum(f["id"] in by_id for f in postponed)
    through_round = 7 if finished_seven else 6
    if through_round == 7:
        note = f"Fecha 7: {finished_seven} de {len(round_seven)} partidos finalizados"
        partial = finished_seven < len(round_seven) or finished_postponed < len(postponed)
        if finished_postponed < len(postponed):
            note += "; Alemania–Venezuela de la fecha 6 pendiente"
    else:
        partial = finished_postponed < len(postponed)
        note = data["roundNote"] if partial else "Fecha 6 completa"
    return {"matches": matches, "standings": standings, "scorers": scorers,
            "throughRound": through_round, "partialRound": partial, "roundNote": note,
            "goleadoresPendientes": pending, "updatedAt": max((r["actualizado_en"] for r in results), default=None)}


def panel_admin(conn, admin_uid):
    exigir_administrador(conn, admin_uid)
    fixtures, players = catalogo()
    results, goals = _resultados(conn)
    by_id = {row["fixture_id"]: row for row in results}
    schedule = []
    for key, fixture in fixtures.items():
        result = by_id.get(key)
        schedule.append({**fixture, "result": {
            "homeGoals": result["goles_local"], "awayGoals": result["goles_visitante"],
            "revision": result["revision"],
            "goals": [dict(row) for row in goals[key]],
        } if result else None})
    return {"fixtures": schedule, "players": players}


def guardar_resultado(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    fixtures, players = catalogo()
    fixture = fixtures.get(str(data.get("fixture_id", "")))
    if not fixture:
        raise ErrorValidacion("Selecciona un partido programado de la fecha 7 o el reprogramado.")
    home = numero(data.get("homeGoals"), "Goles del local", 0, 99)
    away = numero(data.get("awayGoals"), "Goles del visitante", 0, 99)
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
            """INSERT INTO copa_resultados(fixture_id,fecha,local,visitante,goles_local,goles_visitante,registrado_por)
               VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (fixture_id) DO NOTHING""",
            (fixture["id"], fixture["round"], fixture["home"], fixture["away"], home, away, admin_uid),
        )
    current = conn.execute(
        "SELECT revision FROM copa_resultados WHERE fixture_id=%s FOR UPDATE", (fixture["id"],)
    ).fetchone()
    if not current or current["revision"] != revision:
        raise HTTPError(409, "Este resultado cambió mientras lo editabas. Recarga el partido antes de guardar.")
    updated = conn.execute(
        """UPDATE copa_resultados SET goles_local=%s,goles_visitante=%s,
           revision=revision+1,registrado_por=%s,actualizado_en=current_timestamp
           WHERE fixture_id=%s RETURNING revision""",
        (home, away, admin_uid, fixture["id"]),
    ).fetchone()
    conn.execute("DELETE FROM copa_goles WHERE fixture_id=%s", (fixture["id"],))
    for identifier, (country, name, number, count) in goal_rows.items():
        conn.execute(
            """INSERT INTO copa_goles(fixture_id,equipo,jugador_clave,jugador_nombre,dorsal,goles)
               VALUES(%s,%s,%s,%s,%s,%s)""",
            (fixture["id"], country, identifier, name, number, count),
        )
    missing = home + away - sum(totals.values())
    return {"fixture_id": fixture["id"], "revision": updated["revision"],
            "goleadores_pendientes": missing,
            "message": "Resultado publicado. " + (f"Quedan {missing} goles sin atribuir a jugadores." if missing else "Posiciones y goleadores actualizados.")}
