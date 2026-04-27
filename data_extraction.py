import pandas as pd
from bs4 import BeautifulSoup, Comment
import requests
import os
import time
from io import StringIO


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


class DataExtraction:
    def __init__(self):
        self.home_url = "https://www.basketball-reference.com/"
        self.team_abrev = ["GSW", "LAL", "SAS", "MIA", "BOS", "SAC"]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def _fetch_html(self, url):
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.text

    def _find_table(self, html, table_id):
        soup = BeautifulSoup(html, "html.parser")

        # Try finding the table directly in the HTML
        table = soup.find("table", {"id": table_id})

        # Basketball-reference hides some tables inside HTML comments
        if table is None:
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment_soup = BeautifulSoup(comment, "html.parser")
                table = comment_soup.find("table", {"id": table_id})
                if table:
                    break

        return table

    def download_team_stats(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        for team in self.team_abrev:
            url = f"https://www.basketball-reference.com/teams/{team}/stats_basic_totals.html"
            print(f"Fetching {team}...")
            html = self._fetch_html(url)
            table = self._find_table(html, "stats")

            if table is None:
                print(f"  Could not find stats table for {team}")
                continue

            df = pd.read_html(StringIO(str(table)))[0]
            df = df.iloc[1:].reset_index(drop=True)
            out_path = os.path.join(DATA_DIR, f"{team}_stats.csv")
            df.to_csv(out_path, index=False)
            print(f"  Saved {out_path} ({len(df)} rows)")

            time.sleep(3)  # avoid hammering the server
        
    def download_historic_team_players(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        for team in self.team_abrev:
            url = f"https://www.basketball-reference.com/teams/{team}/players.html"
            print(f"Fetching {team} players...")
            html = self._fetch_html(url)
            table = self._find_table(html, "franchise_register")

            if table is None:
                print(f"  Could not find players table for {team}")
                continue

            df = pd.read_html(StringIO(str(table)), header=1)[0]
            out_path = os.path.join(DATA_DIR, f"{team}_players.csv")
            df.to_csv(out_path, index=False)
            print(f"  Saved {out_path} ({len(df)} rows)")

            time.sleep(3)  # avoid hammering the server

    def download_historic_team_coaches(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        for team in self.team_abrev:
            url = f"https://www.basketball-reference.com/teams/{team}/coaches.html"
            print(f"Fetching {team} coaches...")
            html = self._fetch_html(url)
            table = self._find_table(html, "coaches")

            if table is None:
                print(f"  Could not find coaches table for {team}")
                continue

            df = pd.read_html(StringIO(str(table)), header=1)[0]
            out_path = os.path.join(DATA_DIR, f"{team}_coaches.csv")
            df.to_csv(out_path, index=False)
            print(f"  Saved {out_path} ({len(df)} rows)")

            time.sleep(3)  # avoid hammering the server

    def download_historic_executives(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        for team in self.team_abrev:
            url = f"https://www.basketball-reference.com/teams/{team}/executives.html"
            print(f"Fetching {team} executives...")
            html = self._fetch_html(url)
            table = self._find_table(html, "executives")

            if table is None:
                print(f"  Could not find executives table for {team}")
                continue

            df = pd.read_html(StringIO(str(table)))[0]
            out_path = os.path.join(DATA_DIR, f"{team}_executives.csv")
            df.to_csv(out_path, index=False)
            print(f"  Saved {out_path} ({len(df)} rows)")

            time.sleep(3)  # avoid hammering the server

    def download_leage_avgs(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        url = "https://www.basketball-reference.com/leagues/NBA_stats_per_game.html"
        print("Fetching league averages...")
        html = self._fetch_html(url)
        table = self._find_table(html, "stats-Regular-Season")

        if table is None:
            print("  Could not find league averages table")
            return

        df = pd.read_html(StringIO(str(table)), header=1)[0]
        out_path = os.path.join(DATA_DIR, "league_avgs.csv")
        df.to_csv(out_path, index=False)
        print(f"  Saved {out_path} ({len(df)} rows)")

    def download_team_ovr(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        for team in self.team_abrev:
            url = f"https://www.basketball-reference.com/teams/{team}/"
            print(f"Fetching {team} overview...")
            html = self._fetch_html(url)
            table = self._find_table(html, team)

            if table is None:
                print(f"  Could not find overview table for {team}")
                continue

            df = pd.read_html(StringIO(str(table)))[0]
            df = df.iloc[1:].reset_index(drop=True)
            out_path = os.path.join(DATA_DIR, f"{team}_ovr.csv")
            df.to_csv(out_path, index=False)
            print(f"  Saved {out_path} ({len(df)} rows)")

            time.sleep(3)  # avoid hammering the server

    def run_all(self):
        self.download_team_stats()
        self.download_historic_team_players()
        self.download_historic_team_coaches()
        self.download_historic_executives()
        self.download_leage_avgs()
        self.download_team_ovr()

# extract_data = DataExtraction()
# extract_data.run_all()

def get_player_transactions_history():
    import json
    out_dir = os.path.join(os.path.dirname(__file__), "player_transaction_history")
    os.makedirs(out_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for year in range(1970, 2027):
        url = f"https://www.basketball-reference.com/leagues/NBA_{year}_transactions.html"
        print(f"Fetching {year} transactions...")

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.HTTPError:
            print(f"  No data for {year}, skipping")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.find("div", {"id": "content"})
        ul = content.find("ul", class_="page_index") if content else None

        if ul is None:
            print(f"  No transactions list found for {year}, skipping")
            continue

        records = []
        for li in ul.find_all("li", recursive=False):
            date_span = li.find("span")
            date = date_span.get_text(strip=True) if date_span else "Unknown"
            transactions = [p.get_text(strip=True) for p in li.find_all("p")]
            if transactions:
                records.append({"date": date, "transactions": transactions})

        out_path = os.path.join(out_dir, f"{year}_transactions.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        print(f"  Saved {out_path} ({len(records)} dates, {sum(len(r['transactions']) for r in records)} transactions)")

        time.sleep(3)

get_player_transactions_history()