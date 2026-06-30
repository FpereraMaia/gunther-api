"""CLI entry point. Run with: python -m app.cli <command>"""
from __future__ import annotations

import sys


def gmail_auth() -> None:
    from app.infrastructure.banking.gmail.client import GmailClient
    from app.shared.config import settings

    if not settings.gmail_credentials_path:
        print("ERROR: GMAIL_CREDENTIALS_PATH not set in .env")
        sys.exit(1)
    if not settings.gmail_token_path:
        print("ERROR: GMAIL_TOKEN_PATH not set in .env")
        sys.exit(1)

    client = GmailClient(
        credentials_path=settings.gmail_credentials_path,
        token_path=settings.gmail_token_path,
    )
    print("Opening browser for Gmail OAuth...")
    client.authorize()
    print(f"Token saved to {settings.gmail_token_path}")


_COMMANDS = {
    "gmail-auth": gmail_auth,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = _COMMANDS.get(cmd)
    if fn is None:
        print(f"Unknown command: {cmd!r}. Available: {', '.join(_COMMANDS)}")
        sys.exit(1)
    fn()
