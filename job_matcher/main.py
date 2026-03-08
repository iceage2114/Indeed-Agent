"""
CLI entry point for the Job Matcher Agent.

Usage:
  python main.py
  python main.py --resume ./resume/my_cv.pdf
  python main.py --resume ./resume/my_cv.pdf --top-n 7
"""

import sys
import argparse
from pathlib import Path

import config


def main() -> None:
    parser = argparse.ArgumentParser(description="Job Matcher Agent — match your resume to scraped Indeed jobs.")
    parser.add_argument(
        "--resume",
        type=Path,
        default=config.RESUME_PATH,
        help=f"Path to resume file (.pdf, .txt, or .md). Default: {config.RESUME_PATH}",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=config.TOP_N,
        help=f"Number of top job candidates to enrich and report. Default: {config.TOP_N}",
    )
    args = parser.parse_args()

    # Override config values with CLI args
    resume_path: Path = args.resume.resolve()
    config.TOP_N = args.top_n

    # Verify resume file exists before invoking the graph
    if not resume_path.exists():
        print(f"ERROR: Resume file not found: {resume_path}")
        sys.exit(1)

    initial_state = {
        "resume_path": str(resume_path),
        "resume_text": "",
        "resume_embedding": [],
        "resume_summary": "",
        "all_jobs": [],
        "top_candidates": [],
        "enriched_matches": [],
        "final_report_path": "",
        "error": None,
    }

    print(f"Starting Job Matcher Agent...")
    print(f"  Resume : {resume_path}")
    print(f"  DB     : {config.DB_PATH}")
    print(f"  Top N  : {config.TOP_N}")
    print()

    from agent.graph import build_graph
    app = build_graph()

    result = app.invoke(initial_state)

    if result.get("error"):
        print(f"\nERROR: {result['error']}")
        sys.exit(1)

    print(f"\nReport saved to: {result['final_report_path']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nUnhandled error: {exc}")
        sys.exit(1)
