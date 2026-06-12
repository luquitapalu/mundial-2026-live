"""
actualizar_2026.py — actualiza data/historico.json con los datos en vivo
del Mundial 2026 desde la API de football-data.org.

Uso (n8n "Execute Command" o CLI):
    python actualizar_2026.py path/to/matches.json
    cat matches.json | python actualizar_2026.py

El input es el JSON crudo de:
    GET https://api.football-data.org/v4/competitions/WC/matches
Opcionalmente puede incluir un campo top-level "scorers" con la respuesta de:
    GET https://api.football-data.org/v4/competitions/WC/scorers
para alimentar el ranking de goleadores. Si no viene, queda vacío.
"""

import os
import sys
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone


JSON_PATH = 'data/live.json'


# ── Cargar input ────────────────────────────────────────────────────────────
def load_input():
    """Lee JSON desde argv[1] (path) o desde stdin (pipe)."""
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f'Leyendo input desde archivo: {path}')
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    print('Leyendo input desde stdin')
    return json.load(sys.stdin)


# ── Helpers ─────────────────────────────────────────────────────────────────
def safe_score(m, side):
    """Devuelve los goles del lado dado, 0 si la API mandó null."""
    return (m.get('score', {}).get('fullTime', {}) or {}).get(side) or 0


def get_finished_matches(payload):
    matches = payload.get('matches', [])
    finished = [m for m in matches if m.get('status') == 'FINISHED']
    print(f'Partidos totales: {len(matches)} · finalizados: {len(finished)}')
    return finished


# ── Resultados partido a partido ────────────────────────────────────────────
def build_results(finished):
    results = []
    for m in finished:
        results.append({
            'date':       m.get('utcDate'),
            'stage':      m.get('stage'),
            'group':      m.get('group'),
            'home':       m['homeTeam']['name'],
            'home_code':  m['homeTeam'].get('tla'),
            'away':       m['awayTeam']['name'],
            'away_code':  m['awayTeam'].get('tla'),
            'home_goals': safe_score(m, 'home'),
            'away_goals': safe_score(m, 'away'),
            'winner':     m['score'].get('winner'),
            'duration':   m['score'].get('duration'),
        })
    return results


# ── Tabla de posiciones (solo fase de grupos) ───────────────────────────────
def build_standings(finished):
    """3 pts win, 1 draw, 0 lose. Agrupa por nombre de grupo."""
    groups = defaultdict(lambda: defaultdict(lambda: {
        'team': '', 'code': '',
        'played': 0, 'won': 0, 'draw': 0, 'lost': 0,
        'goals_for': 0, 'goals_against': 0, 'goal_diff': 0, 'points': 0,
    }))

    for m in finished:
        if m.get('stage') != 'GROUP_STAGE':
            continue

        g  = m.get('group') or 'Group ?'
        h, a   = m['homeTeam']['name'], m['awayTeam']['name']
        hc, ac = m['homeTeam'].get('tla', ''), m['awayTeam'].get('tla', '')
        hs, as_ = safe_score(m, 'home'), safe_score(m, 'away')

        for tn, tc in ((h, hc), (a, ac)):
            groups[g][tn]['team'] = tn
            groups[g][tn]['code'] = tc

        groups[g][h]['played']        += 1
        groups[g][a]['played']        += 1
        groups[g][h]['goals_for']     += hs
        groups[g][h]['goals_against'] += as_
        groups[g][a]['goals_for']     += as_
        groups[g][a]['goals_against'] += hs

        if hs > as_:
            groups[g][h]['won']  += 1; groups[g][h]['points'] += 3
            groups[g][a]['lost'] += 1
        elif hs < as_:
            groups[g][a]['won']  += 1; groups[g][a]['points'] += 3
            groups[g][h]['lost'] += 1
        else:
            groups[g][h]['draw'] += 1; groups[g][h]['points'] += 1
            groups[g][a]['draw'] += 1; groups[g][a]['points'] += 1

    standings = {}
    for gname, teams in groups.items():
        rows = list(teams.values())
        for r in rows:
            r['goal_diff'] = r['goals_for'] - r['goals_against']
        # Orden: puntos desc, diferencia de gol desc, goles a favor desc, nombre asc
        rows.sort(key=lambda r: (-r['points'], -r['goal_diff'], -r['goals_for'], r['team']))
        standings[gname] = rows

    return dict(sorted(standings.items()))


