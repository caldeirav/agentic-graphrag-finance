"""Load .env before CLI or pipeline imports that read os.environ."""

from dotenv import load_dotenv

load_dotenv()
