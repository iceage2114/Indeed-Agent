"""
generate_report node — sorts enriched matches by score, writes report.json and
report.md to the output directory, and prints a summary table to stdout.
"""

import json
from datetime import datetime
from pathlib import Path

import config
from agent.state import AgentState


def generate_report(state: AgentState) -> dict:
    """LangGraph node — compile and write the final ranked report."""
    matches: list = sorted(
        state.get("top_candidates", []),
        key=lambda j: j.get("similarity_score") or 0.0,
        reverse=True,
    )

    output_dir = config.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── JSON report ──────────────────────────────────────────────────────────
    json_path = output_dir / "report.json"
    json_path.write_text(json.dumps(matches, indent=2), encoding="utf-8")

    # ── Markdown report ───────────────────────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resume_name = Path(state.get("resume_path", "resume")).name

    lines: list[str] = []
    lines.append("# Job Match Report")
    lines.append(f"Generated: {now}")
    lines.append(f"Resume: {resume_name}")
    lines.append("")
    lines.append("## Summary Table")
    lines.append("| Rank | Title | Company | Location | Similarity | Easy Apply | Date Posted |")
    lines.append("|------|-------|---------|----------|------------|------------|-------------|")

    for rank, job in enumerate(matches, start=1):
        easy  = "Yes" if job.get("easy_apply") else "No"
        score = f"{job.get('similarity_score', 0.0):.4f}"
        lines.append(
            f"| {rank} | {job.get('title','')} | {job.get('company','')} "
            f"| {job.get('location','')} | {score} "
            f"| {easy} | {job.get('date_posted','')} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    for rank, job in enumerate(matches, start=1):
        easy  = "Yes" if job.get("easy_apply") else "No"
        score = f"{job.get('similarity_score', 0.0):.4f}"
        lines.append(f"## #{rank} — {job.get('title','')} at {job.get('company','')} ({job.get('location','')})")
        lines.append(f"**Similarity Score**: {score}")
        lines.append(f"**Easy Apply**: {easy}")
        lines.append(f"**Field**: {job.get('field','')}")
        lines.append(f"**Date Posted**: {job.get('date_posted','')}")
        lines.append(f"**URL**: {job.get('url','')}")
        lines.append(f"**Description**: {(job.get('description') or '')[:300]}...")
        lines.append("")

    md_path = output_dir / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # ── stdout summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("JOB MATCH REPORT SUMMARY")
    print("=" * 70)
    header = f"{'Rank':<5} {'Similarity':<11} {'Easy':^5}  {'Title':<35} {'Company'}"
    print(header)
    print("-" * 70)
    for rank, job in enumerate(matches, start=1):
        easy    = "Y" if job.get("easy_apply") else "N"
        title   = (job.get("title") or "")[:34]
        company = (job.get("company") or "")[:25]
        score   = f"{job.get('similarity_score', 0.0):.4f}"
        print(f"{rank:<5} {score:<11} {easy:^5}  {title:<35} {company}")
    print("=" * 70)

    return {"final_report_path": str(md_path)}
