import numpy as np, pandas as pd, string
from string import digits

import tensorflow as tf
from keras.models import Model
from keras.layers import Input, LSTM, Embedding, Dense, RepeatVector
from keras.preprocessing.sequence import pad_sequences

from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

import matplotlib.pyplot as plt
import os
from functools import reduce

os.environ["TF_ENABLE_ONEDNN_OPTS"] = '0'

def get_gamelogs():
    CHAMPIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "champions_since_2000")
    log_frames = []
    for entry in os.scandir(CHAMPIONS_DIR):
        if not entry.is_dir():
            continue
        gamelog_path = os.path.join(entry.path, "gamelog.csv")
        if not os.path.exists(gamelog_path):
            continue
        year, team = entry.name.split("_")
        df = pd.read_csv(gamelog_path)
        df["team"] = f"{team}_{year}"
        log_frames.append(df)
    # shapes = [x.shape for x in log_frames]
    # print(min(shapes))
    combined_df = pd.concat(log_frames, ignore_index=True)
    return combined_df

def get_sac_gamelogs():
    SAC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "SAC_since_2000")
    log_frames = []
    for entry in os.scandir(SAC_DIR):
        if not entry.is_dir():
            continue
        gamelog_path = os.path.join(entry.path, "gamelog.csv")
        if not os.path.exists(gamelog_path):
            continue
        year = entry.name
        df = pd.read_csv(gamelog_path)
        df["team"] = f"SAC_{year}"
        log_frames.append(df)
    # shapes = [x.shape for x in log_frames]
    # print(min(shapes))
    combined_df = pd.concat(log_frames, ignore_index=True)
    return combined_df

df_advanced_stats = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "champions_advanced_stats.csv"))
df_advanced_stats["team"] = df_advanced_stats["team"] + "_" + df_advanced_stats["year"].astype(str)
df_advanced_stats.drop(columns=["year"], inplace=True)
print(df_advanced_stats.columns)
df_advanced_stats_sac = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "SAC_since_2000", "SAC_advanced_stats.csv"))
df_advanced_stats_sac["team"] = df_advanced_stats_sac["team"] + "_" + df_advanced_stats_sac["year"].astype(str)
df_advanced_stats_sac.drop(columns=["year"], inplace=True)

df_sac = get_sac_gamelogs()
df_sac.rename(columns={"Unnamed: 3" : "h/a"}, inplace=True)
df_sac["h/a"] = (df_sac["h/a"] == "@").astype(int) # home is 0, away is 1
df_sac["Rslt"] = (df_sac["Rslt"] == "W").astype(int) # W is 1, L is 0
df_sac["OT"] = df_sac['OT'].astype('category').cat.codes
df_sac.dropna(subset=["Date"], inplace=True)
df_sac.fillna(0, inplace=True)
print(df_sac.columns)

df = get_gamelogs()    
df.rename(columns={"Unnamed: 3" : "h/a"}, inplace=True)
df["h/a"] = (df["h/a"] == "@").astype(int) # home is 0, away is 1
df["Rslt"] = (df["Rslt"] == "W").astype(int) # W is 1, L is 0
df["OT"] = df['OT'].astype('category').cat.codes
df.dropna(subset=["Date"], inplace=True)
df.fillna(0, inplace=True)
print(df.columns)

string_cols = df.select_dtypes(include=['object', 'string']).columns

# Encoder
timesteps = 66
features = 49
latent_dim = 16

inputs = Input(shape=(timesteps, features))
encoded = LSTM(64)(inputs)

embeddings = Dense(latent_dim, activation='relu')(encoded)

# Decoder
decoded = RepeatVector(timesteps)(embeddings)

decoded = LSTM(64, return_sequences=True)(decoded)

outputs = Dense(features)(decoded)

# Autoencoder Model
autoencoder = Model(inputs, outputs)
autoencoder.compile(optimizer='adam', loss='mse')

autoencoder.summary()

