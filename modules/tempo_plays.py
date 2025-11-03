import os
import requests
from statistics import mean
from modules.cache_utils import load_cache, save_cache  # new shared cache utilities

CFB_API = "https://api.collegefootballdata.com"
CFB_KEY = os.getenv("CFBD_API_KEY", "")


def get_tempo(team: str):
    """
    Returns team tempo metrics derived from drive-level stats:
    - plays_per_game: estimated from average plays × ~12 drives/game
    - plays_per_minute: normalized per minute of drive time
    Includes 6-hour cache to avoid redundant CFBD API calls.
    """

    cache_key = f"tempo_{team.lower()}"
    cached = load_cache(cache_key)
    if cached:
        return cached

    headers = {"Authorization": f"Bearer {CFB_KEY}"} if CFB_KEY else {}
    url = f"{CFB_API}/drives"
    params = {"year": 2025, "team": team}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        if not data:
            return {"error": f"no drive data found for {team}"}

        total_plays = []
        durations = []

        for d in data:
            # plays count per drive
            if "plays" in d:
                total_plays.append(d["plays"])

            # parse drive duration in "mm:ss" safely
            if "driveTime" in d and isinstance(d["driveTime"], str):
                try:
                    mm, ss = map(int, d["driveTime"].split(":"))
                    durations.append(mm + ss / 60)
                except Exception:
                    pass

        if not total_plays:
            return {"error": f"no tempo data found for {team}"}

        avg_plays = mean(total_plays)
        avg_duration = mean(durations) if durations else 2.5  # fallback 2.5 min per drive

        plays_per_game = avg_plays * 12  # ~12 drives per game estimate
        plays_per_minute = round(plays_per_game / (avg_duration * 12), 3)

        result = {
            "plays_per_game": round(plays_per_game, 3),
            "plays_per_minute": plays_per_minute,
        }

        # Save to cache for 6 hours
        save_cache(cache_key, result)
        return result

    except Exception as e:
        return {"error": f"tempo fetch failed: {str(e)}"}
