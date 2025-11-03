import os
import requests
import time
from modules.normalization import preprocess_team_metrics

CFBD_API_KEY = os.getenv("CFBD_API_KEY")

# -----------------------------
# Helper: Generic GET request
# -----------------------------
def fetch_cfbd(endpoint, params=None):
    headers = {"Authorization": f"Bearer {CFBD_API_KEY}"}
    url = f"https://api.collegefootballdata.com/{endpoint}"
    resp = requests.get(url, headers=headers, params=params or {})
    if resp.status_code != 200:
        return {"error": f"CFBD API error {resp.status_code}", "content": resp.text}
    return resp.json()

# -----------------------------
# 1️⃣ TEAM INFO
# -----------------------------
def get_cfbd_team(name, year=2024):
    """
    Fetch team info + basic performance stats from CollegeFootballData API.
    """
    team_info = fetch_cfbd("teams", {"year": year})
    if isinstance(team_info, dict) and "error" in team_info:
        return team_info

    team = next((t for t in team_info if t["school"].lower() == name.lower()), None)
    if not team:
        return {"error": "Team not found", "match": None}

    # Get advanced stats
    adv_stats = fetch_cfbd("stats/season", {"year": year, "team": name})
    if isinstance(adv_stats, dict) and "error" in adv_stats:
        return adv_stats

    # Simplify and normalize
    simplified = []
    for stat in adv_stats:
        simplified.append({
            "team": name,
            "epa_off": stat.get("offense", {}).get("epaPerPlay", 0),
            "epa_def": stat.get("defense", {}).get("epaPerPlay", 0),
            "success_rate_off": stat.get("offense", {}).get("successRate", 0),
            "success_rate_def": stat.get("defense", {}).get("successRate", 0),
            "explosiveness": stat.get("offense", {}).get("explosiveness", 0),
        })

    normalized = preprocess_team_metrics(simplified)
    return {
        "source": "collegefootballdata",
        "team": name,
        "year": year,
        "timestamp": int(time.time()),
        "metrics": normalized,
    }

# -----------------------------
# 2️⃣ SportsData placeholder
# -----------------------------
def get_sportsdata_team_stats(name):
    """
    Optional future integration for SportsData.io
    (currently returns a message stub)
    """
    return {
        "team": name,
        "source": "sportsdata.io",
        "status": "not integrated",
        "timestamp": int(time.time()),
    }

# ----------------------------------------------------------------------
# Added helper wrappers for warmers.py compatibility
# ----------------------------------------------------------------------
def get_team_matchup(team: str, opp: str, year: int, week: int):
    """
    Lightweight wrapper to return matchup info.
    Replace this with your real logic if it already exists elsewhere.
    """
    try:
        from modules.cfb_extended import fetch_team_matchup  # if you have such a function
        return fetch_team_matchup(team, opp, year, week)
    except ImportError:
        # fallback: return empty dict
        return {"team": team, "opp": opp, "year": year, "week": week, "note": "placeholder"}


def get_lines(team: str, year: int, week: int):
    """
    Placeholder or wrapper for CFBD lines data.
    Adjust to call your actual data source if different.
    """
    try:
        from modules.cfb_extended import fetch_lines
        return fetch_lines(team, year, week)
    except ImportError:
        return {"team": team, "year": year, "week": week, "note": "placeholder"}

