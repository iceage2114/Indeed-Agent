from typing import TypedDict, Optional


class JobCandidate(TypedDict):
    id: str
    title: str
    company: str
    location: str
    description: str            # short description pulled from DB
    url: str
    date_posted: str
    field: str
    easy_apply: bool
    embedding: Optional[list]           # set during retrieval subgraph
    similarity_score: Optional[float]   # cosine similarity vs resume embedding
    full_description: Optional[str]     # scraped from the live job URL
    match_score: Optional[int]          # 1-100, assigned by LLM in enrichment
    match_reasoning: Optional[str]      # LLM explanation of score
    top_skills_matched: Optional[list]  # list[str] extracted by LLM


class AgentState(TypedDict):
    resume_path: str
    resume_text: str                    # raw text extracted from resume file
    resume_embedding: list              # embedding vector of full resume text
    resume_summary: str                 # LLM-structured JSON summary of resume
    all_jobs: list                      # list[JobCandidate] loaded from DB
    top_candidates: list                # list[JobCandidate] after similarity rank
    enriched_matches: list              # list[JobCandidate] after URL scrape + LLM
    final_report_path: str
    error: Optional[str]
