"""Interactive Garmin Connect login: `garmin-setup`.

Prompts for email, password and (if required) an MFA code, then saves OAuth
tokens to the token directory. Credentials exist only in process memory for
the duration of this command — they are never written to disk or logged.
"""

from __future__ import annotations

import logging
import sys
from getpass import getpass

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .auth import token_store_path


def main() -> int:
    # Keep library logging quiet so no request/session details end up on screen.
    logging.getLogger("garminconnect").setLevel(logging.ERROR)
    logging.getLogger("garth").setLevel(logging.ERROR)

    tokens = token_store_path()
    print("Garmin Connect setup")
    print("Your email and password are used once to obtain OAuth tokens and are not stored.")
    print(f"Tokens will be saved to: {tokens}\n")

    try:
        email = input("Garmin email: ").strip()
        password = getpass("Garmin password (hidden): ")
        if not email or not password:
            print("Email and password are both required.", file=sys.stderr)
            return 1

        api = Garmin(
            email=email,
            password=password,
            prompt_mfa=lambda: input("MFA code: ").strip(),
        )
        api.login(str(tokens))
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        return 130
    except GarminConnectAuthenticationError:
        print("Login failed: Garmin rejected the email/password (or MFA code).", file=sys.stderr)
        return 1
    except GarminConnectTooManyRequestsError:
        print("Garmin rate limit hit (HTTP 429). Wait a few minutes and retry.", file=sys.stderr)
        return 1
    except GarminConnectConnectionError as e:
        print(f"Could not reach Garmin Connect: {e}", file=sys.stderr)
        return 1

    name = api.get_full_name() or "your Garmin account"
    print(f"\nLogged in as {name}.")
    print(f"Tokens saved to {tokens} — future commands will reuse them automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
