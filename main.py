# file: main.py
import os
import sys
import math
import time
import types
from typing import Any, Dict, Optional, Tuple
from flask import Flask, jsonify, request

# --- existing modules in your ZIP ---
from modules.cfb_data import get_cfbd_team, get_lines
from modules.cfb_matchup import get_team_matchup
from modules.cfb_power_ratings import get_massey_ratings
from modules.weather_openmeteo import (
    get_weather,
    get_kickoff_window,
    get_hourly_kickoff_window,
)
from modules.spread_engine import calculate_spread_edge

app = Flask(__name__)

# ----------------------- validation (import or embed) -----------------------
def _try_import_validate():
    """
    Why: keep a single source of truth. If validate_input_revised.py exists,
    import it; else fall back to an embedded equivalent (no behavior drift).
    """
    try:
        from validate_input_revised import validate_input  # type: ignore
        return validate_input
    except Exception:
        pass

    # Embedded validator mirrors your validate_input_revised.py
    EXPECTED_INPUT_KEYS = [
        "offense_home","defense_home","offense_away","defense_away",
        "home_field_points","rest_diff_days","away_travel_miles",
        "qb_home_delta","qb_away_delta","key_injuries_home","key_injuries_away",
        "wind_mph","pass_rate_home","pass_rate_away",
    ]
    EXPECTED_MARKET_KEYS = ["spread","odds_home","odds_away"]

    def _is_number(value):
        return isinstance(value, (int,float)) and not isinstance(value,bool)

    def _validate_numeric_field(section, key, value, min_val=-9999, max_val=9999):
        if not _is_number(value):
            return False, f"{section}.{key} must be numeric"
        if not (min_val <= value <= max_val):
            return False, f"{section}.{key}={value} out of range ({min_val},{max_val})"
        return True, ""

    def validate_input(data: dict) -> bool:
        ok = True
        if "inputs" not in data or "market" not in data:
            return False
        inputs = data.get("inputs", {})
        market = data.get("market", {})
        for k in EXPECTED_INPUT_KEYS:
            if k not in inputs:
                ok = False
            else:
                ok &= _validate_numeric_field("inputs", k, inputs[k])[0]
        for k in EXPECTED_MARKET_KEYS:
            if k not in market:
                ok = False
            else:
                ok &= _validate_numeric_field("market", k, market[k], -20000, 20000)[0]
        return ok

    return validate_input

validate_input = _try_import_validate()

# ------------------------ tiny helpers / error style ------------------------
def _err(msg: str, code: int = 400):
    return jsonify({"error": msg}), code

def _require(d: Dict[str, Any], *names: str) -> Optional[str]:
    miss = [n for n in names if d.get(n) in (None, "")]
    return f"missing required params: {', '.join(miss)}" if miss else None

def _install_cache_shim():
    """Why: your repo omitted modules.cache_utils; provide a no-op memory shim."""
    if "modules.cache_utils" in sys.modules:
        return
    cache: Dict[str, Any] = {}
    mod = types.ModuleType("modules.cache_utils")
    def load_cache(key: str): return cache.get(key)
    def save_cache(key: str, value: Any, *_, **__): cache[key] = value
    mod.load_cache = load_cache
    mod.save_cache = save_cache
    sys.modules["modules.cache_utils"] = mod

# ------------------------------ health/meta ------------------------------
@app.route("/")
def root():
    return jsonify({
        "service": "CFB Data Intelligence API (Flask)",
        "health": "/health",
        "validation_first": True,
        "model": {"name": "cfb_spread_model_v2", "version": "2.0.0", "lambda": 0.834421, "seed": 42},
        "endpoints": {
            "build_inputs": "GET/POST /cfb/build_inputs",
            "run_model": "POST /cfb/run_model",
        },
    })

@app.route("/health")
def health():
    return jsonify({"ok": True, "ts": int(time.time())})

# ------------------------------ scrapers ------------------------------
@app.route("/cfb/team")
def cfb_team():
    name = request.args.get("name")
    if not name: return _err("param 'name' is required")
    try:
        return jsonify(get_cfbd_team(name))
    except Exception as e:
        return _err(f"team lookup failed: {e}", 500)

@app.route("/cfb/lines")
def cfb_lines():
    e = _require(request.args, "team","year","week")
    if e: return _err(e)
    try:
        team = request.args["team"]; year = int(request.args["year"]); week = int(request.args["week"])
    except ValueError:
        return _err("params 'year' and 'week' must be integers")
    try:
        return jsonify(get_lines(team, year, week))
    except Exception as e:
        return _err(f"lines fetch failed: {e}", 500)

@app.route("/cfb/matchup")
def cfb_matchup_route():
    e = _require(request.args, "team1","team2","year")
    if e: return _err(e)
    team1 = request.args["team1"]; team2 = request.args["team2"]
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

