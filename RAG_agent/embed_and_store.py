import os
import sys
import json
import glob
from langchain_core.documents import Document
from langchain.chat_models import init_chat_model
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import LANGSMITH_API_KEY, ANTHROPIC_API_KEY

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
CHROMA_DIR = os.path.join(ROOT_DIR, "chroma_langchain_db")
TRANSACTIONS_DIR = os.path.join(ROOT_DIR, "player_transaction_history")

vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings,
    persist_directory=CHROMA_DIR,
)

def load_transaction_docs(directory: str) -> list[Document]:
    docs = []
    for path in glob.glob(os.path.join(directory, "*.json")):
        year = os.path.basename(path).replace("_transactions.json", "")
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        for record in records:
            content = f"{record['date']}: " + " ".join(record["transactions"])
            docs.append(Document(page_content=content, metadata={"date": record["date"], "year": year}))
    return docs

def load_draft_csv() -> list[Document]:
    import re

    csv_path = os.path.join(ROOT_DIR, "data", "SAC_draft_history.csv")
    df = pd.read_csv(csv_path)
    df = df[df["Year"] != "Year"].reset_index(drop=True)

    traded_pattern = re.compile(r"\s*\(↳\s*([A-Z]{2,3})\s*\)\s*$")

    docs = []
    for _, row in df.iterrows():
        raw_player = str(row["Player"])
        match = traded_pattern.search(raw_player)
        if match:
            player_name = traded_pattern.sub("", raw_player).strip()
            traded_to = match.group(1)
        else:
            player_name = raw_player.strip()
            traded_to = None

        content = (
            f"{row['Year']} NBA Draft: The Sacramento Kings selected {player_name} "
            f"from {row['College']} with pick #{row['Pk']} in round {row['Rd']}."
        )
        if traded_to:
            content += f" {player_name} was subsequently traded to the {traded_to}."

        career_bits = []
        if pd.notna(row.get("G")):
            career_bits.append(f"played {row['G']} career games")
        if pd.notna(row.get("WS")):
            career_bits.append(f"{row['WS']} career Win Shares")
        if pd.notna(row.get("BPM")):
            career_bits.append(f"BPM {row['BPM']}")
        if pd.notna(row.get("VORP")):
            career_bits.append(f"VORP {row['VORP']}")
        if career_bits:
            content += " Career stats: " + ", ".join(career_bits) + "."

        metadata = {
            "year": str(row["Year"]),
            "round": str(row["Rd"]),
            "pick": str(row["Pk"]),
            "player": player_name,
            "source": "draft",
            "drafted_then_traded": traded_to is not None,
        }
        if traded_to:
            metadata["traded_to"] = traded_to
        docs.append(Document(page_content=content, metadata=metadata))
    return docs

def load_champions_draft_csv() -> list[Document]:
    import re

    CHAMPIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mgmt_history")
    draft_dfs = []
    for entry in os.scandir(CHAMPIONS_DIR):
        if not entry.is_dir():
            continue
        csv_path = os.path.join(entry.path, "draft_history.csv")
        if not os.path.exists(csv_path):
            continue
        df = pd.read_csv(csv_path)
        df["team"] = entry.name.strip()
        # print(df.head())
        df = df[df["Year"] != "Year"].reset_index(drop=True)
        draft_dfs.append(df)

    traded_pattern = re.compile(r"\s*\(↳\s*([A-Z]{2,3})\s*\)\s*$")

    df = pd.concat(draft_dfs)
    # print(df)
    docs = []
    for _, row in df.iterrows():
        raw_player = str(row["Player"])
        match = traded_pattern.search(raw_player)
        drafted_by = row["team"]
        if match:
            player_name = traded_pattern.sub("", raw_player).strip()
            traded_to = match.group(1)
        else:
            player_name = raw_player.strip()
            traded_to = None

        content = (
            f"{row['Year']} NBA Draft: {drafted_by} selected {player_name} "
            f"from {row['College']} with pick #{row['Pk']} in round {row['Rd']}."
        )
        if traded_to:
            content += f" {player_name} was subsequently traded to the {traded_to}."

        career_bits = []
        if pd.notna(row.get("G")):
            career_bits.append(f"played {row['G']} career games")
        if pd.notna(row.get("WS")):
            career_bits.append(f"{row['WS']} career Win Shares")
        if pd.notna(row.get("BPM")):
            career_bits.append(f"BPM {row['BPM']}")
        if pd.notna(row.get("VORP")):
            career_bits.append(f"VORP {row['VORP']}")
        if career_bits:
            content += " Career stats: " + ", ".join(career_bits) + "."

        metadata = {
            "year": str(row["Year"]),
            "round": str(row["Rd"]),
            "pick": str(row["Pk"]),
            "player": player_name,
            "source": "draft",
            "drafted_then_traded": traded_to is not None,
        }
        if traded_to:
            metadata["traded_to"] = traded_to
        docs.append(Document(page_content=content, metadata=metadata))
    return docs

# print(load_champions_draft_csv())

if vector_store._collection.count() == 0:
    print("Vector store empty, loading documents...")
    docs = load_transaction_docs(TRANSACTIONS_DIR) + load_draft_csv() + load_champions_draft_csv()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_splits = text_splitter.split_documents(docs)
    BATCH_SIZE = 5000
    for i in range(0, len(all_splits), BATCH_SIZE):
        vector_store.add_documents(documents=all_splits[i:i + BATCH_SIZE])
    print(f"Loaded {len(all_splits)} chunks into vector store")
else:
    print(f"Vector store already populated ({vector_store._collection.count()} chunks), skipping load")
