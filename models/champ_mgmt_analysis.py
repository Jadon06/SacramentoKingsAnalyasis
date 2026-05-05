import os
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, "data")
MGMT_DIR = os.path.join(DATA_DIR, "mgmt_history")
START_2000 = pd.Timestamp("2000-01-01")

CHAMP_TEAMS = sorted(e.name for e in os.scandir(MGMT_DIR) if e.is_dir())

# === Load all draft histories into one combined frame ===
all_drafts = []
for team in CHAMP_TEAMS:
    path = os.path.join(MGMT_DIR, team, "draft_history.csv")
    if not os.path.exists(path):
        continue
    df = pd.read_csv(path)
    df = df[df["Year"] != "Year"].reset_index(drop=True)
    df["team"] = team
    all_drafts.append(df)

combined = pd.concat(all_drafts, ignore_index=True)
combined["Year"] = pd.to_numeric(combined["Year"], errors="coerce")
combined["Pk"] = pd.to_numeric(combined["Pk"], errors="coerce")
combined["VORP"] = pd.to_numeric(combined["VORP"], errors="coerce")

# Apples-to-apples: only post-2000 drafts
combined = combined[combined["Year"] >= 2000].copy()

# Global slot baseline pooled across all 12 teams
global_baseline = combined.groupby("Pk")["VORP"].median()
combined["draft_value_add"] = combined["VORP"] - combined["Pk"].map(global_baseline)

# === Per-team executive tagging ===
def load_execs(team: str) -> pd.DataFrame:
    path = os.path.join(MGMT_DIR, team, "executives.csv")
    df = pd.read_csv(path)
    df["End"] = df["End"].replace("present", pd.Timestamp.now().strftime("%Y-%m-%d"))
    df["Start"] = pd.to_datetime(df["Start"], errors="coerce", format="mixed")
    df["End"] = pd.to_datetime(df["End"], errors="coerce", format="mixed")
    return df

def exec_at(execs: pd.DataFrame, year: int) -> str | None:
    if pd.isna(year):
        return None
    date = pd.Timestamp(f"{int(year)}-06-25")  # NBA draft is late June
    match = execs[(execs["Start"] <= date) & (execs["End"] >= date)]
    return match["Executive"].iloc[0] if len(match) else None

execs_by_team = {team: load_execs(team) for team in CHAMP_TEAMS
                 if os.path.exists(os.path.join(MGMT_DIR, team, "executives.csv"))}

combined["executive"] = combined.apply(
    lambda r: exec_at(execs_by_team[r["team"]], r["Year"]) if r["team"] in execs_by_team else None,
    axis=1,
)

# === Per-team scorecards ===
def build_team_scorecard(team: str) -> pd.DataFrame:
    team_drafts = combined[combined["team"] == team]
    score = team_drafts.dropna(subset=["draft_value_add"]).groupby("executive")["draft_value_add"].sum()
    if team not in execs_by_team:
        return pd.DataFrame()
    execs = execs_by_team[team].copy()
    # Clip tenure window to [2000, present] for fair per-year comparison
    execs["start_clipped"] = execs["Start"].apply(lambda d: max(d, START_2000) if pd.notna(d) else d)
    execs["tenure_days"] = (execs["End"] - execs["start_clipped"]).dt.days.clip(lower=0)
    gm_dates = execs.groupby("Executive").agg(
        tenure_start=("start_clipped", "min"),
        tenure_end=("End", "max"),
        tenure_days=("tenure_days", "sum"),
    )
    gm_dates["tenure_years"] = gm_dates["tenure_days"] / 365.25

    sc = pd.DataFrame({"draft_value_add": score})
    sc["tenure_start"] = gm_dates["tenure_start"].dt.strftime("%Y-%m-%d")
    sc["tenure_end"] = gm_dates["tenure_end"].dt.strftime("%Y-%m-%d")
    sc["tenure_years"] = gm_dates["tenure_years"].round(2)
    sc["per_year"] = (sc["draft_value_add"] / sc["tenure_years"]).round(2)
    sc["draft_value_add"] = sc["draft_value_add"].round(2)
    sc = sc.fillna(0).sort_values("draft_value_add", ascending=False)
    return sc

print("=" * 60)
print("PER-TEAM DRAFT VALUE-ADD SCORECARDS (post-2000)")
print("=" * 60)
for team in CHAMP_TEAMS:
    sc = build_team_scorecard(team)
    if sc.empty:
        continue
    out_path = os.path.join(MGMT_DIR, team, "scorecard.csv")
    sc.to_csv(out_path)
    print(f"\n--- {team} ---")
    print(sc)
# === Playoff / Finals / Championship counts per executive ===
PLAYOFFS_DIR = os.path.join(DATA_DIR, "champions_playoff_appearances")

