"""Read unread mail from Gmail."""

import base64
import datetime

from auth import get_gmail_service


def _list_all_unread_ids(service):
    """Page through every unread message id (the API returns newest first)."""
    ids, page_token = [], None
    while True:
        kwargs = {"userId": "me", "q": "is:unread", "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token
        result = service.users().messages().list(**kwargs).execute()
        ids.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return ids


def get_all_unread_ids_oldest_first():
    service = get_gmail_service()
    all_ids = _list_all_unread_ids(service)
    all_ids.reverse()
    return [m["id"] for m in all_ids], service


def fetch_email_by_id(service, msg_id):
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    internal_date_ms = int(msg.get("internalDate", 0))
    return {
        "id": msg_id,
        "subject": headers.get("Subject", "(no subject)"),
        "sender": headers.get("From", "(unknown sender)"),
        "snippet": msg.get("snippet", ""),
        "body": _extract_body(msg["payload"])[:2000],  # cap what is sent to the model
        "date": datetime.datetime.fromtimestamp(internal_date_ms / 1000, tz=datetime.timezone.utc),
    }


def _extract_body(payload):
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        return _extract_body(payload["parts"][0])
    data = payload["body"].get("data", "")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""
