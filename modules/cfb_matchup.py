
import requests
import os

CFBD_API_KEY = os.getenv("CFBD_API_KEY")
BASE_URL = "https://api.collegefootballdata.com"

def get_team_matchup(team1: str, team2: str, year: int):
    url = f"{BASE_URL}/teams/matchup?team1={team1}&team2={team2}&year={year}"
    headers = {"Authorization": f"Bearer {CFBD_API_KEY}"}
    r = requests.get(url, headers=headers, timeout=10)
    return r.json() if r.status_code == 200 else {"error": r.text}
