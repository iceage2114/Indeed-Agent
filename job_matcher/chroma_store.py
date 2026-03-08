"""
ChromaDB store for job embeddings.

Provides two main entry points:

  populate_chroma(force=False)
      Loads every unapplied job from the SQLite DB, embeds each one using the
      same text-embedding-3-small model as the rest of the pipeline, and upserts
      the results into a persistent ChromaDB collection.  Already-embedded jobs
      are skipped on subsequent runs (idempotent) unless force=True.

  test_chroma(query_text=None, n_results=5)
      Sanity-checks the collection: prints the item count and runs a similarity
      query against query_text (defaults to a generic software-engineer prompt),
      displaying the top matches with their scores.

CLI usage:
  python chroma_store.py                        # populate, then test
  python chroma_store.py --populate-only        # only populate
  python chroma_store.py --test-only            # only test
  python chroma_store.py --query "data engineer python" --n 5
  python chroma_store.py --force                # re-embed all jobs
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import config

COLLECTION_NAME = "jobs"
EMBED_CHARS     = 2000  # chars of description used for embedding (~500 tokens, well under model limit)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_embeddings():
    """Return a LangChain OpenAIEmbeddings instance wired to the configured model."""
    from langchain_openai import OpenAIEmbeddings
    api_key  = config.OPENAI_API_KEY or config.GITHUB_TOKEN
    base_url = None if config.OPENAI_API_KEY else config.LLM_BASE_URL
    return OpenAIEmbeddings(
        model=config.EMBED_MODEL,
        api_key=api_key,
        base_url=base_url,
    )


def _get_chroma_collection():
    """Open (or create) the persistent ChromaDB collection."""
    import chromadb

    config.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},   # use cosine distance for ranking
    )
    return collection


def _job_dedup_key(job: dict) -> str:
    """Stable dedup key — prefer jk= param, fall back to (title, company)."""
    try:
        qs = parse_qs(urlparse(job["url"]).query)
        jk = qs.get("jk")
        if jk:
            return f"jk:{jk[0]}"
    except Exception:
        pass
    return f"tc:{job.get('title', '').lower().strip()}|{job.get('company', '').lower().strip()}"


def _load_jobs_from_db() -> list[dict]:
    """Read all unapplied jobs from the SQLite DB, deduplicated."""
    print(f"[chroma] Loading jobs from {config.DB_PATH} ...")
    conn = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, title, company, location, description, url, "
            "date_posted, field, easy_apply FROM jobs WHERE applied = 0"
        ).fetchall()
    finally:
        conn.close()

    jobs = [
        {
            "id":          str(row["id"]),
            "title":       row["title"]       or "",
            "company":     row["company"]     or "",
            "location":    row["location"]    or "",
            "description": row["description"] or "",
            "url":         row["url"]         or "",
            "date_posted": row["date_posted"] or "",
            "field":       row["field"]       or "",
            "easy_apply":  str(bool(row["easy_apply"])),   # ChromaDB metadata must be str/int/float/bool
        }
        for row in rows
    ]

    # Deduplicate by Indeed job key
    seen: set = set()
    unique: list = []
    for job in jobs:
        key = _job_dedup_key(job)
        if key not in seen:
            seen.add(key)
            unique.append(job)

    print(f"[chroma] {len(rows)} rows fetched → {len(unique)} unique jobs after dedup")
    return unique


# ── Public API ─────────────────────────────────────────────────────────────────

def populate_chroma(force: bool = False, batch_size: int = 100) -> int:
    """
    Embed every unapplied job from SQLite and upsert into ChromaDB.

    Parameters
    ----------
    force : bool
        When True, re-embeds and overwrites all existing entries.
        When False (default), only jobs whose IDs are not yet in the collection
        are embedded and inserted — making repeated runs cheap.
    batch_size : int
        Number of documents embedded per OpenAI API call.

    Returns
    -------
    int
        Number of new documents upserted in this run.
    """
    collection = _get_chroma_collection()
    jobs       = _load_jobs_from_db()

    if not jobs:
        print("[chroma] No unapplied jobs found in the DB — nothing to embed.")
        return 0

    # Determine which jobs need embedding
    if force:
        jobs_to_embed = jobs
        print(f"[chroma] --force: re-embedding all {len(jobs)} jobs")
    else:
        existing_ids = set(collection.get(ids=[j["id"] for j in jobs])["ids"])
        jobs_to_embed = [j for j in jobs if j["id"] not in existing_ids]
        skip_count = len(jobs) - len(jobs_to_embed)
        if skip_count:
            print(f"[chroma] {skip_count} jobs already in collection — skipping")
        print(f"[chroma] {len(jobs_to_embed)} jobs will be embedded and upserted")

    if not jobs_to_embed:
        print(f"[chroma] Collection is up-to-date ({collection.count()} documents total)")
        return 0

    # Build embedding text for each job (mirrors retrieval_subgraph.py)
    texts = [
        f"{j['title']}\n\n{j['description'][:EMBED_CHARS]}".strip()
        for j in jobs_to_embed
    ]

    embeddings_model = _get_embeddings()
    all_vectors: list = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        print(f"[chroma] Embedding jobs {i + 1}–{i + len(batch)} of {len(texts)} ...")
        all_vectors.extend(embeddings_model.embed_documents(batch))

    # Upsert into ChromaDB in the same batches
    upserted = 0
    for i in range(0, len(jobs_to_embed), batch_size):
        batch_jobs = jobs_to_embed[i : i + batch_size]
        batch_vecs = all_vectors[i : i + batch_size]

        collection.upsert(
            ids        = [j["id"] for j in batch_jobs],
            embeddings = batch_vecs,
            documents  = texts[i : i + batch_size],
            metadatas  = [
                {
                    "title":       j["title"],
                    "company":     j["company"],
                    "location":    j["location"],
                    "url":         j["url"],
                    "date_posted": j["date_posted"],
                    "field":       j["field"],
                    "easy_apply":  j["easy_apply"],
                }
                for j in batch_jobs
            ],
        )
        upserted += len(batch_jobs)

    print(f"[chroma] Done — {upserted} jobs upserted. "
          f"Collection now holds {collection.count()} documents.")
    return upserted


def test_chroma(query_text: str | None = None, n_results: int = 5) -> None:
    """
    Verify the ChromaDB collection and run a sample similarity query.

    Parameters
    ----------
    query_text : str | None
        The query to run against the collection.  Defaults to a generic
        software-engineer probe so the function works without arguments.
    n_results : int
        How many results to display (default 5).
    """
    collection = _get_chroma_collection()
    count = collection.count()

    print("\n── ChromaDB collection info ─────────────────────────────────────")
    print(f"  Path       : {config.CHROMA_PATH}")
    print(f"  Collection : {COLLECTION_NAME}")
    print(f"  Documents  : {count}")

    if count == 0:
        print("\n  [!] Collection is empty. Run populate_chroma() first.")
        return

    # ── Sample peek (no embedding needed) ────────────────────────────
    peek = collection.peek(limit=3)
    print("\n  First 3 document excerpts:")
    for i, (doc_id, doc_text) in enumerate(zip(peek["ids"], peek["documents"]), 1):
        meta = peek["metadatas"][i - 1]
        snippet = doc_text[:120].replace("\n", " ")
        print(f"    [{i}] id={doc_id}")
        print(f"        {meta.get('title', '')} @ {meta.get('company', '')} ({meta.get('location', '')})")
        print(f"        \"{snippet}...\"")

    # ── Similarity query ──────────────────────────────────────────────
    if query_text is None:
        query_text = (
            "software engineer python backend REST API "
            "microservices cloud AWS Docker"
        )

    print(f"\n── Similarity query ─────────────────────────────────────────────")
    print(f"  Query: \"{query_text}\"")
    print(f"  Top  : {n_results} results\n")

    embeddings_model = _get_embeddings()
    query_vec = embeddings_model.embed_query(query_text)

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=min(n_results, count),
        include=["documents", "metadatas", "distances"],
    )

    ids        = results["ids"][0]
    metadatas  = results["metadatas"][0]
    distances  = results["distances"][0]

    for rank, (doc_id, meta, dist) in enumerate(zip(ids, metadatas, distances), 1):
        # ChromaDB cosine collection returns *distance* (1 - similarity), so
        # similarity = 1 - distance
        similarity = 1.0 - dist
        print(f"  #{rank:>2}  score={similarity:.4f}  id={doc_id}")
        print(f"       {meta.get('title', '')} @ {meta.get('company', '')}")
        print(f"       {meta.get('location', '')}  |  {meta.get('url', '')[:80]}")
        print()

    print("── Test complete ────────────────────────────────────────────────\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate and/or test the ChromaDB job-embedding store."
    )
    parser.add_argument(
        "--populate-only", action="store_true",
        help="Only run the populate step (skip test).",
    )
    parser.add_argument(
        "--test-only", action="store_true",
        help="Only run the test step (skip populate).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-embed and overwrite all jobs even if already in collection.",
    )
    parser.add_argument(
        "--query", type=str, default=None,
        help="Custom query text for the test step.",
    )
    parser.add_argument(
        "--n", type=int, default=5,
        help="Number of results to show in test query (default: 5).",
    )
    args = parser.parse_args()

    if not config.DB_PATH.exists():
        print(f"ERROR: SQLite database not found: {config.DB_PATH}")
        sys.exit(1)

    if not args.test_only:
        populate_chroma(force=args.force)

    if not args.populate_only:
        test_chroma(query_text=args.query, n_results=args.n)


if __name__ == "__main__":
    main()
