import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
MGMT_DIR = os.path.join(ROOT, "data", "mgmt_history")
PLAYOFFS_DIR = os.path.join(ROOT, "data", "champions_playoff_appearances")
CHAMPS_DIR = os.path.join(ROOT, "data", "champions_since_2000")
SAC_DIR = os.path.join(ROOT, "data", "SAC_since_2000")

PLAYOFFS_DEPTH_DIR = os.path.join(ROOT, "data", "Champions_playoffs_depth")


def _load_team_advanced(team: str, year) -> pd.DataFrame | None:
    """Return per-player advanced stats for a (team, year) if available, else None.

    Checks (in order): SAC_since_2000, Champions_playoffs_depth (newly scraped
    playoff-season data), then champions_since_2000 (title seasons).
    """
    if pd.isna(year):
        return None
    year = int(year)

    if team == "SAC":
        path = os.path.join(SAC_DIR, str(year), "advanced_stats.csv")
        return pd.read_csv(path) if os.path.exists(path) else None

    # Try the new Champions_playoffs_depth folder first (covers all post-2000 playoff seasons)
    p = os.path.join(PLAYOFFS_DEPTH_DIR, f"{team}_{year}.csv")
    if os.path.exists(p):
        return pd.read_csv(p)

    # Fallback to the original title-season folder
    p = os.path.join(CHAMPS_DIR, f"{year}_{team}", "advanced_stats.csv")
    if os.path.exists(p):
        return pd.read_csv(p)
    return None


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

# Coaches by post-2000 playoff appearances — one appearance = one season with playoff games
df_coaches["G_playoff"] = pd.to_numeric(df_coaches["G.1"], errors="coerce").fillna(0)
playoff_seasons = df_coaches[df_coaches["G_playoff"] > 0]
playoff_appearances = (
    playoff_seasons.groupby("Coach").size().rename("playoffs")
)

# One-row-per-coach summary card: same data as df_coaches with Season dropped, plus a "playoffs" column
numeric_sum_cols = ["G", "W", "L", "G.1", "W.1", "L.1", "W > .500"]
for c in numeric_sum_cols:
    df_coaches[c] = pd.to_numeric(df_coaches[c], errors="coerce")
df_coaches["Notes"] = pd.to_numeric(df_coaches["Notes"], errors="coerce").fillna(0)

agg_spec = {
    "team": lambda s: ", ".join(sorted(set(s.dropna().astype(str)))),
    "Tm": lambda s: ", ".join(sorted(set(s.dropna().astype(str)))),
    "Lg": lambda s: ", ".join(sorted(set(s.dropna().astype(str)))),
    "G": "sum", "W": "sum", "L": "sum",
    "G.1": "sum", "W.1": "sum", "L.1": "sum",
    "W > .500": "sum",
    "Notes": "max",  # 1=NBA chip, 2=conference title — keep best
}
coaches_card = df_coaches.groupby("Coach").agg(agg_spec)
coaches_card["W/L%"] = (coaches_card["W"] / (coaches_card["W"] + coaches_card["L"])).round(3)
coaches_card["W/L%.1"] = (coaches_card["W.1"] / (coaches_card["W.1"] + coaches_card["L.1"])).round(3)
coaches_card = coaches_card.join(playoff_appearances).fillna({"playoffs": 0})
coaches_card["playoffs"] = coaches_card["playoffs"].astype(int)

def _season_end(s):
    if not isinstance(s, str) or "-" not in s:
        return None
    try:
        return int(s.split("-")[0]) + 1
    except ValueError:
        return None

df_coaches["season_end_year"] = df_coaches["Season"].apply(_season_end)

# Build depth lookup by computing from ALL available sources (SAC + titles + new playoff-depth folder)
unique_pairs = df_coaches[["team", "season_end_year"]].drop_duplicates()
depth_map: dict[tuple, float | None] = {}
for _, r in unique_pairs.iterrows():
    if pd.isna(r["season_end_year"]):
        continue
    key = (r["team"], int(r["season_end_year"]))
    depth_map[key] = _compute_depth_score(_load_team_advanced(r["team"], int(r["season_end_year"])))

df_coaches["depth_score"] = df_coaches.apply(
    lambda r: depth_map.get((r["team"], r["season_end_year"])) if pd.notna(r["season_end_year"]) else None,
    axis=1,
)

# Encode playoff distance from the Playoffs result text
def encode_distance(text):
    if pd.isna(text) or not str(text).strip():
        return 0
    t = str(text).strip()
    if "Won Finals" in t:
        return 5
    if "Lost Finals" in t and "Conf" not in t:
        return 4
    if "Conf" in t and "Finals" in t:
        return 3
    if "Semis" in t:
        return 2
    if "1st Rnd" in t or "First Round" in t:
        return 1
    return 0

