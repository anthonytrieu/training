"""Token storage location and re-authentication messaging.

Credentials are only ever handled interactively by `garmin-setup`; everything
else in this package loads previously saved OAuth tokens from disk.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_TOKEN_DIR = "~/.garminconnect"

REAUTH_MESSAGE = (
    "Garmin session is missing or expired. "
    "Run `garmin-setup` in a terminal to log in again (you may be asked for an MFA code)."
)


def token_store_path() -> Path:
    """Directory holding Garmin OAuth tokens (GARMINTOKENS env var or ~/.garminconnect)."""
    return Path(os.getenv("GARMINTOKENS", DEFAULT_TOKEN_DIR)).expanduser()
