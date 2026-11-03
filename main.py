"""Classify every unread email and label the low-priority ones.

Default is a DRY RUN (nothing in Gmail changes). Use --live to apply labels.
Safe to re-run: ids already in the log are skipped.
"""

import argparse
import json
import os
import re
import signal
import socket
import sys
from pathlib import Path

from classifier import classify_email, is_always_important
from gmail_reader import fetch_email_by_id, get_all_unread_ids_oldest_first
from labeler import apply_low_priority_label

LOG_PATH = Path(os.getenv("LOG_PATH", "classification_log.json"))
BATCH_SIZE = 50
PROGRESS_EVERY = 500
MAX_RUNTIME_SECONDS = 2 * 60 * 60


def arm_watchdog() -> None:
    """Hang protection.

    googleapiclient uses httplib2, which has no socket timeout by default, so a stalled
    connection blocks forever. A run that hung for 20 days also stopped launchd from starting
    new runs. Two guards: a global socket timeout, and a wall-clock watchdog that always
    ends the run.
    """
    socket.setdefaulttimeout(90)

    def _abort(signum, frame):
        print(f"[watchdog] run exceeded {MAX_RUNTIME_SECONDS}s - aborting", flush=True)
        sys.exit(1)

    signal.signal(signal.SIGALRM, _abort)
    signal.alarm(MAX_RUNTIME_SECONDS)


def _pattern_key(sender: str, subject: str):
    m = re.search(r"@([\w.]+)>?", sender.lower())
    domain = m.group(1) if m else sender.lower()
    return (domain, re.sub(r"\s+", " ", subject.lower().strip())[:60])


def _load_log(log_path: Path):
    if log_path.exists():
        with open(log_path) as f:
            return json.load(f)
    return []


def run_all(dry_run: bool = True, log_path: Path = LOG_PATH) -> dict:
    all_ids, service = get_all_unread_ids_oldest_first()
    entries = _load_log(log_path)
    done = {e["id"] for e in entries}
    remaining = [i for i in all_ids if i not in done]
    print(f"Unread: {len(all_ids)} | already processed: {len(done)} | remaining: {len(remaining)}")

    # Rebuild seen patterns so duplicate detection is consistent across runs.
    seen = {_pattern_key(e["sender"], e["subject"]) for e in entries}
    counts = {"important": 0, "low_priority": 0, "errors": 0}
    for e in entries:
        counts[e["decision"]] = counts.get(e["decision"], 0) + 1

    for start in range(0, len(remaining), BATCH_SIZE):
        for msg_id in remaining[start:start + BATCH_SIZE]:
            try:
                email = fetch_email_by_id(service, msg_id)
            except Exception as exc:
                print(f"  [error] could not fetch {msg_id}: {exc}")
                counts["errors"] += 1
                continue

            key = _pattern_key(email["sender"], email["subject"])
            # Collapse repeats of the same sender+subject, but never important overrides.
            if key in seen and not is_always_important(email):
                result = {"priority": "low_priority", "reason": "duplicate sender/subject"}
            else:
                seen.add(key)
                result = classify_email(email)

            decision = result["priority"]
            counts[decision] += 1
            if decision == "low_priority" and not dry_run:
                apply_low_priority_label(email["id"])

            entries.append({
                "id": msg_id,
                "sender": email["sender"],
                "subject": email["subject"],
                "date": email["date"].isoformat(),
                "decision": decision,
                "reason": result["reason"],
            })
            if len(entries) % PROGRESS_EVERY == 0:
                print(f"-- {len(entries)} processed: {counts}")

        # Save after every batch so an interrupted run loses nothing.
        with open(log_path, "w") as f:
            json.dump(entries, f, indent=2)

    print(f"DONE. total={len(entries)} {counts}" + (" (dry run, nothing moved)" if dry_run else ""))
    return {"total": len(entries), **counts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="apply labels (default: dry run)")
    args = parser.parse_args()
    arm_watchdog()
    run_all(dry_run=not args.live)
