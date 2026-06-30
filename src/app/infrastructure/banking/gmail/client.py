from __future__ import annotations

import base64
import logging
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


@dataclass
class GmailClient:
    credentials_path: str
    token_path: str

    def _service(self) -> Any:
        creds = self._load_credentials()
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _load_credentials(self) -> Credentials:
        token_file = Path(self.token_path)
        creds: Credentials | None = None

        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), _SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._save_token(creds)
        elif not creds or not creds.valid:
            raise RuntimeError(
                f"Gmail token not found or invalid at {self.token_path}. "
                "Run: python -m app.cli gmail-auth"
            )

        return creds

    def _save_token(self, creds: Credentials) -> None:
        Path(self.token_path).write_text(creds.to_json())

    def authorize(self) -> None:
        """Run the one-time OAuth browser flow. Call from CLI, not from the app."""
        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, _SCOPES)
        creds = flow.run_local_server(port=0)
        self._save_token(creds)
        logger.info("gmail.authorized", extra={"token_path": self.token_path})

    def fetch_attachments(
        self, query: str, ext: str
    ) -> Generator[tuple[str, str, bytes], None, None]:
        """Yield (message_id, filename, bytes) for each matching attachment."""
        service = self._service()
        results = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
        messages = results.get("messages", [])

        for msg_meta in messages:
            msg_id = msg_meta["id"]
            msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

            for part in _iter_parts(msg.get("payload", {})):
                filename = part.get("filename", "")
                if not filename.lower().endswith(ext):
                    continue

                body = part.get("body", {})
                attachment_id = body.get("attachmentId")
                if attachment_id:
                    att = (
                        service.users()
                        .messages()
                        .attachments()
                        .get(userId="me", messageId=msg_id, id=attachment_id)
                        .execute()
                    )
                    data = base64.urlsafe_b64decode(att["data"])
                elif body.get("data"):
                    data = base64.urlsafe_b64decode(body["data"])
                else:
                    continue

                logger.info(
                    "gmail.attachment_found", extra={"msg_id": msg_id, "attachment": filename}
                )
                yield msg_id, filename, data


def _iter_parts(payload: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    yield payload
    for part in payload.get("parts", []):
        yield from _iter_parts(part)