@app.route("/cfb/weather")
def cfb_weather():
    e = _require(request.args, "lat","lon")
    if e: return _err(e)
    try:
        lat = float(request.args["lat"]); lon = float(request.args["lon"])
    except ValueError:
        return _err("params 'lat' and 'lon' must be numeric")
    try:
        return jsonify(get_weather(lat, lon))
    except Exception as e:
        return _err(f"weather fetch failed: {e}", 500)

@app.route("/cfb/weather/kickoff")
def cfb_weather_kickoff():
    e = _require(request.args, "lat","lon","kickoff")
    if e: return _err(e)
    try:
        lat = float(request.args["lat"]); lon = float(request.args["lon"]); kickoff = request.args["kickoff"]
    except ValueError:
        return _err("params 'lat' and 'lon' must be numeric")
    try:
        return jsonify(get_kickoff_window(lat, lon, kickoff))
    except Exception as e:
        return _err(f"kickoff window fetch failed: {e}", 500)

@app.route("/cfb/weather/hourly")
def cfb_weather_hourly():
    e = _require(request.args, "lat","lon","start","end")
    if e: return _err(e)
    try:
        lat = float(request.args["lat"]); lon = float(request.args["lon"])
    except ValueError:
        return _err("params 'lat' and 'lon' must be numeric")
    start = request.args["start"]; end = request.args["end"]
    try:
        return jsonify(get_hourly_kickoff_window(lat, lon, start, end))
    except Exception as e:
        return _err(f"hourly window fetch failed: {e}", 500)

@app.route("/cfb/tempo")
def cfb_tempo():
    team = request.args.get("team")
    if not team: return _err("param 'team' is required")
    try:
        _install_cache_shim()
        from modules.tempo_plays import get_tempo
        return jsonify(get_tempo(team))
    except Exception as e:
        return _err(f"tempo fetch failed: {e}", 500)

@app.route("/cfb/injuries")
def cfb_injuries():
    team = request.args.get("team")
    if not team: return _err("param 'team' is required")
    try:
        _install_cache_shim()
        from modules.injuries_scraper import get_injuries
        return jsonify(get_injuries(team))
    except Exception as e:
        return _err(f"injuries fetch failed: {e}", 500)

@app.route("/cfb/spread/edge")
def cfb_spread_edge():
    e = _require(request.args, "team_sp","opp_sp","line")
    if e: return _err(e)
    try:
        team_sp = float(request.args["team_sp"]); opp_sp = float(request.args["opp_sp"]); line = float(request.args["line"])
    except ValueError:
        return _err("params 'team_sp', 'opp_sp', and 'line' must be numeric")
    try:
        return jsonify(calculate_spread_edge(team_sp, opp_sp, line))
    except Exception as e:
        return _err(f"edge calc failed: {e}", 500)

# ----------------------- bridge: build_inputs (validation-first) -----------------------
@app.route("/cfb/build_inputs", methods=["GET","POST"])
def cfb_build_inputs():
    """
    Returns model-ready JSON skeleton. No fabrication per your laws:
    - If fields can't be derived from available modules, they are returned as null
      and listed in 'missing'.
    - Clients can fill and POST to /cfb/run_model.
    """
    if request.method == "POST" and request.is_json:
        payload = request.get_json(silent=True) or {}
        # Pass-through (useful if client already assembled inputs)
        inputs = payload.get("inputs", {})
        market = payload.get("market", {})
    else:
        # Minimal sketch from query params; most fields remain null.
        q = request.args
        inputs = {
            "offense_home": None, "defense_home": None,
            "offense_away": None, "defense_away": None,
            "home_field_points": None, "rest_diff_days": None,
            "away_travel_miles": None, "qb_home_delta": None, "qb_away_delta": None,
            "key_injuries_home": None, "key_injuries_away": None,
            "wind_mph": None, "pass_rate_home": None, "pass_rate_away": None,
        }
        market = {"spread": None, "odds_home": None, "odds_away": None}

    expected_inputs = set([
        "offense_home","defense_home","offense_away","defense_away",
        "home_field_points","rest_diff_days","away_travel_miles",
        "qb_home_delta","qb_away_delta","key_injuries_home","key_injuries_away",
        "wind_mph","pass_rate_home","pass_rate_away",
    ])
    expected_market = set(["spread","odds_home","odds_away"])

    missing = [k for k in sorted(expected_inputs) if inputs.get(k) in (None,"")]
    missing += [f"market.{k}" for k in sorted(expected_market) if market.get(k) in (None,"")]

    return jsonify({
        "inputs": inputs,
        "market": market,
        "missing": missing,
        "note": "Populate missing fields with numeric values; then POST to /cfb/run_model.",
    })

# ------------------------- deterministic model (v2) -------------------------
def _american_to_decimal(odds: float) -> float:
    if odds > 0: return 1 + odds/100.0
    if odds < 0: return 1 + (100.0/abs(odds))
    return 1.0

