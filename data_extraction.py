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

    def download_champions_player_advanced_stats(self):
        champions_dir = os.path.join(DATA_DIR, "champions_since_2000")

        def season_str(year):
            y = int(year)
            return f"{y - 1}-{str(y)[2:]}"

        for entry in sorted(os.scandir(champions_dir), key=lambda e: e.name):
            if not entry.is_dir():
                continue
            parts = entry.name.split("_")
            if len(parts) != 2:
                continue
            year, team_abbr = parts
            season = season_str(year)
            out_path = os.path.join(entry.path, "advanced_stats.csv")

            if os.path.exists(out_path):
                print(f"Skipping {year} {team_abbr} — already saved")
                continue

            print(f"Processing {year} {team_abbr} ({season})...")

            # Re-fetch team page to get player hrefs from the roster table
            try:
                roster_html = self._fetch_html(
                    f"https://www.basketball-reference.com/teams/{team_abbr}/{year}.html"
                )
            except Exception as e:
                print(f"  Could not fetch roster page: {e}")
                continue
            time.sleep(3)

            roster_table = self._find_table(roster_html, "roster")
            if roster_table is None:
                print(f"  Could not find roster table")
                continue

            player_links = {}
            for row in roster_table.find_all("tr"):
                cell = row.find("td", {"data-stat": "player"})
                if cell is None:
                    continue
                link = cell.find("a")
                if link and link.get("href"):
                    player_links[link.get_text(strip=True)] = link["href"]

            rows = []
            for player_name, href in player_links.items():
                print(f"  Fetching {player_name}...")
                try:
                    player_html = self._fetch_html(
                        f"https://www.basketball-reference.com{href}"
                    )
                except Exception as e:
                    print(f"    Could not fetch player page: {e}")
                    time.sleep(3)
                    continue
                time.sleep(3)

                adv_table = self._find_table(player_html, "advanced")
                if adv_table is None:
                    print(f"    No advanced stats table found")
                    continue

                target_row = None
                for tr in adv_table.find_all("tr"):
                    season_cell = tr.find(["td", "th"], {"data-stat": "year_id"})
                    team_cell = tr.find(["td", "th"], {"data-stat": "team_name_abbr"})
                    if not season_cell or not team_cell:
                        continue
                    if season_cell.get_text(strip=True) == season and team_cell.get_text(strip=True) == team_abbr:
                        target_row = tr
                        break

                if target_row is None:
                    print(f"    No row for {season} {team_abbr}")
                    continue

                row_data = {"Player": player_name}
                for cell in target_row.find_all(["td", "th"]):
                    stat = cell.get("data-stat")
                    if stat:
                        row_data[stat] = cell.get_text(strip=True)
                rows.append(row_data)

            if rows:
                pd.DataFrame(rows).to_csv(out_path, index=False)
                print(f"  Saved {out_path} ({len(rows)} players)")
            else:
                print(f"  No rows collected for {year} {team_abbr}")

    def download_sac_player_advanced_stats(self):
        sac_dir = os.path.join(DATA_DIR, "SAC_since_2000")

        def season_str(year):
            y = int(year)
            return f"{y - 1}-{str(y)[2:]}"

        for entry in sorted(os.scandir(sac_dir), key=lambda e: e.name):
            if not entry.is_dir():
                continue
            year = entry.name
            if not year.isdigit():
                continue
            season = season_str(year)
            out_path = os.path.join(entry.path, "advanced_stats.csv")

            if os.path.exists(out_path):
                print(f"Skipping SAC {year} — already saved")
                continue

            print(f"Processing SAC {year} ({season})...")

            try:
                roster_html = self._fetch_html(
                    f"https://www.basketball-reference.com/teams/SAC/{year}.html"
                )
            except Exception as e:
                print(f"  Could not fetch roster page: {e}")
                continue
            time.sleep(3)

            roster_table = self._find_table(roster_html, "roster")
            if roster_table is None:
                print(f"  Could not find roster table")
                continue

            player_links = {}
            for row in roster_table.find_all("tr"):
                cell = row.find("td", {"data-stat": "player"})
                if cell is None:
                    continue
                link = cell.find("a")
                if link and link.get("href"):
                    player_links[link.get_text(strip=True)] = link["href"]

            rows = []
            for player_name, href in player_links.items():
                print(f"  Fetching {player_name}...")
                try:
                    player_html = self._fetch_html(
                        f"https://www.basketball-reference.com{href}"
                    )
                except Exception as e:
                    print(f"    Could not fetch player page: {e}")
                    time.sleep(3)
                    continue
                time.sleep(3)

                adv_table = self._find_table(player_html, "advanced")
                if adv_table is None:
                    print(f"    No advanced stats table found")
                    continue

                target_row = None
                for tr in adv_table.find_all("tr"):
                    season_cell = tr.find(["td", "th"], {"data-stat": "year_id"})
                    team_cell = tr.find(["td", "th"], {"data-stat": "team_name_abbr"})
                    if not season_cell or not team_cell:
                        continue
                    if season_cell.get_text(strip=True) == season and team_cell.get_text(strip=True) == "SAC":
                        target_row = tr
                        break

                if target_row is None:
                    print(f"    No row for {season} SAC")
                    continue

                row_data = {"Player": player_name}
                for cell in target_row.find_all(["td", "th"]):
                    stat = cell.get("data-stat")
                    if stat:
                        row_data[stat] = cell.get_text(strip=True)
                rows.append(row_data)

            if rows:
                pd.DataFrame(rows).to_csv(out_path, index=False)
                print(f"  Saved {out_path} ({len(rows)} players)")
            else:
                print(f"  No rows collected for SAC {year}")

    def run_all(self):
        self.download_team_stats()
        self.download_historic_team_players()
        self.download_historic_team_coaches()
        self.download_historic_executives()
        self.download_leage_avgs()
        self.download_team_ovr()

