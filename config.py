import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN      = os.getenv("BOT_TOKEN")
    GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
    GROQ_MODEL     = os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")
