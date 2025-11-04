# file: main.py
import os
import sys
import time
import types
from typing import Any, Dict
from flask import Flask, jsonify, request

# Import ONLY modules that exist in the repo you uploaded
from modules.cfb_data import get_cfbd_team, get_lines
from modules.cfb_matchup import get_team_matchup
from modules.cfb_power_ratings import get_massey_ratings
from modules.weather_openmeteo import get_weather, get_kickoff_window
from modules.spread_engine import calculate_spread_edge

app = Flask(__name__)

# --------- helpers ---------
def err(msg: str, code: int = 400):
    """Uniform JSON errors (why: consistent client handling)."""
    return jsonify({"error": msg}), code

def require_params(d: Dict[str, Any], *names: str):
    missing = [n for n in names if d.get(n) in (None, "")]
    if missing:
        return f"missing required params: {', '.join(missing)}"
    return None

def _install_cache_shim():
    """
    If modules.cache_utils is absent, provide a tiny in-memory shim so
    modules/tempo_plays.py and modules/injuries_scraper.py can import.
    Why: your ZIP excluded cache_utils; this prevents ImportError.
    """
    if "modules.cache_utils" in sys.modules:
        return
    cache: Dict[str, Any] = {}
    mod = types.ModuleType("modules.cache_utils")
    def load_cache(key: str):
        return cache.get(key)
    def save_cache(key: str, value: Any, *args, **kwargs):
        cache[key] = value
    mod.load_cache = load_cache
    mod.save_cache = save_cache
    sys.modules["modules.cache_utils"] = mod

# --------- health ---------
@app.route("/health")
def health():
    return jsonify({"ok": True, "ts": int(time.time())})

# --------- CFB: team info ---------
@app.route("/cfb/team")
def cfb_team():
    team = request.args.get("team")
    if not team:
        return err("param 'team' is required")
    try:
        return jsonify(get_cfbd_team(team))
    except Exception as e:
        return err(f"team lookup failed: {e}", 500)

# --------- CFB: lines (placeholder wrapper in your repo) ---------
@app.route("/cfb/lines")
def cfb_lines():
    params_error = require_params(request.args, "team", "year", "week")
    if params_error:
        return err(params_error)
    team = request.args["team"]
    try:
        year = int(request.args["year"])
        week = int(request.args["week"])
    except ValueError:
        return err("params 'year' and 'week' must be integers")
    try:
        return jsonify(get_lines(team, year, week))
    except Exception as e:
        return err(f"lines fetch failed: {e}", 500)

# --------- CFB: matchup ---------
@app.route("/cfb/matchup")
def cfb_matchup():
    params_error = require_params(request.args, "team1", "team2", "year")
    if params_error:
        return err(params_error)
    team1 = request.args["team1"]
    team2 = request.args["team2"]
    try:
        year = int(request.args["year"])
    except ValueError:
        return err("param 'year' must be an integer")
    try:
        return jsonify(get_team_matchup(team1, team2, year))
    except Exception as e:
        return err(f"matchup fetch failed: {e}", 500)

# --------- CFB: power ratings (Massey) ---------
@app.route("/cfb/power/massey")
def cfb_power_massey():
    try:
        return jsonify(get_massey_ratings())
    except Exception as e:
        return err(f"massey ratings failed: {e}", 500)

# --------- Weather (Open-Meteo) ---------
@app.route("/cfb/weather")
def cfb_weather():
    params_error = require_params(request.args, "lat", "lon")
    if params_error:
        return err(params_error)
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except ValueError:
        return err("params 'lat' and 'lon' must be numeric")
    try:
        return jsonify(get_weather(lat, lon))
    except Exception as e:
        return err(f"weather fetch failed: {e}", 500)

@app.route("/cfb/weather/kickoff")
def cfb_weather_kickoff():
    params_error = require_params(request.args, "lat", "lon", "kickoff")
    if params_error:
        return err(params_error)
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except ValueError:
        return err("params 'lat' and 'lon' must be numeric")
    kickoff = request.args["kickoff"]
    try:
        return jsonify(get_kickoff_window(lat, lon, kickoff))
    except Exception as e:
        return err(f"kickoff window fetch failed: {e}", 500)

# --------- Spread engine (toy) ---------
@app.route("/cfb/spread/edge")
def cfb_spread_edge():
    params_error = require_params(request.args, "team_sp", "opp_sp", "line")
    if params_error:
        return err(params_error)
    try:
        team_sp = float(request.args["team_sp"])
        opp_sp  = float(request.args["opp_sp"])
        line    = float(request.args["line"])
    except ValueError:
        return err("params 'team_sp', 'opp_sp', and 'line' must be numeric")
    try:
        return jsonify(calculate_spread_edge(team_sp, opp_sp, line))
    except Exception as e:
        return err(f"edge calc failed: {e}", 500)

# --------- Injuries (lazy import due to missing cache_utils) ---------
@app.route("/cfb/injuries")
def cfb_injuries():
    team = request.args.get("team")
    if not team:
        return err("param 'team' is required")
    try:
        _install_cache_shim()
        from modules.injuries_scraper import get_injuries  # import here to avoid startup failure
        return jsonify(get_injuries(team))
    except Exception as e:
        return err(f"injuries fetch failed: {e}", 500)

# --------- Tempo (lazy import due to missing cache_utils) ---------
@app.route("/cfb/tempo")
def cfb_tempo():
    team = request.args.get("team")
    if not team:
        return err("param 'team' is required")
    try:
        _install_cache_shim()
        from modules.tempo_plays import get_tempo  # import here to avoid startup failure
        return jsonify(get_tempo(team))
    except Exception as e:
        return err(f"tempo fetch failed: {e}", 500)

# --------- run ---------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
