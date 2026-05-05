import json
import os
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

# Analyze choices and impact made by management
def load_transactions(start_year: int = 2000, end_year: int = 2026) -> pd.DataFrame:
    transactions_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "player_transaction_history"
    )
    rows = []
    for year in range(start_year, end_year + 1):
        path = os.path.join(transactions_dir, f"{year}_transactions.json")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        for record in records:
            rows.append({
                "year": year,
                "date": record["date"],
                "transactions": record["transactions"],
            })
    df = pd.DataFrame(rows).explode("transactions").reset_index(drop=True)
    df.rename(columns={"transactions": "transaction"}, inplace=True)
    df = df[df["transaction"].str.contains("Sacramento Kings", case=False, na=False)].reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df

df_gms = pd.read_csv("data/SAC_GMs.csv")
df_gms["End"] = df_gms["End"].replace("present", pd.Timestamp.now().strftime("%Y-%m-%d"))
df_gms["Start"] = pd.to_datetime(df_gms["Start"], errors="coerce", format="mixed")
df_gms["End"] = pd.to_datetime(df_gms["End"], errors="coerce", format="mixed")
print(df_gms[df_gms["End"] >= "2000-01-01"])
df_draft_hist = pd.read_csv("data/SAC_draft_history.csv")
print(df_draft_hist.head())

df_coaches = pd.read_csv("data/SAC_coaches.csv")
df_transactions = load_transactions()
print(df_transactions)

def gm_at(date):
    date = pd.to_datetime(date, errors="coerce")
    if pd.isna(date):
        return None
    match = df_gms[(df_gms["Start"] <= date) & (df_gms["End"] >= date)]
    return match["Executive"].iloc[0] if len(match) else None

df_transactions["gm"] = df_transactions["date"].apply(gm_at)
df_draft_hist["gm"] = df_draft_hist["Year"].astype(str).apply(lambda y: gm_at(f"{y}-06-25"))

# === DRAFT SCORING ===
# value-add per pick = career VORP - median VORP at that pick slot
df_draft_hist["VORP"] = pd.to_numeric(df_draft_hist["VORP"], errors="coerce")
df_draft_hist["Pk"] = pd.to_numeric(df_draft_hist["Pk"], errors="coerce")

slot_baseline = df_draft_hist.groupby("Pk")["VORP"].median()
df_draft_hist["draft_value_add"] = df_draft_hist["VORP"] - df_draft_hist["Pk"].map(slot_baseline)

draft_score_per_gm = df_draft_hist.dropna(subset=["draft_value_add"]).groupby("gm")["draft_value_add"].sum()
print("\n--- Draft value-add per GM ---")
print(draft_score_per_gm.sort_values(ascending=False))

# === TRANSACTION SCORING ===
# Build player → SAC-tenure career VORP lookup from per-season advanced stats
import re
import unicodedata

def normalize(name: str) -> str:
    if not isinstance(name, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return stripped.lower().strip()

sac_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "SAC_since_2000")
adv_frames = []
for entry in os.scandir(sac_dir):
    if entry.is_dir():
        adv_path = os.path.join(entry.path, "advanced_stats.csv")
        if os.path.exists(adv_path):
            adv_frames.append(pd.read_csv(adv_path))
df_adv = pd.concat(adv_frames, ignore_index=True)
df_adv["vorp"] = pd.to_numeric(df_adv["vorp"], errors="coerce")
df_adv["player_norm"] = df_adv["Player"].apply(normalize)
career_vorp = df_adv.groupby("player_norm")["vorp"].sum()

PICK_PATTERN = re.compile(r"\(R\d+\s*P\d+\)", re.IGNORECASE)

def asset_value(asset_str) -> float:
    cleaned = PICK_PATTERN.sub("", str(asset_str)).strip()
    return float(career_vorp.get(normalize(cleaned), 0.0))

# Load major transactions from the agent's structured output (CSV has the full mix incl. trades)
import ast

majors_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SAC_major_transacts.csv")
if os.path.exists(majors_path):
    df_majors = pd.read_csv(majors_path)

    def parse_list(cell):
        if pd.isna(cell) or cell in ("None", "N/A", ""):
            return []
        try:
            val = ast.literal_eval(cell)
            return val if isinstance(val, list) else []
        except (ValueError, SyntaxError):
            return []

    df_majors["assets_gained"] = df_majors["assets_gained"].apply(parse_list)
    df_majors["assets_lost"] = df_majors["assets_lost"].apply(parse_list)
    df_majors = df_majors[df_majors["transaction_type"] != "draft"].copy()

    df_majors["gained_value"] = df_majors["assets_gained"].apply(lambda lst: sum(asset_value(a) for a in lst))
    df_majors["lost_value"] = df_majors["assets_lost"].apply(lambda lst: sum(asset_value(a) for a in lst))
    df_majors["net_value"] = df_majors["gained_value"] - df_majors["lost_value"]
    df_majors["gm"] = df_majors["transaction_date"].apply(gm_at)

    txn_score_per_gm = df_majors.groupby("gm")["net_value"].sum()
    print("\n--- Transaction value-add per GM ---")
    print(txn_score_per_gm.sort_values(ascending=False))
else:
    txn_score_per_gm = pd.Series(dtype=float)
    print(f"\nNo major transactions file found at {majors_path}")

# === FINAL SCORECARD ===
scorecard = pd.DataFrame({
    "draft_value_add": draft_score_per_gm,
    "txn_value_add": txn_score_per_gm,
}).fillna(0)
scorecard["total"] = scorecard["draft_value_add"] + scorecard["txn_value_add"]

# Normalize by tenure length — sum across multi-stint executives (e.g., Joe Axelson)
df_gms["tenure_days"] = (df_gms["End"] - df_gms["Start"]).dt.days
gm_dates = df_gms.groupby("Executive").agg(
    tenure_start=("Start", "min"),
    tenure_end=("End", "max"),
    tenure_days=("tenure_days", "sum"),
)
gm_dates["tenure_years"] = gm_dates["tenure_days"] / 365.25
scorecard["tenure_start"] = gm_dates["tenure_start"].dt.strftime("%Y-%m-%d")
scorecard["tenure_end"] = gm_dates["tenure_end"].dt.strftime("%Y-%m-%d")
scorecard["tenure_years"] = gm_dates["tenure_years"]
scorecard["per_year"] = scorecard["total"] / scorecard["tenure_years"]

print("\n--- GM scorecard ---")
print(scorecard.sort_values("total", ascending=False).round(2))