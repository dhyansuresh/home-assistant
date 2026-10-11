"""Load repository-root local settings for backend services."""

from pathlib import Path

from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = REPOSITORY_ROOT / ".env"


def load_local_environment() -> None:
    """Load root .env without overriding values already set by the process."""
    load_dotenv(ROOT_ENV_FILE, override=False)
