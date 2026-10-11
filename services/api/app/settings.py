"""Repository paths and local configuration for the backend services."""

from functools import cache
from pathlib import Path

from dotenv import load_dotenv

# services/api/app/settings.py -> repository root
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@cache
def load_local_environment() -> None:
    """Read the repository's .env once. Values already set in the process environment win."""
    load_dotenv(REPOSITORY_ROOT / ".env", override=False)
