import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set. Run: export GROQ_API_KEY=your_key")