playoff_hist = load_playoff_history(include_depth=False)
playoff_hist["distance"] = playoff_hist["Playoffs"].apply(encode_distance)
df_coaches = df_coaches.merge(
    playoff_hist[["team", "Season", "distance"]], on=["team", "Season"], how="left"
)
df_coaches["distance"] = df_coaches["distance"].fillna(0).astype(int)

# Per-season impact = playoff_distance / (depth_score + 1)
# +1 offset keeps the denominator positive even for SAC seasons with negative raw depth
mask = df_coaches["depth_score"].notna() & (df_coaches["distance"] > 0)
df_coaches["impact_score"] = pd.NA
df_coaches.loc[mask, "impact_score"] = (
    df_coaches.loc[mask, "distance"] / (df_coaches.loc[mask, "depth_score"] + 1)
)
df_coaches["impact_score"] = pd.to_numeric(df_coaches["impact_score"], errors="coerce")

# Aggregate per coach: sum + scoring season count
total_impact = df_coaches.groupby("Coach")["impact_score"].sum().rename("total_impact").round(3)
impact_seasons = (
    df_coaches[df_coaches["impact_score"].notna()].groupby("Coach").size().rename("impact_seasons")
)

playoff_only = df_coaches[df_coaches["G_playoff"] > 0]
avg_playoff_depth = (
    playoff_only.groupby("Coach")["depth_score"].mean().rename("avg_playoff_depth").round(3)
)

coaches_card = coaches_card.join(avg_playoff_depth)
coaches_card = coaches_card.join(total_impact).join(impact_seasons)
coaches_card["impact_seasons"] = coaches_card["impact_seasons"].fillna(0).astype(int)

# Most impactful single season per coach
impact_rows = df_coaches.dropna(subset=["impact_score"]).copy()
best_idx = impact_rows.groupby("Coach")["impact_score"].idxmax()
best_seasons = impact_rows.loc[best_idx, ["Coach", "Season", "team", "season_end_year", "impact_score", "depth_score"]]
best_seasons["best_season"] = best_seasons.apply(
    lambda r: f"{r['Season']} {r['team']} ({round(r['impact_score'], 2)})",
    axis=1,
)

# Star power = sum of VORP for all players on that roster with vorp >= 2.0 (All-Star caliber)
STAR_VORP_THRESHOLD = 1.0
def _star_power(team, year):
    df = _load_team_advanced(team, year)
    if df is None or "vorp" not in df.columns:
        return None
    vorp = pd.to_numeric(df["vorp"], errors="coerce")
    stars = vorp[vorp >= STAR_VORP_THRESHOLD]
    if stars.empty:
        return 0.0
    return float(stars.sum())

best_seasons["star_power"] = best_seasons.apply(
    lambda r: _star_power(r["team"], r["season_end_year"]),
    axis=1,
)

best_seasons = best_seasons.set_index("Coach")
coaches_card = coaches_card.join(best_seasons[["best_season", "impact_score", "star_power", "depth_score"]])
coaches_card = coaches_card.rename(columns={"impact_score": "best_impact", "depth_score": "best_season_depth"})
coaches_card["best_season_depth"] = coaches_card["best_season_depth"].round(3)
coaches_card["star_power"] = coaches_card["star_power"].round(2)

coaches_card = coaches_card.sort_values("best_impact", ascending=False)
coaches_card.drop(columns=["Tm", "Lg", "team", "G", "G.1", "W.1", "L.1"], inplace=True)
only_champions = coaches_card[coaches_card["Notes"] == 2]
# print(only_champions)

print("\n--- Coach summary card (post-2000) ---")
notna = coaches_card[(coaches_card["best_season_depth"].notna())].sort_values("star_power", ascending=True)["star_power"]

# plt.hist(notna, bins=14, density=True)

# mu = np.mean(notna)
# sigma = np.std(notna)

# x = np.linspace(min(notna), max(notna), 200)
# y = (1 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mu) / sigma) ** 2)
# q1, q2, q3 = np.percentile(notna, [25, 50, 75])

# plt.plot(x,y)
# plt.axvline(mu, linestyle='--', color="red")
# plt.axvline(q1, linestyle=':', color='green')
# plt.axvline(q2, linestyle=':', color='green')
# plt.axvline(q3, linestyle=':', color='green')

# plt.text(mu, max(y) * 0.9, f'μ = {mu:.2f}')
# plt.text(q1, max(y) * 0.8, f'Q1 = {q1:.2f}')
# plt.text(q2, max(y) * 0.7, f'Q2 = {q2:.2f}')
# plt.text(q3, max(y) * 0.6, f'Q3 = {q3:.2f}')

# plt.xlabel("values")
# plt.ylabel("density")
# plt.show()

print(notna.to_string())
notna = coaches_card[(coaches_card["best_season_depth"].notna()) & (coaches_card["Notes"] == 2)]
print(notna.to_string())