# extract_data = DataExtraction()
# extract_data.run_all()
# extractor = DataExtraction()
# extractor.download_sac_player_advanced_stats()

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

def download_last_20_champions():
    out_dir = os.path.join(os.path.dirname(__file__), "data", "champions_since_2000")
    os.makedirs(out_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def find_table(html, table_id):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"id": table_id})
        if table is None:
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment_soup = BeautifulSoup(comment, "html.parser")
                table = comment_soup.find("table", {"id": table_id})
                if table:
                    break
        return table

    print("Fetching champions list...")
    response = requests.get("https://www.basketball-reference.com/playoffs/", headers=headers)
    response.raise_for_status()
    time.sleep(3)

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"id": "champions_index"})
    if table is None:
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment_soup = BeautifulSoup(comment, "html.parser")
            table = comment_soup.find("table", {"id": "champions_index"})
            if table:
                break

    if table is None:
        print("Could not find champions table")
        return

    # Extract (year, team_abbr) by parsing the champion cell's href: /teams/DEN/2023.html
    champions = []
    for row in table.find_all("tr"):
        year_cell = row.find(["td", "th"], {"data-stat": "year_id"})
        champ_cell = row.find(["td", "th"], {"data-stat": "champion"})
        if not year_cell or not champ_cell:
            continue
        year_link = year_cell.find("a")
        champ_link = champ_cell.find("a")
        if not year_link or not champ_link:
            continue
        year = year_link.get_text(strip=True)
        if int(year) < 2000:
            continue
        parts = champ_link.get("href", "").strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "teams":
            champions.append((year, parts[1]))

    # Process oldest -> newest for cleaner output
    champions.reverse()

    for year, team_abbr in champions:
        print(f"Processing {year} champion: {team_abbr}...")
        team_dir = os.path.join(out_dir, f"{year}_{team_abbr}")
        os.makedirs(team_dir, exist_ok=True)

        # Roster
        roster_html = requests.get(
            f"https://www.basketball-reference.com/teams/{team_abbr}/{year}.html",
            headers=headers
        ).text
        time.sleep(3)
        roster_table = find_table(roster_html, "roster")
        if roster_table is not None:
            roster_df = pd.read_html(StringIO(str(roster_table)))[0]
            roster_df.to_csv(os.path.join(team_dir, "roster.csv"), index=False)
            print(f"  Saved roster ({len(roster_df)} players)")
        else:
            print(f"  Could not find roster table for {team_abbr} {year}")

        # Regular season gamelog
        gamelog_html = requests.get(
            f"https://www.basketball-reference.com/teams/{team_abbr}/{year}/gamelog/",
            headers=headers
        ).text
        time.sleep(3)
        gamelog_table = find_table(gamelog_html, "team_game_log_reg")
        if gamelog_table is not None:
            gamelog_df = pd.read_html(StringIO(str(gamelog_table)), header=1)[0]
            # Drop repeated header rows basketball-reference inserts every N rows
            gamelog_df = gamelog_df[gamelog_df.iloc[:, 0] != gamelog_df.columns[0]].reset_index(drop=True)
            gamelog_df.to_csv(os.path.join(team_dir, "gamelog.csv"), index=False)
            print(f"  Saved gamelog ({len(gamelog_df)} games)")
        else:
            print(f"  Could not find gamelog table for {team_abbr} {year}")

