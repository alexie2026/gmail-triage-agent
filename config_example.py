"""Example rules. Copy this file to config.py (git-ignored) and put your own senders in it.

Rules are evaluated in a strict order and the first match wins (see classifier.py).
Matching is case-insensitive and on whole words or phrases, so "deal" does not match "ideal".
"""

MODEL = "claude-haiku-4-5-20251001"  # override with the CLASSIFIER_MODEL env var
MIN_AGE_YEARS = 5  # unread mail older than this is demoted (protected senders excepted)

# A subject containing any of these is ALWAYS important. Checked before every low-priority rule.
IMPORTANT_OVERRIDES = [
    "security alert", "new device", "login", "log in", "sign-in", "verify",
    "password", "suspicious", "unauthorized", "2fa", "two-factor",
    "account locked", "breach", "boarding pass",
    "job offer", "offer letter", "interview",
]

# A subject that STARTS with one of these is always important.
IMPORTANT_SUBJECT_PREFIXES = ["action required:"]

# Senders that are never demoted by age or rules (substring match on the From header).
PROTECTED_SENDERS = ["partner@example.com"]

# Matched against "sender + subject".
LOW_PRIORITY_KEYWORDS = [
    "newsletter", "unsubscribe", "promotion", "deal", "offer", "trending",
    "weekly digest", "sale", "discount", "we've updated", "updated our terms",
    "how was your", "tell us more", "what do you think",
]

# Matched against the sender (substring).
LOW_PRIORITY_DOMAINS = ["newsletters.example.com", "social.example.com"]
LOW_PRIORITY_SENDER_KEYWORDS = ["jobalerts"]

# (sender domain, subject keywords). None means any subject from that sender.
SENDER_SUBJECT_RULES = [
    ("bank.example.com", ["statement"]),
    ("promo.example.com", None),
]

# Never offer these for the Unsubscribe label: (sender domain, subject keywords).
UNSUBSCRIBE_EXCLUSIONS = [
    ("shop.example.com", ["order confirmation", "receipt"]),
]
