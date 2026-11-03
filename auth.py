"""Gmail OAuth. Least privilege, and never opens a browser when run headless."""

import os
import sys

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# gmail.modify = read, label and move mail. It cannot permanently delete anything.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "token.json")
CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")


def _run_browser_flow():
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    return flow.run_local_server(port=0)


def _fail_headless(reason: str):
    raise RuntimeError(
        f"{reason} and there is no interactive terminal to log in. "
        "Run `python main.py` from a terminal once to authenticate."
    )


def get_gmail_service():
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Expired or revoked token. A scheduled (headless) run must NOT delete the
                # token or try to open a browser: keep the file for manual recovery and fail loudly.
                if not sys.stdin.isatty():
                    _fail_headless("Gmail token expired or revoked")
                print("Saved token is expired or revoked - re-authenticating in the browser...")
                os.remove(TOKEN_FILE)
                creds = _run_browser_flow()
        else:
            if not sys.stdin.isatty():
                _fail_headless("No valid Gmail token")
            creds = _run_browser_flow()

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)