# download_last_20_champions()

def download_champions_advanced_stats():
    import re
    out_path = os.path.join(os.path.dirname(__file__), "data", "champions_advanced_stats.csv")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    print("Fetching champions list...")
    response = requests.get("https://www.basketball-reference.com/playoffs/", headers=headers)
    response.raise_for_status()
    time.sleep(3)

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"id": "champions_index"})
    if table is None:
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment_soup = BeautifulSoup(comment, "html.parser")
            table = comment_soup.find("table", {"id": "champions_index"})
            if table:
                break

    if table is None:
        print("Could not find champions table")
        return

    champions = []
    for row in table.find_all("tr"):
        year_cell = row.find(["td", "th"], {"data-stat": "year_id"})
        champ_cell = row.find(["td", "th"], {"data-stat": "champion"})
        if not year_cell or not champ_cell:
            continue
        year_link = year_cell.find("a")
        champ_link = champ_cell.find("a")
        if not year_link or not champ_link:
            continue
        year = year_link.get_text(strip=True)
        if int(year) < 2000:
            continue
        parts = champ_link.get("href", "").strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "teams":
            champions.append((year, parts[1]))
    champions.reverse()

    # Matches "12.34 (5th of 30)" -> value, rank, league size
    stat_pattern = re.compile(r"([+-]?\d+\.?\d*)\s*\((\d+)\w+\s+of\s+(\d+)\)")
    stat_labels = ["Off Rtg", "Def Rtg", "SRS", "Pace"]

    rows = []
    for year, team_abbr in champions:
        print(f"Fetching advanced stats for {year} {team_abbr}...")
        url = f"https://www.basketball-reference.com/teams/{team_abbr}/{year}/gamelog/"
        html = requests.get(url, headers=headers).text
        time.sleep(3)
        page = BeautifulSoup(html, "html.parser")

        row = {"year": year, "team": team_abbr}
        for label in stat_labels:
            strong = page.find("strong", string=label)
            sibling_text = ""
            if strong is not None:
                # Walk siblings until next <strong>; this isolates the value belonging to this label
                for sib in strong.next_siblings:
                    if getattr(sib, "name", None) == "strong":
                        break
                    sibling_text += sib.get_text() if hasattr(sib, "get_text") else str(sib)
            match = stat_pattern.search(sibling_text)
            if match:
                row[f"{label}_value"] = float(match.group(1))
                row[f"{label}_rank"] = int(match.group(2))
                row[f"{label}_of"] = int(match.group(3))
            else:
                row[f"{label}_value"] = None
                row[f"{label}_rank"] = None
                row[f"{label}_of"] = None
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    print(f"Saved {out_path} ({len(df)} rows)")

# download_champions_advanced_stats()

