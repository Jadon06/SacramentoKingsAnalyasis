import json
import os
import pandas as pd

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
print(df_gms.head())
df_draft_hist = pd.read_csv("data/SAC_draft_history.csv")
print(df_draft_hist.head())
df_coaches = pd.read_csv("data/SAC_coaches.csv")
df_transactions = load_transactions()
print(df_transactions.head())
