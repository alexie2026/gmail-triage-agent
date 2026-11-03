"""Find recent low-priority emails that contain an unsubscribe link.

Read-only by default. With --apply it prints the FULL list, then asks for an explicit "yes"
before adding an "Unsubscribe" label. It never clicks links and never deletes anything.
"""

import argparse
import base64
import datetime
import json
import os
import re
import sys
from pathlib import Path

try:
    import config as cfg
except ImportError:
    import config_example as cfg

LOG_PATH = Path(os.getenv("LOG_PATH", "classification_log.json"))
LABEL_NAME = "Unsubscribe"


def extract_html_body(payload) -> str:
    """Recursively collect every text/html part."""
    html = ""
    if "parts" in payload:
        for part in payload["parts"]:
            html += extract_html_body(part)
    elif payload.get("mimeType") == "text/html":
        data = payload["body"].get("data", "")
        if data:
            html += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return html


def has_unsubscribe_href(html: str) -> bool:
    return bool(re.search(r'href=["\'][^"\']*unsubscribe[^"\']*["\']', html, re.IGNORECASE))


def is_excluded(entry: dict) -> bool:
    sender, subject = entry["sender"].lower(), entry["subject"].lower()
    return any(
        domain in sender and any(kw in subject for kw in keywords)
        for domain, keywords in cfg.UNSUBSCRIBE_EXCLUSIONS
    )


def find_candidates(service, entries: list, days: int = 30):
    cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=days)
    recent_low = [
        e for e in entries
        if e.get("decision") == "low_priority" and e.get("id")
        and datetime.datetime.fromisoformat(e["date"]) >= cutoff
    ]
    candidates, errors = [], 0
    for e in recent_low:
        try:
            msg = service.users().messages().get(userId="me", id=e["id"], format="full").execute()
        except Exception:
            errors += 1  # counted and reported, not silently ignored
            continue
        if has_unsubscribe_href(extract_html_body(msg["payload"])) and not is_excluded(e):
            candidates.append(e)
    return candidates, errors, len(recent_low)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="label the candidates after confirmation")
    args = parser.parse_args()

    from auth import get_gmail_service  # lazy: keeps the pure functions importable in tests

    with open(LOG_PATH) as f:
        entries = json.load(f)
    service = get_gmail_service()
    candidates, errors, checked = find_candidates(service, entries)

    print(f"Checked {checked} recent low-priority emails, {errors} could not be read.")
    print(f"{len(candidates)} contain an unsubscribe link:\n")
    for i, e in enumerate(candidates, 1):
        print(f"{i:<4} {e['date'][:10]}  {e['sender'][:38]:<40} {e['subject'][:52]}")

    if not args.apply or not candidates:
        return
    if input(f"\nAdd the '{LABEL_NAME}' label to {len(candidates)} emails? (yes/no) ").strip().lower() != "yes":
        print("Aborted. No labels applied.")
        return

    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    label_id = next((l["id"] for l in labels if l["name"] == LABEL_NAME), None)
    if label_id is None:
        label_id = service.users().labels().create(
            userId="me",
            body={"name": LABEL_NAME, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        ).execute()["id"]

    applied = failed = 0
    for e in candidates:
        try:
            service.users().messages().modify(
                userId="me", id=e["id"], body={"addLabelIds": [label_id]}
            ).execute()
            applied += 1
        except Exception:
            failed += 1
    print(f"Labels applied: {applied}, failed: {failed}")


if __name__ == "__main__":
    main()