def parse_playoff_result(text):
    if pd.isna(text):
        return False, False, False
    text = str(text).strip()
    if not text:
        return False, False, False
    # "Lost W. Conf. Finals" / "Lost E. Conf. Finals" are conference finals, NOT NBA Finals
    is_conf = "Conf" in text
    has_finals = "Finals" in text
    made_finals = has_finals and not is_conf
    won_chip = made_finals and "Won" in text
    return True, made_finals, won_chip

def season_to_year(season_str):
    if not isinstance(season_str, str) or "-" not in season_str:
        return None
    try:
        start = int(season_str.split("-")[0])
    except ValueError:
        return None
    return start + 1

def exec_at_season(execs, year):
    if pd.isna(year):
        return None
    date = pd.Timestamp(f"{int(year)}-04-15")  # mid-playoffs date
    match = execs[(execs["Start"] <= date) & (execs["End"] >= date)]
    return match["Executive"].iloc[0] if len(match) else None

playoff_frames = []
for team in CHAMP_TEAMS:
    path = os.path.join(PLAYOFFS_DIR, f"{team}.csv")
    if not os.path.exists(path) or team not in execs_by_team:
        continue
    df_p = pd.read_csv(path)
    df_p["year"] = df_p["Season"].apply(season_to_year)
    df_p = df_p[df_p["year"] >= 2000].copy()
    parsed = df_p["Playoffs"].apply(lambda x: pd.Series(parse_playoff_result(x),
                                                          index=["made_playoffs", "made_finals", "won_championship"]))
    df_p = pd.concat([df_p, parsed], axis=1)
    df_p["executive"] = df_p["year"].apply(lambda y: exec_at_season(execs_by_team[team], y))
    df_p["team"] = team
    playoff_frames.append(df_p[["team", "year", "executive", "made_playoffs", "made_finals", "won_championship"]])

playoff_combined = pd.concat(playoff_frames, ignore_index=True)
playoff_summary = (
    playoff_combined.dropna(subset=["executive"])
    .groupby(["team", "executive"])
    .agg(
        playoff_appearances=("made_playoffs", "sum"),
        finals_appearances=("made_finals", "sum"),
        championships=("won_championship", "sum"),
    )
    .reset_index()
)

# === Tenure dates per (team, executive), clipped to post-2000 ===
tenure_rows = []
for team, execs in execs_by_team.items():
    df = execs.copy()
    df["start_clipped"] = df["Start"].apply(lambda d: max(d, START_2000) if pd.notna(d) else d)
    grouped = df.groupby("Executive").agg(
        tenure_start=("start_clipped", "min"),
        tenure_end=("End", "max"),
    ).reset_index().rename(columns={"Executive": "executive"})
    grouped["team"] = team
    tenure_rows.append(grouped)
tenure_dates = pd.concat(tenure_rows, ignore_index=True)
tenure_dates["tenure_start"] = tenure_dates["tenure_start"].dt.strftime("%Y-%m-%d")
tenure_dates["tenure_end"] = tenure_dates["tenure_end"].dt.strftime("%Y-%m-%d")

# === Master scorecard across all teams ===
master = (
    combined.dropna(subset=["draft_value_add", "executive"])
    .groupby(["team", "executive"])["draft_value_add"]
    .agg(["sum", "count"])
    .reset_index()
    .rename(columns={"sum": "draft_value_add", "count": "picks"})
)
master["draft_value_add"] = master["draft_value_add"].round(2)
master = master.merge(playoff_summary, on=["team", "executive"], how="left").fillna(0)
master[["playoff_appearances", "finals_appearances", "championships"]] = (
    master[["playoff_appearances", "finals_appearances", "championships"]].astype(int)
)
master = master.merge(tenure_dates, on=["team", "executive"], how="left")
master = master.sort_values("draft_value_add", ascending=False)
master_path = os.path.join(MGMT_DIR, "master_scorecard.csv")
master.to_csv(master_path, index=False)

print("\n" + "=" * 60)
print("MASTER SCORECARD (top 20 GMs across all 12 champion teams)")
print("=" * 60)
print(master.head(20).to_string(index=False))
print(f"\nSaved master to {master_path}")

avg_draft_va = master["draft_value_add"].mean()
median_draft_va = master["draft_value_add"].median()
print(f"\nAverage GM draft value-add across championship teams: {avg_draft_va:.2f} ({len(master)} GMs)")
print(f"Median GM draft value-add across championship teams: {median_draft_va:.2f}")

# === Bell-curve distribution: all GMs (champion teams + SAC) ===
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde

TEAM_COLORS = {
    "SAC": "#5A2D81", "LAL": "#FDB927", "SAS": "#C4CED4", "MIA": "#98002E",
    "DET": "#C8102E", "BOS": "#007A33", "DAL": "#00538C", "MIL": "#00471B",
    "CLE": "#860038", "GSW": "#1D428A", "TOR": "#CE1141", "DEN": "#FEC524",
    "OKC": "#EF3B24",
}

