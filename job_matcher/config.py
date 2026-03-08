import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR    = Path(__file__).parent
DB_PATH     = Path(os.getenv("DB_PATH",     str(BASE_DIR / "../backend/data/jobs.db"))).resolve()
RESUME_PATH = Path(os.getenv("RESUME_PATH", str(BASE_DIR / "resume/resume.pdf"))).resolve()
OUTPUT_DIR  = Path(os.getenv("OUTPUT_DIR",  str(BASE_DIR / "output"))).resolve()
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", str(BASE_DIR / "chroma_db"))).resolve()
TOP_N       = int(os.getenv("TOP_N_CANDIDATES", 20))

GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Use GitHub Models endpoint unless a direct OpenAI key is set
LLM_BASE_URL = "https://models.inference.ai.azure.com"
LLM_MODEL    = "gpt-4o"
EMBED_MODEL  = "text-embedding-3-small"
