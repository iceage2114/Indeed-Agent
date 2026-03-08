"""
Retrieval subgraph — ChromaDB-backed:
  embed_resume → query_chroma

Embeds the resume using text-embedding-3-small, then queries the pre-populated
ChromaDB collection for the top-N most similar jobs.  Job embeddings are never
computed at runtime; run `python chroma_store.py` once (or after new scrapes)
to keep the collection current.
"""

import sqlite3
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

import config


# ── Sub-state ─────────────────────────────────────────────────────────────────

class RetrievalState(TypedDict):
    resume_text: str
    resume_embedding: list
    all_jobs: list          # kept for graph-state compatibility (empty after this subgraph)
    top_candidates: list    # list[JobCandidate]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_embeddings():
    from langchain_openai import OpenAIEmbeddings
    api_key  = config.OPENAI_API_KEY or config.GITHUB_TOKEN
    base_url = None if config.OPENAI_API_KEY else config.LLM_BASE_URL
    return OpenAIEmbeddings(
        model=config.EMBED_MODEL,
        api_key=api_key,
        base_url=base_url,
    )


def _get_chroma_collection():
    import chromadb
    from chroma_store import COLLECTION_NAME
    client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
    return client.get_collection(name=COLLECTION_NAME)


# ── Nodes ─────────────────────────────────────────────────────────────────────

def embed_resume(state: RetrievalState) -> dict:
    """Embed the resume text."""
    print("[retrieval] Embedding resume...")
    embeddings = _get_embeddings()
    vector = embeddings.embed_query(state["resume_text"])
    print(f"[retrieval] Resume embedding: {len(vector)}-dim vector")
    return {"resume_embedding": vector}


def query_chroma(state: RetrievalState) -> dict:
    """
    Query ChromaDB with the resume embedding to retrieve the top-N most similar
    jobs, then hydrate each result with its full description from SQLite.
    """
    collection = _get_chroma_collection()
    count = collection.count()
    if count == 0:
        raise RuntimeError(
            "ChromaDB collection is empty. "
            "Run `python chroma_store.py` to populate it first."
        )

    # Over-fetch slightly so we still have TOP_N after any SQLite misses
    n_fetch = min(config.TOP_N * 3, count)
    results = collection.query(
        query_embeddings=[state["resume_embedding"]],
        n_results=n_fetch,
        include=["metadatas", "distances"],
    )

    ids       = results["ids"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    print(f"[retrieval] ChromaDB returned {len(ids)} candidates (collection size: {count})")

    # Fetch full descriptions for just these N job IDs from SQLite
    placeholders = ",".join("?" * len(ids))
    conn = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT id, description FROM jobs WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
    finally:
        conn.close()
    desc_map = {row["id"]: row["description"] or "" for row in rows}

    # Build candidate dicts in similarity order
    candidates = []
    for job_id, meta, dist in zip(ids, metadatas, distances):
        # ChromaDB cosine collection stores distance = 1 - cosine_similarity
        similarity = 1.0 - dist
        candidates.append({
            "id":                 job_id,
            "title":             meta.get("title", ""),
            "company":           meta.get("company", ""),
            "location":          meta.get("location", ""),
            "description":       desc_map.get(job_id, ""),
            "url":               meta.get("url", ""),
            "date_posted":       meta.get("date_posted", ""),
            "field":             meta.get("field", ""),
            "easy_apply":        meta.get("easy_apply", "False") == "True",
            "embedding":         None,   # not needed downstream
            "similarity_score":  similarity,
            "full_description":  None,
            "match_score":       None,
            "match_reasoning":   None,
            "top_skills_matched": None,
        })

    top = candidates[:config.TOP_N]
    if top:
        print(f"[retrieval] Top {len(top)} candidates selected "
              f"(similarity scores {top[0]['similarity_score']:.4f} "
              f"– {top[-1]['similarity_score']:.4f})")

    return {"top_candidates": top, "all_jobs": []}


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_retrieval_subgraph() -> StateGraph:
    graph = StateGraph(RetrievalState)

    graph.add_node("embed_resume", embed_resume)
    graph.add_node("query_chroma", query_chroma)

    graph.add_edge(START,          "embed_resume")
    graph.add_edge("embed_resume", "query_chroma")
    graph.add_edge("query_chroma", END)

    return graph
