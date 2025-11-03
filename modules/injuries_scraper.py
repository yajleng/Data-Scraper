import os
import requests
from bs4 import BeautifulSoup
from modules.cache_utils import load_cache, save_cache  # new shared cache utility

CFB_API = "https://api.collegefootballdata.com"
CFB_KEY = os.getenv("CFBD_API_KEY", "")


def get_injuries(team_name: str):
    """
    Attempt ESPN scrape; if forbidden or fails, fallback to CFBD injuries API.
    Uses 6-hour caching to minimize redundant fetches.
    """

    cache_key = f"injuries_{team_name.lower()}"
    cached = load_cache(cache_key)
    if cached:
        return cached

    team_url = team_name.lower().replace(" ", "-")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        )
    }

    espn_url = f"https://www.espn.com/college-football/team/injuries/_/name/{team_url}"

    try:
        resp = requests.get(espn_url, headers=headers, timeout=10)
        # --- fallback if blocked or 403 forbidden
        if resp.status_code == 403:
            cfb_headers = {"Authorization": f"Bearer {CFB_KEY}"} if CFB_KEY else {}
            r2 = requests.get(f"{CFB_API}/injuries", headers=cfb_headers, timeout=10)
            r2.raise_for_status()
            data = r2.json()

            filtered = [inj for inj in data if inj.get("team", "").lower() == team_name.lower()]
            result = filtered if filtered else {"message": f"no injuries found for {team_name}"}
            save_cache(cache_key, result)
            return result

        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # --- ESPN parsing: dynamically find rows
        rows = soup.select("tr.Table__TR")
        injuries = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 3:
                player = cols[0].get_text(strip=True)
                status = cols[-1].get_text(strip=True)
                if player and status and status.lower() not in ("-", "—", "none"):
                    injuries.append({"player": player, "status": status})

        if not injuries:
            result = {"message": f"no active injuries found for {team_name}"}
            save_cache(cache_key, result)
            return result

        save_cache(cache_key, injuries)
        return injuries

    except Exception as e:
        return {"error": f"injury fetch failed: {str(e)}"}
