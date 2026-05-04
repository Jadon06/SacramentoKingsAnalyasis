from langchain.tools import tool
from embed_and_store import vector_store
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic
from langchain_core.load import dumps, loads
from langchain_core.runnables import RunnablePassthrough
from langchain_anthropic import ChatAnthropic
from operator import itemgetter
from pydantic import BaseModel
from typing import List, Literal, Optional
import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import LANGSMITH_API_KEY, ANTHROPIC_API_KEY

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

class transaction(BaseModel):
    transaction_date: str
    transaction_type: Literal["trade", "waive", "signing", "extension", "free agency", "draft"]
    assets_gained: Optional[List[str]] = "N/A"
    assets_lost: Optional[List[str]] = "N/A"


class transactionsReturn(BaseModel):
    transactions: List[transaction]

model = ChatAnthropic(
    model="claude-haiku-4-5",
    temperature=0,
    max_tokens=4000
).with_structured_output(transactionsReturn)



# Use RAG fusion to help the agent create better queries
prompt_template = """You are a helpful assistant that generates multiple search queries based on a single input query. \n
Generate multiple search queries related to: {question} \n
Output (4 queries):"""
prompt_rag_fusion = ChatPromptTemplate.from_template(prompt_template)

generate_queries = (
    prompt_rag_fusion 
    | ChatAnthropic(temperature=0, model_name="claude-haiku-4-5")
    | StrOutputParser() 
    | (lambda x: x.split("\n"))
)

def reciprocal_rank_fusion(results: list[list], k=60):
    """ Reciprocal_rank_fusion that takes multiple lists of ranked documents 
        and an optional parameter k used in the RRF formula """
    
    # Initialize a dictionary to hold fused scores for each unique document
    fused_scores = {}

    # Iterate through each list of ranked documents
    for docs in results:
        # Iterate through each document in the list, with its rank (position in the list)
        for rank, doc in enumerate(docs):
            # Convert the document to a string format to use as a key (assumes documents can be serialized to JSON)
            doc_str = dumps(doc)
            # If the document is not yet in the fused_scores dictionary, add it with an initial score of 0
            if doc_str not in fused_scores:
                fused_scores[doc_str] = 0
            # Retrieve the current score of the document, if any
            previous_score = fused_scores[doc_str]
            # Update the score of the document using the RRF formula: 1 / (rank + k)
            fused_scores[doc_str] += 1 / (rank + k)

    # Sort the documents based on their fused scores in descending order to get the final reranked results
    reranked_results = [
        (loads(doc), score)
        for doc, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    ]

    # Return the reranked results as a list of tuples, each containing the document and its fused score
    return reranked_results

from langchain_core.runnables import RunnableLambda
from langchain_core.documents import Document

transactions_retriever = vector_store.as_retriever(
    search_kwargs={"k": 30}  # broader — we filter by "Sacramento Kings" client-side
)

def fetch_drafts_since_2000() -> list[Document]:
    raw = vector_store._collection.get(where={"source": "draft"})
    seen = set()
    docs = []
    for content, metadata in zip(raw["documents"], raw["metadatas"]):
        try:
            year = int(metadata.get("year", "0"))
        except (ValueError, TypeError):
            continue
        if year < 2000:
            continue
        key = (metadata.get("player"), year, metadata.get("pick"))
        if key in seen:
            continue
        seen.add(key)
        docs.append(Document(page_content=content, metadata=metadata))
    return docs

def retrieve_context(input_dict: dict) -> list[Document]:
    question = input_dict["question"]
    queries = generate_queries.invoke({"question": question})

    # RAG fusion for transactions
    txn_results = []
    for q in queries:
        txn_docs = transactions_retriever.invoke(q)
        sac_txn_docs = [d for d in txn_docs if "sacramento kings" in d.page_content.lower()]
        txn_results.append(sac_txn_docs)
    fused_txns = reciprocal_rank_fusion(txn_results)
    txn_docs = [doc for doc, _ in fused_txns[:50]]

    # All drafts since 2000 (deterministic, no fusion)
    drafts = fetch_drafts_since_2000()

    return txn_docs + drafts

retrieval_chain_rag_fusion = RunnableLambda(retrieve_context)

