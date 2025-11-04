# file: main.py
import os
import time
from typing import Any, Dict
from flask import Flask, jsonify, request

# Only import modules that exist in your ZIP
from modules.cfb_data import get_cfbd_team, get_lines
from modules.cfb_matchup import get_team_matchup
from modules.cfb_power_ratings import get_massey_ratings
from modules.weather_openmeteo import (
    get_weather,
    get_kickoff_window,
    get_hourly_kickoff_window,
)
from modules.spread_engine import calculate_spread_edge
from modules.tempo_plays import get_tempo
from modules.injuries_scraper import get_injuries

app = Flask(__name__)

# ----------------------------- helpers -----------------------------
def _err(msg: str, code: int = 400):
    """Why: consistent client errors."""
    return jsonify({"error": msg}), code

def _require_params(d: Dict[str, Any], *names: str):
    missing = [n for n in names if d.get(n) in (None, "")]
    if missing:
        return f"missing required params: {', '.join(missing)}"
    return None

# ------------------------------ meta -------------------------------
@app.route("/")
def root():
    return jsonify({
        "service": "CFB data + utilities",
        "health": "/health",
        "endpoints": {
            "cfb_team": "/cfb/team?name=Georgia",
            "cfb_lines": "/cfb/lines?team=Georgia&year=2024&week=10",
            "cfb_matchup": "/cfb/matchup?team1=Georgia&team2=Alabama&year=2024",
            "massey": "/cfb/power/massey",
            "weather": "/cfb/weather?lat=33.948&lon=-83.377",
            "weather_kickoff": "/cfb/weather/kickoff?lat=33.948&lon=-83.377&kickoff=2024-11-23T19:00:00Z",
            "weather_hourly": "/cfb/weather/hourly?lat=33.948&lon=-83.377&start=2024-11-23T18:00:00Z&end=2024-11-23T22:00:00Z",
            "tempo": "/cfb/tempo?team=Georgia",
            "injuries": "/cfb/injuries?team=Georgia",
            "spread_edge": "/cfb/spread/edge?team_sp=30.1&opp_sp=27.8&line=-6.5",
        },
    })

@app.route("/health")
def health():
    return jsonify({"ok": True, "ts": int(time.time())})

# ------------------------------ CFB -------------------------------
@app.route("/cfb/team")
def cfb_team():
    name = request.args.get("name")
    if not name:
        return _err("param 'name' is required")
    try:
        return jsonify(get_cfbd_team(name))
    except Exception as e:
        return _err(f"team lookup failed: {e}", 500)

@app.route("/cfb/lines")
def cfb_lines():
    params_error = _require_params(request.args, "team", "year", "week")
    if params_error:
        return _err(params_error)
    try:
        team = request.args["team"]
        year = int(request.args["year"])
        week = int(request.args["week"])
    except ValueError:
        return _err("params 'year' and 'week' must be integers")
    try:
        return jsonify(get_lines(team, year, week))
    except Exception as e:
        return _err(f"lines fetch failed: {e}", 500)

@app.route("/cfb/matchup")
def cfb_matchup_route():
    params_error = _require_params(request.args, "team1", "team2", "year")
    if params_error:
        return _err(params_error)
    team1 = request.args["team1"]
    team2 = request.args["team2"]
    try:
        year = int(request.args["year"])
    except ValueError:
        return _err("param 'year' must be an integer")
    try:
        return jsonify(get_team_matchup(team1, team2, year))
    except Exception as e:
        return _err(f"matchup fetch failed: {e}", 500)

@app.route("/cfb/power/massey")
def cfb_power_massey():
    try:
        return jsonify(get_massey_ratings())
    except Exception as e:
        return _err(f"massey ratings failed: {e}", 500)

# ----------------------------- Weather ----------------------------
@app.route("/cfb/weather")
def cfb_weather():
    params_error = _require_params(request.args, "lat", "lon")
    if params_error:
        return _err(params_error)
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except ValueError:
        return _err("params 'lat' and 'lon' must be numeric")
    try:
        return jsonify(get_weather(lat, lon))
    except Exception as e:
        return _err(f"weather fetch failed: {e}", 500)

@app.route("/cfb/weather/kickoff")
def cfb_weather_kickoff():
    params_error = _require_params(request.args, "lat", "lon", "kickoff")
    if params_error:
        return _err(params_error)
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
        kickoff = request.args["kickoff"]
    except ValueError:
        return _err("params 'lat' and 'lon' must be numeric")
    try:
        return jsonify(get_kickoff_window(lat, lon, kickoff))
    except Exception as e:
        return _err(f"kickoff window fetch failed: {e}", 500)

@app.route("/cfb/weather/hourly")
def cfb_weather_hourly():
    params_error = _require_params(request.args, "lat", "lon", "start", "end")
    if params_error:
        return _err(params_error)
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
        start = request.args["start"]
        end = request.args["end"]
    except ValueError:
        return _err("params 'lat' and 'lon' must be numeric")
    try:
        return jsonify(get_hourly_kickoff_window(lat, lon, start, end))
    except Exception as e:
        return _err(f"hourly window fetch failed: {e}", 500)

# ----------------------------- Tempo/Injuries ---------------------
@app.route("/cfb/tempo")
def cfb_tempo():
    team = request.args.get("team")
    if not team:
        return _err("param 'team' is required")
    try:
        return jsonify(get_tempo(team))
    except Exception as e:
        return _err(f"tempo fetch failed: {e}", 500)

@app.route("/cfb/injuries")
def cfb_injuries():
    team = request.args.get("team")
    if not team:
        return _err("param 'team' is required")
    try:
        return jsonify(get_injuries(team))
    except Exception as e:
        return _err(f"injuries fetch failed: {e}", 500)

# ----------------------------- Spread Edge ------------------------
@app.route("/cfb/spread/edge")
def cfb_spread_edge():
    params_error = _require_params(request.args, "team_sp", "opp_sp", "line")
    if params_error:
        return _err(params_error)
    try:
        team_sp = float(request.args["team_sp"])
        opp_sp = float(request.args["opp_sp"])
        line = float(request.args["line"])
    except ValueError:
        return _err("params 'team_sp', 'opp_sp', and 'line' must be numeric")
    try:
        return jsonify(calculate_spread_edge(team_sp, opp_sp, line))
    except Exception as e:
        return _err(f"edge calc failed: {e}", 500)

# ------------------------------ run -------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
