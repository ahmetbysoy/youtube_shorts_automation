"""Environment-based configuration; never commit credentials or tokens."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = ""
    gemini_api_key: str = ""
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    output_dir: Path = PROJECT_ROOT / "output"
    youtube_client_secrets_file: Path = PROJECT_ROOT / "secrets" / "client_secret.json"
    youtube_token_file: Path = PROJECT_ROOT / "secrets" / "youtube_token.json"
    youtube_privacy_status: str = "private"
    request_timeout_seconds: float = 30.0
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "Settings":
        """Read settings without making network requests or requiring secrets."""
        return cls(
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")),
            pexels_api_key=os.getenv("PEXELS_API_KEY", ""),
            pixabay_api_key=os.getenv("PIXABAY_API_KEY", ""),
            output_dir=Path(os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "output"))),
            youtube_client_secrets_file=Path(os.getenv(
                "YOUTUBE_CLIENT_SECRETS_FILE",
                str(PROJECT_ROOT / "secrets" / "client_secret.json"),
            )),
            youtube_token_file=Path(os.getenv(
                "YOUTUBE_TOKEN_FILE",
                str(PROJECT_ROOT / "secrets" / "youtube_token.json"),
            )),
            youtube_privacy_status=os.getenv("YOUTUBE_PRIVACY_STATUS", "private"),
        )
