"""
actualizar_2026.py — actualiza data/live.json con los datos en vivo del
Mundial 2026 desde la API de football-data.org, en el formato que lee la página.

Uso (n8n "Execute Command" o CLI):
    python actualizar_2026.py path/to/matches.json
    cat matches.json | python actualizar_2026.py

El input es el JSON crudo de:
    GET https://api.football-data.org/v4/competitions/WC/matches

Cuando hay al menos 1 partido FINISHED, además consulta en vivo el ranking de
goleadores (GET .../WC/scorers) usando la variable de entorno FOOTBALL_DATA_API_KEY.
Si esa consulta falla (rate limit / red / falta la key), se loguea y goleadores[]
queda sin cambios — no rompe el resto de la actualización.

Qué actualiza dentro de data/live.json (las estructuras que consume index.html):
    · partidos[]       — estado / goles / minuto, matcheando por fdId == match id
    · clasificaciones  — recalculadas desde los partidos de grupos finalizados
    · goleadores[]     — top 20 desde la API, si hay partidos finalizados
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timezone


JSON_PATH = 'data/live.json'

# API football-data.org — para traer el ranking de goleadores en vivo.
# Configurar FOOTBALL_DATA_API_KEY en el entorno (Render).
FOOTBALL_DATA_API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY')
WC_COMPETITION_ID = 2000

# football-data.org (nombre en inglés) -> (nombre en español, bandera emoji).
# Debe coincidir con los nombres usados en data/live.json (partidos/clasificaciones).
TEAM_MAP = {
    "Czechia": ("Chequia", "🇨🇿"), "Mexico": ("México", "🇲🇽"), "South Africa": ("Sudáfrica", "🇿🇦"),
    "South Korea": ("Corea del Sur", "🇰🇷"), "Bosnia-Herzegovina": ("Bosnia y Herzegovina", "🇧🇦"),
    "Canada": ("Canadá", "🇨🇦"), "Qatar": ("Catar", "🇶🇦"), "Switzerland": ("Suiza", "🇨🇭"),
    "Brazil": ("Brasil", "🇧🇷"), "Morocco": ("Marruecos", "🇲🇦"), "Haiti": ("Haití", "🇭🇹"),
    "Scotland": ("Escocia", "🏴󠁧󠁢󠁳󠁣󠁴󠁿"), "Turkey": ("Turquía", "🇹🇷"), "United States": ("Estados Unidos", "🇺🇸"),
    "Paraguay": ("Paraguay", "🇵🇾"), "Australia": ("Australia", "🇦🇺"), "Germany": ("Alemania", "🇩🇪"),
    "Curaçao": ("Curazao", "🇨🇼"), "Ivory Coast": ("Costa de Marfil", "🇨🇮"), "Ecuador": ("Ecuador", "🇪🇨"),
    "Sweden": ("Suecia", "🇸🇪"), "Netherlands": ("Países Bajos", "🇳🇱"), "Japan": ("Japón", "🇯🇵"),
    "Tunisia": ("Túnez", "🇹🇳"), "Belgium": ("Bélgica", "🇧🇪"), "Egypt": ("Egipto", "🇪🇬"),
    "Iran": ("Irán", "🇮🇷"), "New Zealand": ("Nueva Zelanda", "🇳🇿"), "Spain": ("España", "🇪🇸"),
    "Cape Verde Islands": ("Cabo Verde", "🇨🇻"), "Saudi Arabia": ("Arabia Saudita", "🇸🇦"),
    "Uruguay": ("Uruguay", "🇺🇾"), "Iraq": ("Irak", "🇮🇶"), "France": ("Francia", "🇫🇷"),
    "Senegal": ("Senegal", "🇸🇳"), "Norway": ("Noruega", "🇳🇴"), "Argentina": ("Argentina", "🇦🇷"),
    "Algeria": ("Argelia", "🇩🇿"), "Austria": ("Austria", "🇦🇹"), "Jordan": ("Jordania", "🇯🇴"),
    "Congo DR": ("RD Congo", "🇨🇩"), "Portugal": ("Portugal", "🇵🇹"), "Uzbekistan": ("Uzbekistán", "🇺🇿"),
    "Colombia": ("Colombia", "🇨🇴"), "England": ("Inglaterra", "🏴󠁧󠁢󠁥󠁮󠁧󠁿"), "Croatia": ("Croacia", "🇭🇷"),
    "Ghana": ("Ghana", "🇬🇭"), "Panama": ("Panamá", "🇵🇦"),
}


def tr_team(name):
    """Traduce el nombre de la API a (nombre_es, bandera). Si no está mapeado,
    devuelve el nombre tal cual con bandera neutra."""
    if not name:
        return (None, None)
    return TEAM_MAP.get(name, (name, '🏳️'))


# football-data status -> estado interno de la página
ESTADO_MAP = {
    'FINISHED': 'finished',
    'IN_PLAY': 'in_play', 'PAUSED': 'in_play',
    'TIMED': 'scheduled', 'SCHEDULED': 'scheduled',
}


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


# ── Actualizar partidos[] (matcheando por fdId == id de la API) ──────────────
def apply_live_to_partidos(d, payload):
    """Actualiza estado / goles / minuto de cada partido en partidos[], buscando
    por fdId == match id de football-data. En eliminatorias, completa los equipos
    'Por definir' cuando la API ya los define (traducidos con TEAM_MAP)."""
    by_fd = {p.get('fdId'): p for p in d.get('partidos', [])}
    updated = 0
    for m in payload.get('matches', []):
        p = by_fd.get(m.get('id'))
        if not p:
            continue
        status = m.get('status')
        p['estado'] = ESTADO_MAP.get(status, p.get('estado'))
        if status in ('IN_PLAY', 'PAUSED', 'FINISHED'):
            p['goles_local'] = safe_score(m, 'home')
            p['goles_visitante'] = safe_score(m, 'away')
        p['minuto'] = m.get('minute')

        # Eliminatorias: cuando la API ya tiene los clasificados, reemplazar "Por definir"
        if p.get('grupo') is None:
            home = (m.get('homeTeam') or {}).get('name')
            away = (m.get('awayTeam') or {}).get('name')
            if home:
                p['local'], p['bandera_local'] = tr_team(home)
            if away:
                p['visitante'], p['bandera_visitante'] = tr_team(away)
        updated += 1
    print(f'partidos[] actualizados: {updated}')
    return updated


# ── Goleadores: ranking en vivo desde football-data.org ──────────────────────
def fetch_scorers(limit=20):
    """Trae el ranking de goleadores del Mundial desde football-data.org.
    Requiere FOOTBALL_DATA_API_KEY en el entorno. Devuelve una lista plana.
    Lanza excepción ante error de red / rate limit / falta de key."""
    if not FOOTBALL_DATA_API_KEY:
        raise RuntimeError('falta la variable de entorno FOOTBALL_DATA_API_KEY')
    # Import diferido: el resto del script no depende de requests (no rompe si falta).
    import requests
    url = f'https://api.football-data.org/v4/competitions/{WC_COMPETITION_ID}/scorers'
    resp = requests.get(url, headers={'X-Auth-Token': FOOTBALL_DATA_API_KEY},
                        params={'limit': limit}, timeout=30)
    resp.raise_for_status()
    out = []
    for item in resp.json().get('scorers', []):
        out.append({
            'player': item['player']['name'],
            'team': item['team']['name'],
            'goals': item.get('goals'),
            'assists': item.get('assists'),
            'matches_played': item.get('playedMatches'),
        })
    return out


def to_goleadores(scorers, limit=20):
    """Convierte el ranking de fetch_scorers() al esquema de goleadores[] en
    live.json (pos/jugador/pais/bandera/goles/asistencias), traduciendo país y
    bandera con TEAM_MAP."""
    out = []
    for i, s in enumerate(scorers[:limit], start=1):
        pais, bandera = tr_team(s.get('team'))
        out.append({
            'pos': i,
            'jugador': s.get('player', ''),
            'pais': pais or s.get('team', ''),
            'bandera': bandera or '🏳️',
            'goles': s.get('goals') or 0,
            'asistencias': s.get('assists'),
        })
    return out


# ── Clasificaciones: recalcular sobre la estructura existente (12 grupos x 4) ─
def update_clasificaciones(d, finished):
    """Recalcula clasificaciones[] sumando los partidos de grupos finalizados.
    Parte de la estructura existente (mantiene los 4 equipos de cada grupo aunque
    todavía no hayan jugado) y reordena por puntos / dif. de gol / GF."""
    clas = d.get('clasificaciones') or {}
    index = {}
    for letra, rows in clas.items():
        index[letra] = {}
        for r in rows:
            for k in ('pj', 'g', 'e', 'p', 'gf', 'gc', 'dif', 'pts'):
                r[k] = 0
            index[letra][r['pais']] = r

    for m in finished:
        if m.get('stage') != 'GROUP_STAGE':
            continue
        letra = (m.get('group') or '').replace('GROUP_', '')
        rows = index.get(letra)
        if not rows:
            continue
        rh = rows.get(tr_team(m['homeTeam']['name'])[0])
        ra = rows.get(tr_team(m['awayTeam']['name'])[0])
        if not rh or not ra:
            print(f"  aviso: equipo sin fila en grupo {letra} "
                  f"({m['homeTeam']['name']} / {m['awayTeam']['name']}) — salteado")
            continue
        hs, as_ = safe_score(m, 'home'), safe_score(m, 'away')
        rh['pj'] += 1; ra['pj'] += 1
        rh['gf'] += hs; rh['gc'] += as_
        ra['gf'] += as_; ra['gc'] += hs
        if hs > as_:
            rh['g'] += 1; rh['pts'] += 3; ra['p'] += 1
        elif hs < as_:
            ra['g'] += 1; ra['pts'] += 3; rh['p'] += 1
        else:
            rh['e'] += 1; rh['pts'] += 1
            ra['e'] += 1; ra['pts'] += 1

    for letra, rows in clas.items():
        for r in rows:
            r['dif'] = r['gf'] - r['gc']
        rows.sort(key=lambda r: (-r['pts'], -r['dif'], -r['gf'], r['pais']))
    print('clasificaciones[] recalculadas')


# ── Normalizar bracket de eliminatoria (orden + jornada) ─────────────────────
R16_JORNADA = "Dieciseisavos de final"

# Fixture real de 16avos: pareja de equipos (nombres canónicos del TEAM_MAP) -> orden.
# Permite alinear el bracket con el fixture hardcodeado de renderPlayoff aunque el
# orden de fdId de football-data no coincida. Debe espejar el HTML (ojo nombres:
# "Estados Unidos"/"Bosnia y Herzegovina"/"RD Congo", no "EEUU"/"Bosnia"/"Congo").
R32_FIXTURE = {
    frozenset({"Alemania", "Paraguay"}): 1,
    frozenset({"Francia", "Suecia"}): 2,
    frozenset({"Sudáfrica", "Canadá"}): 3,
    frozenset({"Países Bajos", "Marruecos"}): 4,
    frozenset({"Portugal", "Croacia"}): 5,
    frozenset({"España", "Austria"}): 6,
    frozenset({"Estados Unidos", "Bosnia y Herzegovina"}): 7,
    frozenset({"Bélgica", "Senegal"}): 8,
    frozenset({"Brasil", "Japón"}): 9,
    frozenset({"Noruega", "Costa de Marfil"}): 10,
    frozenset({"México", "Ecuador"}): 11,
    frozenset({"Inglaterra", "RD Congo"}): 12,
    frozenset({"Argentina", "Cabo Verde"}): 13,
    frozenset({"Australia", "Egipto"}): 14,
    frozenset({"Suiza", "Argelia"}): 15,
    frozenset({"Colombia", "Ghana"}): 16,
}


def normalize_playoff(d):
    """Deja la estructura del bracket como la espera la página (renderPlayoff):
    - jornada "Tercer puesto" -> "Tercer y cuarto puesto"
    - 16avos: orden alineado al fixture por nombre de equipo (cuando ya están definidos
      los 16 cruces); si todavía no, orden por fdId como placeholder.
    - resto de rondas: orden = 1..N por fdId.
    Idempotente: se puede correr en cada actualización sin efectos secundarios."""
    porRonda = {}
    for p in d.get('partidos', []):
        if p.get('fase') != 'eliminatoria':
            continue
        if p.get('jornada') == 'Tercer puesto':
            p['jornada'] = 'Tercer y cuarto puesto'
        porRonda.setdefault(p['jornada'], []).append(p)

    for ronda, arr in porRonda.items():
        arr.sort(key=lambda p: p.get('fdId') or 0)

        if ronda == R16_JORNADA:
            ordenes = [R32_FIXTURE.get(frozenset({p.get('local'), p.get('visitante')})) for p in arr]
            # Solo si los 16 cruces matchean el fixture y dan órdenes únicos
            if all(ordenes) and len(set(ordenes)) == len(arr):
                for p, orden in zip(arr, ordenes):
                    p['orden'] = orden
                print('16avos: orden alineado al fixture por nombre de equipo')
                continue
            print('16avos aún sin definir por completo — orden por fdId (placeholder)')

        for i, p in enumerate(arr, start=1):
            p['orden'] = i
    print('bracket normalizado (orden por ronda + jornada 3er puesto)')


# ── Persistir en data/live.json ──────────────────────────────────────────────
def update_live_json(payload, finished):
    print(f'Cargando {JSON_PATH}')
    with open(JSON_PATH, encoding='utf-8') as f:
        d = json.load(f)

    apply_live_to_partidos(d, payload)
    update_clasificaciones(d, finished)
    normalize_playoff(d)

    # Goleadores: solo si ya hay al menos 1 partido finalizado. Tolerante a fallos:
    # un error de la API (rate limit / red / falta de key) NO interrumpe el script.
    if finished:
        try:
            d['goleadores'] = to_goleadores(fetch_scorers())
            print(f"goleadores[] actualizados: {len(d['goleadores'])}")
        except Exception as e:
            print(f'No se pudieron traer goleadores ({type(e).__name__}: {e}) — goleadores[] sin cambios')
    else:
        print('Sin partidos finalizados — goleadores[] sin cambios')

    d['ultima_actualizacion'] = datetime.now(timezone.utc).isoformat()
    d.pop('mundial_2026', None)  # limpiar bloque viejo que la página no consume

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print('live.json guardado')


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

    push = run_git(['git', 'push', 'origin', 'HEAD:main'])
    if push.returncode != 0:
        raise RuntimeError(f'git push devolvió rc={push.returncode}')


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        payload  = load_input()
        finished = get_finished_matches(payload)

        total_goals = sum(safe_score(m, 'home') + safe_score(m, 'away') for m in finished)
        print(f'Goles totales: {total_goals}')

        update_live_json(payload, finished)
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
