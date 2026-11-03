"""Apply the Low Priority label and move the message out of the inbox."""

import os
from functools import lru_cache

from auth import get_gmail_service

LABEL_NAME = os.getenv("LOW_PRIORITY_LABEL", "Low Priority")


@lru_cache(maxsize=1)
def _service():
    return get_gmail_service()  # built once per run, not once per email


@lru_cache(maxsize=1)
def _label_id() -> str:
    service = _service()
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == LABEL_NAME:
            return label["id"]
    created = service.users().labels().create(
        userId="me",
        body={"name": LABEL_NAME, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    ).execute()
    return created["id"]


def apply_low_priority_label(email_id: str) -> None:
    _service().users().messages().modify(
        userId="me",
        id=email_id,
        body={"addLabelIds": [_label_id()], "removeLabelIds": ["INBOX"]},
    ).execute()