# ── Top 5 goleadores ────────────────────────────────────────────────────────
def build_top_scorers(payload, limit=5):
    """Usa el campo opcional 'scorers' (respuesta del endpoint /scorers).
    El endpoint /matches NO trae goleadores — para que esto se llene hay que
    combinar ambas respuestas en el JSON de entrada."""
    raw = payload.get('scorers') or []
    if not raw:
        print('Sin "scorers" en el payload — top_scorers queda vacío')
        return []

    out = []
    for s in raw[:limit]:
        player = s.get('player') or {}
        team   = s.get('team')   or {}
        out.append({
            'player': player.get('name', ''),
            'team':   team.get('name', ''),
            'goals':  s.get('goals') or 0,
        })
    return out


# ── Persistir en data/historico.json ────────────────────────────────────────
def update_historico(payload_2026):
    print(f'Cargando {JSON_PATH}')
    with open(JSON_PATH, encoding='utf-8') as f:
        d = json.load(f)

    d['mundial_2026'] = payload_2026

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    print(f'JSON guardado con la clave mundial_2026')


# ── Git add / commit / push ─────────────────────────────────────────────────
def run_git(cmd):
    """Ejecuta un comando git y logueá stdout/stderr."""
    print('$', ' '.join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout: print(r.stdout.rstrip())
    if r.stderr: print(r.stderr.rstrip())
    return r


def ensure_git_identity():
    """Configura la identidad de git si todavía no está definida (entornos CI/bot)."""
    email = subprocess.run(['git', 'config', 'user.email'], capture_output=True, text=True)
    if not email.stdout.strip():
        print('git user.email no configurado — usando identidad del bot')
        subprocess.run(['git', 'config', 'user.email', 'bot@mundial2026.com'])
        subprocess.run(['git', 'config', 'user.name', 'Mundial Bot'])


def configure_authenticated_remote():
    """Configura el remote origin con autenticación por token, si hay uno en el entorno.

    El token se lee SIEMPRE de la variable de entorno GITHUB_TOKEN — nunca se
    hardcodea en el código (esto se commitea y subiría el secreto a GitHub).
    Definí la variable en el entorno donde corre el script (CI / runner):
        Linux/macOS:  export GITHUB_TOKEN=ghp_xxx
        PowerShell:   $env:GITHUB_TOKEN = "ghp_xxx"
    """
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print('Sin GITHUB_TOKEN en el entorno — push con la config de remote existente')
        return

    remote_url = f'https://{token}@github.com/luquitapalu/mundial-2026-live.git'
    # OJO: no usamos run_git acá para no loguear la URL (lleva el token embebido).
    set_url = subprocess.run(['git', 'remote', 'set-url', 'origin', remote_url],
                             capture_output=True, text=True)
    if set_url.returncode == 0:
        print('Remote origin actualizado con autenticación por token')
        return

    # No existe el remote (p. ej. repo clonado en detached HEAD sin remotes): lo agregamos.
    add = subprocess.run(['git', 'remote', 'add', 'origin', remote_url],
                         capture_output=True, text=True)
    if add.returncode == 0:
        print('Remote origin agregado con autenticación por token')
    else:
        print('No se pudo configurar el remote origin (set-url y add fallaron)')


def git_commit_and_push():
    """git add → commit → push. Si no hay cambios, skip silencioso."""
    ensure_git_identity()

    add = run_git(['git', 'add', JSON_PATH])
    if add.returncode != 0:
        raise RuntimeError(f'git add devolvió rc={add.returncode}')

    commit = run_git(['git', 'commit', '-m', 'actualizacion automatica Mundial 2026'])
    if commit.returncode != 0:
        msg = (commit.stdout + commit.stderr).lower()
        if 'nothing to commit' in msg or 'no changes added' in msg or 'sin cambios' in msg:
            print('Sin cambios para commitear — skip push')
            return
        raise RuntimeError(f'git commit devolvió rc={commit.returncode}')

    configure_authenticated_remote()

    push = run_git(['git', 'push'])
    if push.returncode != 0:
        raise RuntimeError(f'git push devolvió rc={push.returncode}')


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        payload  = load_input()
        finished = get_finished_matches(payload)

        total_goals = sum(safe_score(m, 'home') + safe_score(m, 'away') for m in finished)
        print(f'Goles totales: {total_goals}')

        result = {
            'last_update':    datetime.now(timezone.utc).isoformat(),
            'matches_played': len(finished),
            'total_goals':    total_goals,
            'standings':      build_standings(finished),
            'top_scorers':    build_top_scorers(payload),
            'results':        build_results(finished),
        }

        update_historico(result)
        git_commit_and_push()
        print('Listo — Mundial 2026 actualizado')

    except FileNotFoundError as e:
        print(f'ERROR archivo no encontrado: {e}')
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f'ERROR JSON inválido: {e}')
        sys.exit(1)
    except KeyError as e:
        print(f'ERROR campo faltante en el payload: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}')
        sys.exit(1)