encoder_model = Model(inputs, embeddings)

df = df.sort_values(['team', 'Date'])
chip_teams = df['team'].unique()
sac_teams = df_sac["team"].unique()
feature_cols = [col for col in df.columns if col not in ["team", "Date", "Opp"]]

sequences = []
teams = [sac_teams, chip_teams]
for team_group in teams:
    for team in team_group:
        team_df = df[df['team'] == team].sort_values("Date")

        data = team_df[feature_cols].values

        # truncate or pad
        if len(data) >= timesteps:
            seq = data[-timesteps:]
        else:
            pad = np.zeros((timesteps - len(data), len(feature_cols)))
            seq = np.vstack([pad, data])

        sequences.append(seq)

X = np.array(sequences)
X_2d = X.reshape(-1, X.shape[-1])  # flatten time dimension

scaler = StandardScaler() # normalize values
X_2d = scaler.fit_transform(X_2d)

X = X_2d.reshape(X.shape)

autoencoder.fit(
    X, X,
    epochs=50,
    batch_size=16,
    validation_split=0.1
)

embeddings = encoder_model.predict(X)
#  print(embeddings.shape)

kmeans = KMeans(n_clusters=3)
labels = kmeans.fit_predict(embeddings)
# print(labels)

pca = PCA(n_components=2) # compresses the vector's dimensions to 2, while preserving as much structure as possible
reduced = pca.fit_transform(embeddings)

plt.scatter(reduced[:,0], reduced[:,1], c=labels)
# plt.show()

all_teams = np.concatenate([sac_teams, chip_teams])
results = pd.DataFrame({"team": all_teams, "cluster": labels})
grouped = results.groupby("cluster")
clusters = grouped["team"].apply(list)
df_advanced_stats = pd.read_csv("data/champions_advanced_stats.csv")
df_advanced_stats["team"] = df_advanced_stats["team"] + "_" + df_advanced_stats["year"].astype("Int64").astype(str)
df_advanced_stats.drop(columns=["year"], inplace=True)

cluster1 = clusters[1]
cluster2 = clusters[2]
advanced_stats_in_c1 = df_advanced_stats[df_advanced_stats["team"].isin(cluster1)]
advanced_stats_in_c2 = df_advanced_stats[df_advanced_stats["team"].isin(cluster2)]

print(advanced_stats_in_c1)
print(advanced_stats_in_c2)
print(advanced_stats_in_c2.shape)
print(advanced_stats_in_c1.shape)

df_all = pd.concat([df, df_sac], ignore_index=True)
df_all_advanced_stats = pd.concat([df_advanced_stats, df_advanced_stats_sac], ignore_index=True)
dfs = [df_all_advanced_stats, df_all, results]
df_clustered = reduce(lambda left, right: pd.merge(left, right, on='team'), dfs)
summary = df_clustered.groupby("cluster").mean(numeric_only=True)
# print(summary)

# summary.to_csv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "Champions_since_2000_summarized.csv"))

# decision tree to surface human-readable cluster rules (cluster 0 excluded)
df_filtered = df_clustered[df_clustered["cluster"] != 0]
features_df = df_filtered.select_dtypes(include="number").drop(columns=["cluster"])
labels_series = df_filtered["cluster"]

tree = DecisionTreeClassifier(max_depth=3, random_state=0).fit(features_df, labels_series)
print("\n--- cluster decision rules ---")
print(export_text(tree, feature_names=list(features_df.columns)))

importances = pd.Series(tree.feature_importances_, index=features_df.columns).sort_values(ascending=False)
print("\n--- top splitting features ---")
print(importances.head(10))

plt.figure(figsize=(20, 10))
plot_tree(
    tree,
    feature_names=list(features_df.columns),
    class_names=[f"cluster {c}" for c in sorted(labels_series.unique())],
    filled=True,
    rounded=True,
    fontsize=9,
)
plt.tight_layout()
plt.show()