# Master scorecard already includes SAC (it's now in CHAMP_TEAMS via the folder scan)
all_gms = master[["team", "executive", "draft_value_add"]].dropna(subset=["draft_value_add"])
values = all_gms["draft_value_add"].values
kde = gaussian_kde(values)
x_range = np.linspace(values.min() - 30, values.max() + 30, 600)
y_curve = kde(x_range)

fig, ax = plt.subplots(figsize=(18, 9))
ax.plot(x_range, y_curve, color="black", linewidth=1.8)

# Shade quartile bands under the curve
q1, q2, q3 = np.quantile(values, [0.25, 0.50, 0.75])
band_colors = ["#fde0dc", "#dceefb", "#dcf3dc", "#fff5d6"]  # Q1, Q2, Q3, Q4 fills
band_edges = [x_range.min(), q1, q2, q3, x_range.max()]
band_labels = ["Q1", "Q2", "Q3", "Q4"]
for i in range(4):
    mask = (x_range >= band_edges[i]) & (x_range <= band_edges[i + 1])
    ax.fill_between(x_range[mask], y_curve[mask], alpha=0.6, color=band_colors[i])
    # Quartile labels along the bottom (axes coord y=0.02), so they don't block annotations
    mid_x = (band_edges[i] + band_edges[i + 1]) / 2
    ax.text(mid_x, 0.02, band_labels[i],
            ha="center", fontsize=11, fontweight="bold", color="dimgray",
            transform=ax.get_xaxis_transform())

# Vertical lines at quartile boundaries
for q_val, q_name in [(q1, "Q1"), (q2, "Q2 (median)"), (q3, "Q3")]:
    plt.axvline(q_val, color="gray", linestyle=":", linewidth=1)
    plt.text(q_val, y_curve.max() * 0.95, f"{q_name}={q_val:.1f}",
             rotation=90, va="top", ha="right", fontsize=8, color="gray")

mean_va = values.mean()
median_va = float(np.median(values))

for _, row in all_gms.iterrows():
    x = row["draft_value_add"]
    y_at_x = float(kde(x)[0])
    color = TEAM_COLORS.get(row["team"], "gray")
    plt.scatter(x, y_at_x, color=color, s=70, edgecolor="black", linewidth=0.5, zorder=5)
    if row["team"] == "SAC" and (x > mean_va or x > median_va):
        plt.annotate(
            row["executive"],
            (x, y_at_x),
            textcoords="offset points",
            xytext=(0, 12),
            ha="center",
            fontsize=8,
            fontweight="bold",
            color=TEAM_COLORS["SAC"],
        )

plt.axvline(values.mean(), color="red", linestyle="--", linewidth=1, label=f"Mean = {values.mean():.1f}")

# Build a clean team legend
team_handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=TEAM_COLORS[t], markersize=8, label=t)
                for t in sorted(all_gms["team"].unique()) if t in TEAM_COLORS]
mean_median_handles = [
    plt.Line2D([0], [0], color="red", linestyle="--", label=f"Mean = {values.mean():.1f}"),
]
plt.legend(handles=team_handles + mean_median_handles, loc="upper right", fontsize=8, ncol=2)

plt.xlabel("Draft value-add (career VORP minus slot baseline, summed per GM)")
plt.ylabel("Density")
plt.title("Distribution of GM draft value-add — Championship teams + SAC (post-2000)")
plt.tight_layout()
plt.show()

# === Q4 GMs (top quartile by draft_value_add) ===
q4_gms = master[master["draft_value_add"] >= q3].sort_values("draft_value_add", ascending=False).reset_index(drop=True)
print("\n" + "=" * 60)
print(f"Q4 GMs (draft_value_add >= {q3:.2f})")
print("=" * 60)
print(q4_gms.to_string(index=False))

# === Q4 scatter: playoff appearances vs draft_value_add ===
fig, ax = plt.subplots(figsize=(12, 7))
cmap = plt.get_cmap("tab20")
colors_per_gm = [cmap(i % 20) for i in range(len(q4_gms))]

for i, row in q4_gms.iterrows():
    ax.scatter(
        row["playoff_appearances"],
        row["draft_value_add"],
        color=colors_per_gm[i],
        s=140,
        edgecolor="black",
        linewidth=0.7,
        label=f"{row['executive']} ({row['team']})",
        zorder=5,
    )

ax.set_xlabel("Playoff appearances during tenure")
ax.set_ylabel("Draft value-add")
ax.set_title("Q4 GMs — Draft value-add vs. playoff appearances")
ax.grid(True, linestyle="--", alpha=0.4)
ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=9, frameon=True, title="GM (team)")
plt.tight_layout()
plt.show()
