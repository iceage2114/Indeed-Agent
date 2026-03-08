"""
parse_resume node — reads the resume file, extracts raw text, and calls the LLM
to produce a structured JSON summary of the candidate.
"""

from pathlib import Path

import config
from agent.state import AgentState


def _get_llm():
    from langchain_openai import ChatOpenAI

    api_key  = config.OPENAI_API_KEY or config.GITHUB_TOKEN
    base_url = None if config.OPENAI_API_KEY else config.LLM_BASE_URL

    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )


def _extract_text(path: Path) -> str:
    ext = path.suffix.lower()

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )

    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8")

    raise ValueError(f"Unsupported resume format: {ext}")


def parse_resume(state: AgentState) -> dict:
    """
    LangGraph node.

    Loads from cache/resume_cache.json when the file mtime matches, otherwise
    extracts text and calls the LLM for a structured JSON summary.
    """
    path = Path(state["resume_path"])

    if not path.exists():
        return {"error": f"Resume file not found: {path}"}

    try:
        resume_text = _extract_text(path)
    except ValueError as exc:
        return {"error": str(exc)}

    print(f"[parse_resume] Extracted {len(resume_text)} characters from {path.name}")

    # LLM call — structured summary
    llm = _get_llm()
    system_msg = (
        "Extract a structured summary from this resume. "
        "Return ONLY valid JSON with keys: name, contact, years_experience, "
        "tech_skills (list), soft_skills (list), education (list), "
        "certifications (list), target_roles (list), profile (str)."
    )
    from langchain_core.messages import HumanMessage, SystemMessage
    response = llm.invoke([SystemMessage(content=system_msg), HumanMessage(content=resume_text)])
    resume_summary = response.content

    print(f"[parse_resume] Resume summary generated ({len(resume_summary)} chars)")

    return {
        "resume_text":    resume_text,
        "resume_summary": resume_summary,
        "error":          None,
    }
