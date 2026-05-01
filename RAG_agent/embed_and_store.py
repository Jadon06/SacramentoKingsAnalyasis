import os
import sys
import json
import glob
from langchain_core.documents import Document
from langchain.chat_models import init_chat_model
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

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

if vector_store._collection.count() == 0:
    print("Vector store empty, loading documents...")
    docs = load_transaction_docs(TRANSACTIONS_DIR)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_splits = text_splitter.split_documents(docs)
    BATCH_SIZE = 5000
    for i in range(0, len(all_splits), BATCH_SIZE):
        vector_store.add_documents(documents=all_splits[i:i + BATCH_SIZE])
    print(f"Loaded {len(all_splits)} chunks into vector store")
else:
    print(f"Vector store already populated ({vector_store._collection.count()} chunks), skipping load")
