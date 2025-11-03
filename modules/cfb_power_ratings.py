import requests
from bs4 import BeautifulSoup

def get_massey_ratings():
    url = "https://masseyratings.com/cf/compare.htm"
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    return {"rows": len(table.find_all('tr'))} if table else {"error": "Failed to scrape"}