def _phi(x: float) -> float:
    # Normal CDF via erf
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def run_cfb_model_v2(inputs: Dict[str, float], market: Dict[str, float]) -> Dict[str, Any]:
    # Coefficients from your spec
    b_matchup = 7.0
    b_hfa = 1.2
    b_rest = 0.15
    b_travel = -0.10
    b_qb = 3.0
    b_injury = 0.35
    b_weather = 0.03
    sigma_base = 14.0
    lam = 0.834421

    # Step 1: matchup gap
    matchup_gap = (inputs["offense_home"] - inputs["defense_away"]) - (inputs["offense_away"] - inputs["defense_home"])

    # Step 2: expected margin E[m]
    em = (
        b_matchup * matchup_gap
        + b_hfa
        + b_rest * inputs["rest_diff_days"]
        + b_travel * (inputs["away_travel_miles"] / 500.0)
        + b_qb * (inputs["qb_home_delta"] - inputs["qb_away_delta"])
        + b_injury * (-inputs["key_injuries_home"] + inputs["key_injuries_away"])
        + b_weather * (inputs["wind_mph"] * (inputs["pass_rate_home"] - inputs["pass_rate_away"]))
    )

    # Step 3: variance adjustment
    wind = max(0.0, inputs["wind_mph"] - 10.0)
    inj_total = inputs["key_injuries_home"] + inputs["key_injuries_away"]
    sigma = sigma_base * (1 + 0.01 * wind) * (1 + 0.03 * inj_total)

    # Step 4: recency weighting
    n_eff = min(12.0, 1.0 / (1.0 - lam))
    sigma_adj = sigma / math.sqrt(n_eff / 4.0)

    # Step 5: probability of cover
    S = market["spread"]
    z_cover = (em - S) / sigma_adj
    p_home_cover = _phi(z_cover)
    p_away_cover = 1.0 - p_home_cover

    # Step 6: win probability
    p_home_win = _phi(em / sigma_adj)
    p_away_win = 1.0 - p_home_win

    # Step 7: confidence intervals
    ci68 = [em - sigma_adj, em + sigma_adj]
    ci95 = [em - 1.96 * sigma_adj, em + 1.96 * sigma_adj]

    # Step 8: reliability (R^2-like)
    R2 = 0.65 * (1 - min(0.35, sigma / 20.0)) * (0.85 + 0.15 * min(1.0, abs(em - S) / 7.0))
    R2 = max(0.0, min(0.95, R2))

    # Step 9: expected value
    odds_home = market["odds_home"]; odds_away = market["odds_away"]
    dec_home = _american_to_decimal(odds_home)
    dec_away = _american_to_decimal(odds_away)

    ev_home = p_home_win * (dec_home - 1.0) - (1.0 - p_home_win)
    ev_away = p_away_win * (dec_away - 1.0) - (1.0 - p_away_win)

    # Step 10: Kelly (quarter)
    def _kelly(p: float, dec: float) -> float:
        b = dec - 1.0
        q = 1.0 - p
        f_star = (b * p - q) / b if b > 0 else 0.0
        return max(0.0, 0.25 * f_star)

    k_home = _kelly(p_home_win, dec_home)
    k_away = _kelly(p_away_win, dec_away)

    # Step 11: edge confidence
    edge_conf = max(0.0, min(1.0, (abs(z_cover) / 2.5) * R2))

    # Recommendation
    rec = {"side": "no_bet", "edge_ev_per_$1": 0.0, "recommended_fraction_bankroll_quarter_kelly": 0.0}
    if ev_home >= 0.03 or ev_away >= 0.03:
        if ev_home >= ev_away:
            rec = {"side": "home", "edge_ev_per_$1": ev_home, "recommended_fraction_bankroll_quarter_kelly": k_home}
        else:
            rec = {"side": "away", "edge_ev_per_$1": ev_away, "recommended_fraction_bankroll_quarter_kelly": k_away}

    return {
        "spread_pred": em,
        "win_prob_home": p_home_win,
        "win_prob_away": p_away_win,
        "prob_home_cover": p_home_cover,
        "variance": sigma_adj ** 2,
        "confidence_interval": {"ci68": ci68, "ci95": ci95},
        "r2_reliability": R2,
        "edge_confidence": edge_conf,
        "recommendation": rec,
        "metadata": {
            "model": {"name": "cfb_spread_model_v2", "version": "2.0.0", "lambda": 0.834421, "seed": 42},
        },
    }

# ------------------------------ run_model API ------------------------------
@app.route("/cfb/run_model", methods=["POST"])
def cfb_run_model():
    """
    Validation first (your Law #1). Reject if schema invalid; no guessing.
    """
    if not request.is_json:
        return _err("Content-Type must be application/json")
    payload = request.get_json(silent=True) or {}
    if "inputs" not in payload or "market" not in payload:
        return _err("JSON must include 'inputs' and 'market' sections")

    # Strict validation
    if not validate_input(payload):
        return _err("validation failed; use /cfb/build_inputs to construct valid payload", 400)

    try:
        result = run_cfb_model_v2(payload["inputs"], payload["market"])
        return jsonify({"status": "ok", "model_output": result})
    except Exception as e:
        # Why: transparent errors per your laws; avoid silent failures.
        return _err(f"model execution failed: {e}", 500)

# ------------------------------ server ------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
