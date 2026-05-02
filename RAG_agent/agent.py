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

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import LANGSMITH_API_KEY, ANTHROPIC_API_KEY

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

class transaction(BaseModel):
    transaction_date: str
    transaction_type: Literal["trade", "waive", "signing", "extension", "free agency"]
    assets_gained: Optional[List[str]] = None
    assets_lost: Optional[List[str]] = None


class transactionsReturn(BaseModel):
    transactions: List[transaction]

model = ChatAnthropic(
    model="claude-haiku-4-5",
    temperature=0,
    max_tokens=1000
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

retriever = vector_store.as_retriever()
retrieval_chain_rag_fusion = generate_queries | retriever.map() | reciprocal_rank_fusion
docs = retrieval_chain_rag_fusion.invoke({"question": "Find me all major player transactions mentioning 'Sacramento Kings' since the year 2000, include only player name and the detail of the transaction"})

SYSTEM_PROMPT = """You are a transaction retrieval agent for the Sacramento Kings NBA franchise.

You will be given context retrieved from a database of historical player transactions, and a user question. Your job is to extract all relevant transactions from the context and return them in the structured format provided.

For each transaction:
- transaction_date: the date as a string (e.g. "2003-07-15")
- transaction_type: one of "trade", "waive", "signing", "extension", "free agency"
- assets_gained: players, picks, or cash the Sacramento Kings RECEIVED (null if none)
- assets_lost: players, picks, or cash the Sacramento Kings GAVE UP (null if none)

Only include transactions that are directly relevant to the user's question. Do not invent or infer transactions not present in the context."""

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
question = """find me major, major as in transactions that includes signings,
 waivings, tradings of star players, prospects, etc. Transactions that've occurred 
 2024 onwards, inclusive, by the Sacramento Kings otherwise known as SAC"""
results = chain.invoke({"question" : question})
for transaction_object in results.transactions:
    print(transaction_object)
    with open("GM_notable_transactions.JSON", "w") as file:
        json.dump(transaction_object.model_dump(), file)