def download_sac_since_2000():
    import re
    out_dir = os.path.join(os.path.dirname(__file__), "data", "SAC_since_2000")
    os.makedirs(out_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def find_table(html, table_id):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"id": table_id})
        if table is None:
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment_soup = BeautifulSoup(comment, "html.parser")
                table = comment_soup.find("table", {"id": table_id})
                if table:
                    break
        return table

    stat_pattern = re.compile(r"([+-]?\d+\.?\d*)\s*\((\d+)\w+\s+of\s+(\d+)\)")
    stat_labels = ["Off Rtg", "Def Rtg", "SRS", "Pace"]
    advanced_rows = []

    for year in range(2000, 2027):
        print(f"Processing SAC {year}...")
        season_dir = os.path.join(out_dir, str(year))
        os.makedirs(season_dir, exist_ok=True)

        # Roster
        try:
            roster_resp = requests.get(
                f"https://www.basketball-reference.com/teams/SAC/{year}.html",
                headers=headers
            )
            roster_resp.raise_for_status()
            roster_html = roster_resp.text
        except requests.HTTPError:
            print(f"  Could not fetch season page for {year}, skipping")
            continue
        time.sleep(3)
        roster_table = find_table(roster_html, "roster")
        if roster_table is not None:
            roster_df = pd.read_html(StringIO(str(roster_table)))[0]
            roster_df.to_csv(os.path.join(season_dir, "roster.csv"), index=False)
            print(f"  Saved roster ({len(roster_df)} players)")
        else:
            print(f"  Could not find roster table for {year}")

        # Regular season gamelog + advanced stats (both on the gamelog page)
        gamelog_html = requests.get(
            f"https://www.basketball-reference.com/teams/SAC/{year}/gamelog/",
            headers=headers
        ).text
        time.sleep(3)

        gamelog_table = find_table(gamelog_html, "team_game_log_reg")
        if gamelog_table is not None:
            gamelog_df = pd.read_html(StringIO(str(gamelog_table)), header=1)[0]
            gamelog_df = gamelog_df[gamelog_df.iloc[:, 0] != gamelog_df.columns[0]].reset_index(drop=True)
            gamelog_df.to_csv(os.path.join(season_dir, "gamelog.csv"), index=False)
            print(f"  Saved gamelog ({len(gamelog_df)} games)")
        else:
            print(f"  Could not find gamelog table for {year}")

        # Advanced stats (Off Rtg, Def Rtg, SRS, Pace) from the gamelog page
        page = BeautifulSoup(gamelog_html, "html.parser")
        row = {"year": year, "team": "SAC"}
        for label in stat_labels:
            strong = page.find("strong", string=label)
            sibling_text = ""
            if strong is not None:
                for sib in strong.next_siblings:
                    if getattr(sib, "name", None) == "strong":
                        break
                    sibling_text += sib.get_text() if hasattr(sib, "get_text") else str(sib)
            match = stat_pattern.search(sibling_text)
            if match:
                row[f"{label}_value"] = float(match.group(1))
                row[f"{label}_rank"] = int(match.group(2))
                row[f"{label}_of"] = int(match.group(3))
            else:
                row[f"{label}_value"] = None
                row[f"{label}_rank"] = None
                row[f"{label}_of"] = None
        advanced_rows.append(row)

    if advanced_rows:
        adv_df = pd.DataFrame(advanced_rows)
        adv_path = os.path.join(out_dir, "SAC_advanced_stats.csv")
        adv_df.to_csv(adv_path, index=False)
        print(f"Saved {adv_path} ({len(adv_df)} rows)")

# download_sac_since_2000()

def download_sac_coaches():
    out_path = os.path.join(DATA_DIR, "SAC_coaches.csv")
    os.makedirs(DATA_DIR, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    print("Fetching SAC coaches...")
    response = requests.get("https://www.basketball-reference.com/teams/SAC/coaches.html", headers=headers)
    response.raise_for_status()
    time.sleep(3)

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"id": "coaches"})
    if table is None:
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment_soup = BeautifulSoup(comment, "html.parser")
            table = comment_soup.find("table", {"id": "coaches"})
            if table:
                break

    if table is None:
        print("Could not find coaches table")
        return

    df = pd.read_html(StringIO(str(table)), header=1)[0]
    df.to_csv(out_path, index=False)
    print(f"Saved {out_path} ({len(df)} rows)")

# download_sac_coaches()

def download_sac_gms():
    out_path = os.path.join(DATA_DIR, "SAC_GMs.csv")
    os.makedirs(DATA_DIR, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    print("Fetching SAC executives...")
    response = requests.get("https://www.basketball-reference.com/teams/SAC/executives.html", headers=headers)
    response.raise_for_status()
    time.sleep(3)

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"id": "executives"})
    if table is None:
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment_soup = BeautifulSoup(comment, "html.parser")
            table = comment_soup.find("table", {"id": "executives"})
            if table:
                break

    if table is None:
        print("Could not find executives table")
        return

    df = pd.read_html(StringIO(str(table)))[0]
    df.to_csv(out_path, index=False)
    print(f"Saved {out_path} ({len(df)} rows)")

# download_sac_gms()

