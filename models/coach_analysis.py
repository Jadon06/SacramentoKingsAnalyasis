import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
MGMT_DIR = os.path.join(ROOT, "data", "mgmt_history")
PLAYOFFS_DIR = os.path.join(ROOT, "data", "champions_playoff_appearances")
CHAMPS_DIR = os.path.join(ROOT, "data", "champions_since_2000")
SAC_DIR = os.path.join(ROOT, "data", "SAC_since_2000")

def _load_team_advanced(team: str, year) -> pd.DataFrame | None:
    """Return per-player advanced stats for a (team, year) if available, else None."""
    if pd.isna(year):
        return None
    year = int(year)
    if team == "SAC":
        path = os.path.join(SAC_DIR, str(year), "advanced_stats.csv")
    else:
        path = os.path.join(CHAMPS_DIR, f"{year}_{team}", "advanced_stats.csv")
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def _compute_depth_score(df_adv: pd.DataFrame | None) -> float | None:
    """Depth = mean(non-top-2 VORP) + min over positions of best player's VORP.

    Mirrors the calculate_depth() formula from roster_analysis.py.
    """
    if df_adv is None or "vorp" not in df_adv.columns or "pos" not in df_adv.columns:
        return None
    df = df_adv.copy()
    df["vorp"] = pd.to_numeric(df["vorp"], errors="coerce")
    df = df.dropna(subset=["vorp"])
    if len(df) < 3:
        return None
    non_star = df.sort_values("vorp", ascending=False)["vorp"].iloc[2:].mean()
    weakest_pos = df.groupby("pos")["vorp"].max().min()
    if pd.isna(non_star) or pd.isna(weakest_pos):
        return None
    return float(non_star + weakest_pos)


def load_playoff_history(include_depth: bool = True) -> pd.DataFrame:
    """Per-team season-by-season W/L/Playoffs records for all 13 teams.

    `Season` is preserved as the "YYYY-YY" string from basketball-reference;
    `season_end_year` is added for easy filtering/joining (e.g., 2024 for "2023-24").

    If `include_depth=True`, a `depth_score` column is added — populated for
    SAC every season and for champion teams only in their title-winning years
    (NaN otherwise, since per-player advanced stats only exist for those rows).
    """
    frames = []
    for entry in sorted(os.scandir(PLAYOFFS_DIR), key=lambda e: e.name):
        if not entry.is_file() or not entry.name.endswith(".csv"):
            continue
        df = pd.read_csv(entry.path)
        df["team"] = entry.name.replace(".csv", "")
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)

    def _end_year(s):
        if not isinstance(s, str) or "-" not in s:
            return None
        try:
            return int(s.split("-")[0]) + 1
        except ValueError:
            return None

    out["season_end_year"] = out["Season"].apply(_end_year)

    if include_depth:
        out["depth_score"] = out.apply(
            lambda r: _compute_depth_score(_load_team_advanced(r["team"], r["season_end_year"])),
            axis=1,
        )

    return out

def load_coach_histories() -> pd.DataFrame:
    frames = []
    for entry in sorted(os.scandir(MGMT_DIR), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        path = os.path.join(entry.path, "coach_history.csv")
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        df["team"] = entry.name
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_champion_depth_scores() -> pd.DataFrame:
    """One row per championship team-season with its depth score.

    Iterates `data/champions_since_2000/{year}_{team}/` folders and runs the
    same depth formula used in `load_playoff_history`. Returns columns:
    `team, season_end_year, depth_score`.
    """
    rows = []
    for entry in sorted(os.scandir(CHAMPS_DIR), key=lambda e: e.name):
        if not entry.is_dir() or "_" not in entry.name:
            continue
        year_str, team = entry.name.split("_", 1)
        try:
            year = int(year_str)
        except ValueError:
            continue
        depth = _compute_depth_score(_load_team_advanced(team, year))
        rows.append({"team": team, "season_end_year": year, "depth_score": depth})
    return pd.DataFrame(rows)


def load_sac_depth_scores() -> pd.DataFrame:
    """One row per SAC season (post-2000) with its depth score.

    Iterates `data/SAC_since_2000/{year}/` folders and runs the same depth
    formula. Returns columns: `team, season_end_year, depth_score`.
    """
    rows = []
    for entry in sorted(os.scandir(SAC_DIR), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        try:
            year = int(entry.name)
        except ValueError:
            continue
        depth = _compute_depth_score(_load_team_advanced("SAC", year))
        rows.append({"team": "SAC", "season_end_year": year, "depth_score": depth})
    return pd.DataFrame(rows)


def load_sac_coach_history() -> pd.DataFrame:
    """SAC's per-season coaching record (post-2000 only — coach_history.csv was scraped with that filter)."""
    path = os.path.join(MGMT_DIR, "SAC", "coach_history.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["team"] = "SAC"
    return df

df_sac_depth = load_sac_depth_scores()
df_sac_depth.sort_values("depth_score", ascending=False, inplace=True)
print(df_sac_depth["depth_score"].mean())
print(df_sac_depth.to_string(index=False))

df_champ_depth = load_champion_depth_scores()
df_champ_depth.sort_values("depth_score", ascending=True, inplace=True)
print(df_champ_depth.to_string(index=False))

df_coaches = load_coach_histories()
df_coaches.drop(columns=["Unnamed: 10"], inplace=True)

def encode(df: pd.DataFrame):
    df.loc[df["Notes"] == "EC Champions","Notes"] = 2
    df.loc[df["Notes"] == "WC Champions", "Notes"] = 2
    df.loc[df["Notes"] == "NBA Champions", "Notes"] = 1
    df["Notes"] = df["Notes"].fillna(0)

encode(df_coaches)

print(df_coaches["Notes"].unique())
print(df_coaches.head())
