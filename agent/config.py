import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "openai/gpt-oss-120b"

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set. Add it to .env or run: export GROQ_API_KEY=your_key")