def download_sac_draft_history():
    out_path = os.path.join(DATA_DIR, "SAC_draft_history.csv")
    os.makedirs(DATA_DIR, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    print("Fetching SAC draft history...")
    response = requests.get("https://www.basketball-reference.com/teams/SAC/draft.html", headers=headers)
    response.raise_for_status()
    time.sleep(3)

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", {"id": "draft"})
    if table is None:
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment_soup = BeautifulSoup(comment, "html.parser")
            table = comment_soup.find("table", {"id": "draft"})
            if table:
                break

    if table is None:
        print("Could not find draft table")
        return

    df = pd.read_html(StringIO(str(table)), header=1)[0]
    df.to_csv(out_path, index=False)
    print(f"Saved {out_path} ({len(df)} rows)")

# download_sac_draft_history()

def download_champions_mgmt_history():
    import shutil

    champions_dir = os.path.join(DATA_DIR, "champions_since_2000")
    mgmt_dir = os.path.join(DATA_DIR, "mgmt_history")
    src_dir = os.path.join(DATA_DIR, "NBA_champions_team_details")
    os.makedirs(mgmt_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def fetch_table(url, table_id, header_row=None):
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        time.sleep(3)
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", {"id": table_id})
        if table is None:
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment_soup = BeautifulSoup(comment, "html.parser")
                table = comment_soup.find("table", {"id": table_id})
                if table:
                    break
        if table is None:
            return None
        kwargs = {"header": header_row} if header_row is not None else {}
        return pd.read_html(StringIO(str(table)), **kwargs)[0]

    teams = set()
    for entry in os.scandir(champions_dir):
        if entry.is_dir() and "_" in entry.name:
            parts = entry.name.split("_", 1)
            if len(parts) == 2:
                teams.add(parts[1])

    file_specs = [
        # (dst_filename, src_filename_template, url_path, table_id, header_row)
        ("coaches.csv",       "{team}_coaches.csv",    "coaches.html",    "coaches",    1),
        ("executives.csv",    "{team}_executives.csv", "executives.html", "executives", None),
        ("draft_history.csv", None,                    "draft.html",      "draft",      1),
    ]

    for team in sorted(teams):
        team_dir = os.path.join(mgmt_dir, team)
        os.makedirs(team_dir, exist_ok=True)
        print(f"Processing {team}...")

        for dst_name, src_template, url_path, table_id, header_row in file_specs:
            dst_path = os.path.join(team_dir, dst_name)
            if os.path.exists(dst_path):
                print(f"  Skipping {dst_name} (already saved)")
                continue

            if src_template is not None:
                src_path = os.path.join(src_dir, src_template.format(team=team))
                if os.path.exists(src_path):
                    shutil.copy2(src_path, dst_path)
                    print(f"  Copied {dst_name} from existing")
                    continue

            url = f"https://www.basketball-reference.com/teams/{team}/{url_path}"
            print(f"  Fetching {dst_name} from {url}")
            df = fetch_table(url, table_id, header_row=header_row)
            if df is None:
                print(f"  Could not find {table_id} table for {team}")
                continue
            df.to_csv(dst_path, index=False)
            print(f"  Saved {dst_name} ({len(df)} rows)")

# download_champions_mgmt_history()

def download_champions_playoff_appearances():
    out_dir = os.path.join(DATA_DIR, "champions_playoff_appearances")
    champions_dir = os.path.join(DATA_DIR, "champions_since_2000")
    os.makedirs(out_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def find_table(html, table_id):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"id": table_id})
        if table is None:
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment_soup = BeautifulSoup(comment, "html.parser")
                table = comment_soup.find("table", {"id": table_id})
                if table:
                    break
        return table

    teams = set()
    for entry in os.scandir(champions_dir):
        if entry.is_dir() and "_" in entry.name:
            parts = entry.name.split("_", 1)
            if len(parts) == 2:
                teams.add(parts[1])

    for team in sorted(teams):
        out_path = os.path.join(out_dir, f"{team}.csv")
        if os.path.exists(out_path):
            print(f"Skipping {team} (already saved)")
            continue

        url = f"https://www.basketball-reference.com/teams/{team}/"
        print(f"Fetching {team} overview...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        time.sleep(3)

        table = find_table(response.text, team)
        if table is None:
            print(f"  Could not find overview table for {team}")
            continue

        df = pd.read_html(StringIO(str(table)))[0]
        # Drop the "Totals" / averages row at the top of the team overview table
        df = df.iloc[1:].reset_index(drop=True)
        df.to_csv(out_path, index=False)
        print(f"  Saved {out_path} ({len(df)} rows)")

# download_champions_playoff_appearances()

def download_coach_histories():
    out_dir_root = os.path.join(DATA_DIR, "mgmt_history")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    teams = sorted(e.name for e in os.scandir(out_dir_root) if e.is_dir())

    def find_table(html, table_id):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"id": table_id})
        if table is None:
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment_soup = BeautifulSoup(comment, "html.parser")
                table = comment_soup.find("table", {"id": table_id})
                if table:
                    break
        return table

    def season_end_year(s):
        if not isinstance(s, str) or "-" not in s:
            return None
        try:
            return int(s.split("-")[0]) + 1
        except ValueError:
            return None

    # Phase 1 — build (team, coach_name) -> coach_url lookup by re-fetching team coaches pages
    print("Phase 1: collecting coach URLs from team pages...")
    coach_urls = {}  # (team, name) -> "/coaches/xxxx.html"
    for team in teams:
        url = f"https://www.basketball-reference.com/teams/{team}/coaches.html"
        print(f"  fetching {team} coaches page...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        time.sleep(3)
        table = find_table(response.text, "coaches")
        if table is None:
            print(f"    Could not find coaches table for {team}")
            continue
        for tr in table.find_all("tr"):
            cell = tr.find(["td", "th"], {"data-stat": "coach"})
            if cell is None:
                continue
            link = cell.find("a")
            if link and link.get("href"):
                name = link.get_text(strip=True)
                coach_urls[(team, name)] = link["href"]

    print(f"  Got {len(coach_urls)} coach links across {len(teams)} teams")

    # Phase 2 — for each team, identify post-2000 coaches and fetch their pages
    for team in teams:
        out_path = os.path.join(out_dir_root, team, "coach_history.csv")
        if os.path.exists(out_path):
            print(f"Skipping {team} (coach_history.csv already exists)")
            continue

        coaches_csv = os.path.join(out_dir_root, team, "coaches.csv")
        if not os.path.exists(coaches_csv):
            print(f"Skipping {team} (no coaches.csv)")
            continue

        df_coaches = pd.read_csv(coaches_csv)
        if "To" not in df_coaches.columns or "Coach" not in df_coaches.columns:
            print(f"Skipping {team} (coaches.csv missing 'Coach'/'To' columns)")
            continue

        df_coaches["To"] = pd.to_numeric(df_coaches["To"], errors="coerce")
        post_2000 = df_coaches[df_coaches["To"] >= 2000]
        print(f"\nProcessing {team} — {len(post_2000)} post-2000 coaches")

        team_rows = []
        for _, row in post_2000.iterrows():
            name = row["Coach"]
            href = coach_urls.get((team, name))
            if not href:
                print(f"  No URL for {name} ({team}), skipping")
                continue
            coach_url = f"https://www.basketball-reference.com{href}"
            print(f"  fetching {name}...")
            try:
                resp = requests.get(coach_url, headers=headers)
                resp.raise_for_status()
            except requests.HTTPError as e:
                print(f"    HTTP error: {e}")
                time.sleep(3)
                continue
            time.sleep(3)

            table = find_table(resp.text, "coach-stats")
            if table is None:
                print(f"    No coach-stats table on {name}'s page")
                continue

            df = pd.read_html(StringIO(str(table)), header=1)[0]
            # Drop rows where the coach wasn't head coach this season ("Assistant Coach", "Associate Head Coach", etc.)
            df = df[pd.to_numeric(df["G"], errors="coerce").notna()]
            # Drop summary rows ("Career", "1 seasons", etc.)
            df = df[df["Season"].astype(str).str.match(r"^\d{4}-\d{2}$", na=False)]
            # Filter to this team and post-2000 seasons
            df = df[df["Tm"] == team]
            df["season_end_year"] = df["Season"].apply(season_end_year)
            df = df[df["season_end_year"] >= 2000].drop(columns=["season_end_year"])
            df["Coach"] = name
            team_rows.append(df)

        if team_rows:
            combined = pd.concat(team_rows, ignore_index=True)
            combined.to_csv(out_path, index=False)
            print(f"  Saved {out_path} ({len(combined)} rows)")
        else:
            print(f"  No rows collected for {team}")

# download_coach_histories()

def download_champions_playoffs_depth():
    """For each champion team's post-2000 playoff seasons, save per-player advanced stats.

    Skips SAC (we already have all seasons). For title-winning seasons that already
    exist in champions_since_2000/, copies the existing advanced_stats.csv.
    For other playoff seasons, fetches roster + each player's advanced stats fresh.
    Output: data/Champions_playoffs_depth/{team}_{year}.csv per (team, year) pair.
    """
    import shutil

    out_dir = os.path.join(DATA_DIR, "Champions_playoffs_depth")
    os.makedirs(out_dir, exist_ok=True)
    playoff_dir = os.path.join(DATA_DIR, "champions_playoff_appearances")
    title_dir = os.path.join(DATA_DIR, "champions_since_2000")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    def find_table(html, table_id):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"id": table_id})
        if table is None:
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment_soup = BeautifulSoup(comment, "html.parser")
                table = comment_soup.find("table", {"id": table_id})
                if table:
                    break
        return table

    def season_end(s):
        if not isinstance(s, str) or "-" not in s:
            return None
        try:
            return int(s.split("-")[0]) + 1
        except ValueError:
            return None

    # Build list of (team, year) pairs to process
    targets = []
    for f in sorted(os.listdir(playoff_dir)):
        if not f.endswith(".csv"):
            continue
        team = f.replace(".csv", "")
        if team == "SAC":  # already covered by SAC_since_2000
            continue
        df = pd.read_csv(os.path.join(playoff_dir, f))
        df["year"] = df["Season"].apply(season_end)
        playoff_rows = df[
            (df["year"] >= 2000)
            & df["Playoffs"].notna()
            & (df["Playoffs"].astype(str).str.strip() != "")
        ]
        for _, row in playoff_rows.iterrows():
            targets.append((team, int(row["year"])))

    print(f"Found {len(targets)} post-2000 playoff team-seasons to process")

    for team, year in targets:
        out_path = os.path.join(out_dir, f"{team}_{year}.csv")
        if os.path.exists(out_path):
            print(f"Skipping {team} {year} (already saved)")
            continue

        # Title seasons already have advanced_stats.csv — copy it
        title_path = os.path.join(title_dir, f"{year}_{team}", "advanced_stats.csv")
        if os.path.exists(title_path):
            shutil.copy2(title_path, out_path)
            print(f"Copied {team} {year} from existing title-season data")
            continue

        season = f"{year - 1}-{str(year)[2:]}"
        print(f"Fetching {team} {year} ({season})...")

        try:
            roster_resp = requests.get(
                f"https://www.basketball-reference.com/teams/{team}/{year}.html",
                headers=headers,
            )
            roster_resp.raise_for_status()
        except requests.HTTPError as e:
            print(f"  HTTP error on roster page: {e}")
            continue
        time.sleep(3)

        roster_table = find_table(roster_resp.text, "roster")
        if roster_table is None:
            print(f"  No roster table for {team} {year}")
            continue

        player_links = {}
        for tr in roster_table.find_all("tr"):
            cell = tr.find("td", {"data-stat": "player"})
            if cell is None:
                continue
            link = cell.find("a")
            if link and link.get("href"):
                player_links[link.get_text(strip=True)] = link["href"]

        rows = []
        for player_name, href in player_links.items():
            try:
                pr = requests.get(
                    f"https://www.basketball-reference.com{href}", headers=headers
                )
                pr.raise_for_status()
            except requests.HTTPError as e:
                print(f"    {player_name}: HTTP error {e}")
                time.sleep(3)
                continue
            time.sleep(3)

            adv_table = find_table(pr.text, "advanced")
            if adv_table is None:
                continue

            target_row = None
            for tr in adv_table.find_all("tr"):
                season_cell = tr.find(["td", "th"], {"data-stat": "year_id"})
                team_cell = tr.find(["td", "th"], {"data-stat": "team_name_abbr"})
                if not season_cell or not team_cell:
                    continue
                if (
                    season_cell.get_text(strip=True) == season
                    and team_cell.get_text(strip=True) == team
                ):
                    target_row = tr
                    break

            if target_row is None:
                continue

            row_data = {"Player": player_name}
            for cell in target_row.find_all(["td", "th"]):
                stat = cell.get("data-stat")
                if stat:
                    row_data[stat] = cell.get_text(strip=True)
            rows.append(row_data)

        if rows:
            pd.DataFrame(rows).to_csv(out_path, index=False)
            print(f"  Saved {out_path} ({len(rows)} players)")
        else:
            print(f"  No data collected for {team} {year}")

# download_champions_playoffs_depth()