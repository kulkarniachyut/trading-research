"""Settings + secrets loading.

`settings.yaml` holds non-sensitive knobs (universe, costs, risk) and is committed.
Secrets (API keys) live in the git-ignored ``.env`` or ``config/secrets.yaml`` and are
resolved here so no other module hard-codes credential plumbing. Importing this module never
crashes when secrets are absent — providers decide how to react to missing keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

# Repo root = two levels up from this file (src/core/config.py -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = REPO_ROOT / "config" / "settings.yaml"
SECRETS_PATH = REPO_ROOT / "config" / "secrets.yaml"
ENV_PATH = REPO_ROOT / ".env"


@lru_cache(maxsize=1)
def load_settings() -> dict[str, Any]:
    """Parse ``config/settings.yaml`` into a plain dict (cached)."""
    with SETTINGS_PATH.open("r") as fh:
        return yaml.safe_load(fh) or {}


def _load_dotenv(path: Path = ENV_PATH) -> dict[str, str]:
    """Minimal ``.env`` parser (``KEY=VALUE`` lines, ``#`` comments). No external dep."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip("'\"")
    return values


def _load_secrets_yaml(path: Path = SECRETS_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r") as fh:
        return yaml.safe_load(fh) or {}


@dataclass(frozen=True, slots=True)
class AlpacaCredentials:
    api_key_id: str
    api_secret_key: str


def alpaca_credentials() -> Optional[AlpacaCredentials]:
    """Resolve Alpaca keys from (in priority order) the process env, ``.env``, then
    ``config/secrets.yaml``. Returns ``None`` if no complete pair is found.

    Recognized names: ``ALPACA_API_KEY_ID`` / ``ALPACA_API_SECRET_KEY`` (env + .env), or an
    ``alpaca: {api_key_id, api_secret_key}`` block in ``config/secrets.yaml``.
    """
    dotenv = _load_dotenv()
    key = os.environ.get("ALPACA_API_KEY_ID") or dotenv.get("ALPACA_API_KEY_ID")
    secret = os.environ.get("ALPACA_API_SECRET_KEY") or dotenv.get("ALPACA_API_SECRET_KEY")

    if not (key and secret):
        block = _load_secrets_yaml().get("alpaca", {}) or {}
        key = key or block.get("api_key_id")
        secret = secret or block.get("api_secret_key")

    if key and secret:
        return AlpacaCredentials(api_key_id=key, api_secret_key=secret)
    return None
