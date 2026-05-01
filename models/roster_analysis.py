import numpy as np, pandas as pd, string

import matplotlib.pyplot as plt
import os
from functools import reduce

def get_roster():
    CHAMPIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "champions_since_2000")
    SAC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "SAC_since_2000")

    def load_dir(directory, is_sac=False):
        log_frames = []
        for entry in os.scandir(directory):
            if not entry.is_dir():
                continue
            roster_path = os.path.join(entry.path, "roster.csv")
            if not os.path.exists(roster_path):
                continue
            df = pd.read_csv(roster_path)
            if is_sac:
                df["team"] = f"SAC_{entry.name}"
            else:
                year, team = entry.name.split("_")
                df["team"] = f"{team}_{year}"
            log_frames.append(df)
        return pd.concat(log_frames, ignore_index=True)

    return load_dir(CHAMPIONS_DIR), load_dir(SAC_DIR, is_sac=True)

def get_players_stats():
    CHAMPIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "champions_since_2000")
    SAC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "SAC_since_2000")

    def load_dir(directory, is_sac=False):
        log_frames = []
        for entry in os.scandir(directory):
            if not entry.is_dir():
                continue
            adv_path = os.path.join(entry.path, "advanced_stats.csv")
            if not os.path.exists(adv_path):
                continue
            df = pd.read_csv(adv_path)
            if is_sac:
                df["team"] = f"SAC_{entry.name}"
            else:
                year, team = entry.name.split("_")
                df["team"] = f"{team}_{year}"
            log_frames.append(df)
        return pd.concat(log_frames, ignore_index=True)

    return load_dir(CHAMPIONS_DIR), load_dir(SAC_DIR, is_sac=True)

df_advanced_stats, df_sac_advanced_stats = get_players_stats()

df_advanced_stats.drop(columns=["comp_name_abbr", "team_name_abbr"], inplace=True)
df_sac_advanced_stats.drop(columns=["comp_name_abbr", "team_name_abbr"], inplace=True)

df_roster, df_roster_sac = get_roster()

df_roster.loc[df_roster["Exp"] == "R", "Exp"] = 0
df_roster_sac.loc[df_roster_sac["Exp"] == "R", "Exp"] = 0

df_roster_stats = pd.merge(df_advanced_stats, df_roster, on=["Player", "team"])
df_roster_stats_sac = pd.merge(df_sac_advanced_stats, df_roster_sac, on=["Player", "team"])

df_roster_stats.drop(columns=["College"], inplace=True)
df_roster_stats_sac.drop(columns=["College"], inplace=True)
print(df_sac_advanced_stats.head())

# create roster depth measurement
def calculate_bench_contributions(df: pd.DataFrame):
    teams = df.groupby("team")
    starters = df[(df["games_started"] >= 60) | (df["games_started"]/df["games"] > 0.85) | (df["mp"]/df["games"] >= 30)]["Player"].to_list()
    depth_scores = []
    for team in teams:
        depth_score = 0
        for player in team[1]["Player"]:
            if player in starters:
                continue
            else:
                depth_score += float(team[1][team[1]["Player"] == player]["vorp"].iloc[0]) # sum the overall contrubutions of the bench players to determine bench contributions
        depth_scores.append(depth_score)
    depth_scores_dict = dict(zip(df["team"].unique(), depth_scores))
    return depth_scores_dict

def calculate_depth(df: pd.DataFrame):
    teams = df.groupby("team")
    scores = {}
    for team, g in teams:
        non_star = g.sort_values("vorp", ascending=False)["vorp"].iloc[2:].mean() # use mean to fit scores into the vorp scale as it shows the average vorp of non-stars
        weakest_pos = g.groupby("pos")["vorp"].max().min()
        scores[team] = float(non_star + weakest_pos)
    return scores

TEAM_COLORS = {
    "SAC": "#5A2D81",
    "LAL": "#FDB927",
    "SAS": "#C4CED4",
    "MIA": "#98002E",
    "DET": "#C8102E",
    "BOS": "#007A33",
    "DAL": "#00538C",
    "MIL": "#00471B",
    "CLE": "#860038",
    "GSW": "#1D428A",
    "TOR": "#CE1141",
    "DEN": "#FEC524",
    "OKC": "#EF3B24",
}

SAC_PLAYOFF_RESULTS = {
    2000: 0,   # lost first round
    2001: 1,   # conference semis
    2002: 2,   # conference finals
    2003: 1,   # conference semis
    2004: 1,   # conference semis
    2005: 0,   # lost first round
    2006: 0,   # lost first round
    2023: 0,   # lost first round
}

PLAYOFF_LABELS = {
    -1: "DNQ",
    0: "1st Round",
    1: "Conf Semis",
    2: "Conf Finals",
    3: "NBA Finals",
}

def plot_depth_scores(depth_scores, playoff_results=None):
    items = sorted(depth_scores.items(), key=lambda x: abs(x[1]), reverse=True)
    _, ax = plt.subplots(figsize=(14, 6))
    seen_teams = set()
    for key, val in items:
        team = key.split("_")[0]
        year = int(key.split("_")[1])
        color = TEAM_COLORS.get(team, "black")
        label = team if team not in seen_teams else None
        seen_teams.add(team)
        ax.bar(year, val, color=color, label=label, width=0.8)
    ax.set_xticks(range(2000, 2027))
    ax.set_xticklabels(range(2000, 2027), rotation=45, ha="right", fontsize=7)
    ax.set_title("SAC vs Championship teams Bench Depth Rating")
    ax.set_xlabel("Year")
    ax.set_ylabel("Bench Depth (VORP)")

    if playoff_results is not None:
        ax2 = ax.twinx()
        years = list(range(2000, 2027))
        results = [playoff_results.get(y, -1) for y in years]
        ax2.plot(years, results, color="black", marker="o", linewidth=1.5, label="SAC Playoff Run")
        ax2.set_yticks(list(PLAYOFF_LABELS.keys()))
        ax2.set_yticklabels(list(PLAYOFF_LABELS.values()))
        ax2.set_ylabel("SAC Playoff Run")
        ax2.set_ylim(-1.5, 3.5)

        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
    else:
        ax.legend(title="Team")

    plt.tight_layout()
    plt.show()

champs_bench_contributions = calculate_bench_contributions(df_roster_stats)
sac_bench_contributions = calculate_bench_contributions(df_roster_stats_sac)
data = champs_bench_contributions | sac_bench_contributions

champs_depth = calculate_depth(df_roster_stats)
sac_depth = calculate_depth(df_roster_stats_sac)
depth_data = champs_depth | sac_depth
print(champs_depth)
print(sac_depth)
plot_depth_scores(depth_data, SAC_PLAYOFF_RESULTS)