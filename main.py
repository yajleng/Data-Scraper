import os
import time
from flask import Flask, jsonify, request

# Core modules
from modules.cfb_data import get_cfbd_team
from modules.cfb_batch import update_weekly_cache, read_from_cache, get_team_from_cache

# New modules
from modules.weather_openmeteo import get_weather, get_hourly_kickoff_window
from modules.odds_totals import get_odds_totals
from modules.tempo_plays import get_tempo
from modules.injuries_scraper import get_injuries

from modules.cfb_matchup import get_team_matchup
from modules.cfb_lines import get_historical_lines
from modules.cfb_power_ratings import get_massey_ratings
from modules.odds_history import get_odds_history

from modules.massey_scraper import fetch_massey_ratings

app = Flask(__name__)

# -----------------------------------------------------------
# ROOT
# -----------------------------------------------------------
@app.route("/")
def home():
    return jsonify({
        "message": "CFB weekly cache service (batch + normalization)",
        "endpoints": {
            "admin_update": "/admin/cfb/update?year=2025&week=10",
            "cache_info": "/cfb/cache?year=2025&week=10",
            "team": "/cfb/team?name=Georgia&year=2025&week=10",
            "fetch_team_alias": "/fetch/cfb/team?name=Georgia&year=2025&week=10",
            "weather": "/cfb/weather?lat=33.94&lon=-83.37",
            "weather_hourly": "/cfb/weather/hourly?lat=33.94&lon=-83.37&kickoff=2025-11-01T23:00Z",
            "odds": "/cfb/odds?year=2025&week=10",
            "tempo": "/cfb/tempo?team=Georgia",
            "injuries": "/cfb/injuries?team=georgia",
            "matchup": "/cfb/matchup?team1=Georgia&team2=Alabama&year=2025",
            "lines": "/cfb/lines?year=2025&week=10",
            "ratings": "/cfb/ratings",
            "odds_history": "/cfb/odds/history?date=2025-11-01",
            "health": "/health"
        },
        "status": "ok"
    })

# -----------------------------------------------------------
# ADMIN: Update & Cache
# -----------------------------------------------------------
@app.route("/admin/cfb/update")
def admin_update():
    try:
        year = int(request.args.get("year", 2025))
        week = int(request.args.get("week", 10))
    except ValueError:
        return jsonify({"error": "year/week must be integers"}), 400
    result = update_weekly_cache(year, week)
    return jsonify(result)

# -----------------------------------------------------------
# CACHE READ
# -----------------------------------------------------------
@app.route("/cfb/cache")
def cache_info():
    try:
        year = int(request.args.get("year", 2025))
        week = int(request.args.get("week", 10))
    except ValueError:
        return jsonify({"error": "year/week must be integers"}), 400
    return jsonify(read_from_cache(year, week))

# -----------------------------------------------------------
# TEAM STATS (from cache)
# -----------------------------------------------------------
@app.route("/cfb/team")
def cfb_team():
    name = request.args.get("name", "")
    try:
        year = int(request.args.get("year", 2025))
        week = int(request.args.get("week", 10))
    except ValueError:
        return jsonify({"error": "year/week must be integers"}), 400
    if not name:
        return jsonify({"error": "missing ?name="}), 400
    return jsonify(get_team_from_cache(year, week, name))

@app.route("/fetch/cfb/team")
def fetch_cfb_team_alias():
    return cfb_team()

# -----------------------------------------------------------
# WEATHER (Open-Meteo)
# -----------------------------------------------------------
@app.route("/cfb/weather")
def cfb_weather():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    if not lat or not lon:
        return jsonify({"error": "missing lat/lon parameters"}), 400
    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return jsonify({"error": "lat/lon must be numeric"}), 400
    return jsonify(get_weather(lat, lon))

# -----------------------------------------------------------
# WEATHER HOURLY KICKOFF WINDOW
# -----------------------------------------------------------
@app.route("/cfb/weather/hourly")
def cfb_weather_hourly():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        kickoff = request.args.get("kickoff", "2025-11-01T23:00Z")
        data = get_hourly_kickoff_window(lat, lon, kickoff)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"hourly weather failed: {str(e)}"}), 500

# -----------------------------------------------------------
# ODDS / TOTALS (TheOddsAPI)
# -----------------------------------------------------------
@app.route("/cfb/odds")
def cfb_odds():
    year = request.args.get("year", 2025)
    week = request.args.get("week", 10)
    try:
        data = get_odds_totals(week, year)
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "error": f"Failed to fetch odds: {str(e)}",
            "note": "If TheOddsAPI free tier was exceeded, recheck your API key or add a fallback cache."
        }), 500

# -----------------------------------------------------------
# TEMPO / DRIVE PACE
# -----------------------------------------------------------
@app.route("/cfb/tempo")
def cfb_tempo():
    team = request.args.get("team")
    if not team:
        return jsonify({"error": "missing ?team="}), 400
    try:
        data = get_tempo(team)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"tempo fetch failed: {str(e)}"}), 500

# -----------------------------------------------------------
# INJURIES (ESPN scrape)
# -----------------------------------------------------------
@app.route("/cfb/injuries")
def cfb_injuries():
    team = request.args.get("team")
    if not team:
        return jsonify({"error": "missing ?team="}), 400
    try:
        data = get_injuries(team)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"injury scrape failed: {str(e)}"}), 500

# -----------------------------------------------------------
# CFB TEAM MATCHUP (CFBD /teams/matchup)
# -----------------------------------------------------------
@app.route("/cfb/matchup")
def cfb_matchup():
    team1 = request.args.get("team1")
    team2 = request.args.get("team2")
    year = int(request.args.get("year", 2025))
    if not team1 or not team2:
        return jsonify({"error": "missing ?team1= and ?team2="}), 400
    try:
        return jsonify(get_team_matchup(team1, team2, year))
    except Exception as e:
        return jsonify({"error": f"matchup fetch failed: {str(e)}"}), 500

# -----------------------------------------------------------
# CFB HISTORICAL LINES (CFBD /lines)
# -----------------------------------------------------------
@app.route("/cfb/lines")
def cfb_lines():
    try:
        year = int(request.args.get("year", 2025))
        week = int(request.args.get("week", 10))
        data = get_historical_lines(year, week)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"lines fetch failed: {str(e)}"}), 500

# -----------------------------------------------------------
# MASSEY POWER RATINGS (scrape)
# -----------------------------------------------------------
@app.route("/cfb/ratings")
def cfb_ratings():
    try:
        return jsonify(fetch_massey_ratings())
    except Exception as e:
        return jsonify({"error": f"ratings fetch failed: {str(e)}"}), 500

# -----------------------------------------------------------
# PUBLIC ODDS HISTORY (OddsAPI)
# -----------------------------------------------------------
@app.route("/cfb/odds/history")
def cfb_odds_history():
    date = request.args.get("date", "2025-11-01")
    try:
        data = get_odds_history(date)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"odds history fetch failed: {str(e)}"}), 500

@app.get("/cache/list")
def list_cache_files():
    files = [f for f in os.listdir("cache") if f.endswith(".json")]
    return {"count": len(files), "files": files}

@app.get("/cache/read")
def read_cache_file(filename: str):
    path = os.path.join("cache", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Cache file not found")
    with open(path) as f:
        return json.load(f)

# -----------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------
@app.route("/health")
def health():
    return jsonify({"ok": True, "ts": int(time.time())})

# -----------------------------------------------------------
# RUN SERVER
# -----------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