SYSTEM_PROMPT = """You are a transaction retrieval agent for the Sacramento Kings NBA franchise.

You will be given context retrieved from a database of historical NBA teams player transactions and draft picks, and a user question. Your job is to extract relevant events from the context and return them in the structured format provided.

For each entry:
- transaction_date: the date as a string (e.g. "2003-07-15"). For draft picks, use the year only (e.g. "2020").
- transaction_type: one of "trade", "waive", "signing", "extension", "free agency", "draft"
- assets_gained: players, picks, or cash the Sacramento Kings RECEIVED (null if none)
- assets_lost: players, picks, or cash the Sacramento Kings GAVE UP (null if none)

For draft picks specifically:
- transaction_type is "draft"
- assets_gained is a list containing exactly one string formatted as "Player Name (R{{round}} P{{pick}})", e.g. ["Devin Carter (R1 P13)"]. ALWAYS wrap the player string in a list, even though there is only one player.
- assets_lost is null

## "Major" filter

Apply this filter ONLY when the user's question explicitly asks for "major" (or synonyms like "significant" / "notable") events. Otherwise, return all relevant events without this filter.

### Major transactions (trade / signing / waive / extension / free agency)

A transaction qualifies if it meets AT LEAST ONE of:
1. **Star or notable prospect involvement** — All-Stars, All-NBA selections, established NBA starters, hall-of-fame caliber players, or high-profile draft prospects.
2. **First-round draft pick** changing hands — any first-round pick, regardless of slot.
3. **Significant contract** — multi-year deals, max or near-max contracts, mid-level exception signings, or any deal of clear monetary weight.
4. **Franchise-altering / era-defining** in retrospect — moves that visibly reshaped the team's direction, even if criteria 1–3 are borderline.

NEVER include the following (always routine, never major):
- 10-day contracts
- Two-way contract signings
- Training camp invites or summer league signings
- Waivers or releases of bench / end-of-roster players
- G-League assignments

### Major draft picks

A draft pick qualifies as major if the player **became a meaningful NBA player**. Use the career stats and any contextual notes in the retrieved doc to judge this. A pick is major if AT LEAST ONE applies:
1. **All-Star or All-NBA selection** at any point in their career.
2. **Hall-of-Fame caliber** career or trajectory.
3. **Established NBA rotation player or starter** — any player who became a regular contributor on an NBA team for multiple seasons, even if they never made an All-Star team. This includes role players, sixth men, reliable starters, and late-round finds who carved out a real career.
4. **High-impact young player** — established as a franchise cornerstone or led a team to deep playoff success (Conference Finals or NBA Finals as a primary contributor). Tyrese Haliburton (drafted by SAC in 2020, traded to IND, led IND to a Finals appearance) qualifies here — post-trade impact still counts toward majorness of the original SAC pick.
5. **Notable career production** — any positive career VORP, OR a clearly above-replacement BPM/WS, OR a meaningful NBA career length (multiple seasons with regular minutes).

The ONLY picks to exclude are those who **clearly never made it in the NBA** — players with no NBA games, or only a handful of garbage-time minutes before washing out. Everyone else, INCLUDE. The user prefers to filter further on their end rather than miss interesting picks.

### Drafted-then-traded picks

When a draft doc indicates the player was drafted by SAC and then traded away (e.g. "subsequently traded to TOR"), return the **draft event** here as type "draft". The trade event itself, if present in the transaction context, will be returned separately as type "trade" — do not invent a trade entry from the draft doc alone, since the draft doc lacks the actual trade date and compensation. If the same trade also appears in the transaction context with a real date, include both: one "draft" entry and one "trade" entry.

### Borderline cases

When in doubt, INCLUDE. The user prefers to filter further downstream rather than miss notable events.

## General rules

Only include events present in the provided context. Do not invent or infer events. Only include events directly relevant to the user's question."""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "Context:\n{context}\n\nQuestion: {question}"),
])

chain = (
    {"context": retrieval_chain_rag_fusion,
     "question": itemgetter("question")}
    | prompt
    | model
)
question = """find me major transactions and major drafts made by teams since the year 2000 inclusive. Include trades, signings, waives, extensions, free agency moves, and draft picks — anything that meets the major criteria."""
results = chain.invoke({"question" : question})
print(f"Got {len(results.transactions)} results")

import csv

def save_transaction():
    csv_data = [
        ["transaction_date", "transaction_type", "assets_gained", "assets_lost"]
    ]
    for transaction_object in results.transactions:
        print(transaction_object)
        transaction_date = transaction_object.transaction_date
        transaction_type = transaction_object.transaction_type
        assets_gained = transaction_object.assets_gained
        assets_lost = transaction_object.assets_lost
        csv_data.append([transaction_date, transaction_type, assets_gained, assets_lost])

    with open("champions_major_transacts.csv", 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(csv_data)

    return "done"

save_transaction()