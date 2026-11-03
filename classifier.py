"""Decide whether one email is important or low priority.

Order of evaluation, first match wins:
  1. age rule (skipped for protected senders)
  2. important overrides (security, job offers, interviews ...)
  3. deterministic low-priority rules (keywords, domains, sender+subject)
  4. AI fallback (Claude Haiku), only if nothing above matched

Anything the model returns that cannot be parsed stays important (fail safe).
"""

import datetime
import os
import re

try:
    import config as cfg
except ImportError:  # no personal config yet: use the generic example rules
    import config_example as cfg


def _contains_any(text: str, phrases) -> bool:
    """True if any phrase occurs in text as a whole word or phrase (case-insensitive)."""
    text = text.lower()
    return any(
        re.search(rf"(?<!\w){re.escape(p.lower())}(?!\w)", text) for p in phrases
    )


def is_always_important(email: dict) -> bool:
    subject = email["subject"].lower()
    if any(subject.startswith(p.lower()) for p in cfg.IMPORTANT_SUBJECT_PREFIXES):
        return True
    return _contains_any(subject, cfg.IMPORTANT_OVERRIDES)


def _is_low_priority_by_rules(email: dict) -> bool:
    sender = email["sender"].lower()
    subject = email["subject"].lower()

    if _contains_any(f"{sender} {subject}", cfg.LOW_PRIORITY_KEYWORDS):
        return True
    if any(domain in sender for domain in cfg.LOW_PRIORITY_DOMAINS):
        return True
    if any(kw in sender for kw in cfg.LOW_PRIORITY_SENDER_KEYWORDS):
        return True
    for domain, subject_keywords in cfg.SENDER_SUBJECT_RULES:
        if domain in sender:
            if subject_keywords is None or _contains_any(subject, subject_keywords):
                return True
    return False


def _is_protected_sender(email: dict) -> bool:
    sender = email["sender"].lower()
    return any(s.lower() in sender for s in cfg.PROTECTED_SENDERS)


def _is_older_than_limit(email: dict) -> bool:
    date = email.get("date")
    if not date:
        return False
    cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
        days=cfg.MIN_AGE_YEARS * 365
    )
    return date < cutoff


def _ascii_safe(text: str) -> str:
    """Strip non-ASCII characters before calling the API.

    Known limitation: this was added to work around a UnicodeEncodeError and it
    also blanks non-English text. See "Known limitations" in the README.
    """
    return (text or "").encode("ascii", "ignore").decode("ascii")


def parse_decision(response: str) -> dict:
    """Parse 'DECISION: <IMPORTANT|LOW_PRIORITY> | REASON: <text>'. Unparseable means important."""
    priority = "low_priority" if "LOW_PRIORITY" in response else "important"
    reason = response.split("REASON:")[-1].strip() if "REASON:" in response else response
    return {"priority": priority, "reason": reason}


def _ai_classify(email: dict) -> dict:
    import anthropic  # imported lazily so the rules can be used and tested without the SDK
    from dotenv import load_dotenv

    load_dotenv()
    client = anthropic.Anthropic(
        api_key=_ascii_safe(os.getenv("ANTHROPIC_API_KEY")).strip(),
        timeout=60.0,
        max_retries=3,
    )
    safe_sender = _ascii_safe(email["sender"])
    safe_subject = _ascii_safe(email["subject"])
    safe_body = _ascii_safe(email["body"][:500] or email["snippet"])

    prompt = f"""You are an email importance classifier. Given an email, decide if it is IMPORTANT or LOW_PRIORITY.

IMPORTANT means: requires action, is personal/professional, time-sensitive, financial, security-related, or from a real person.
LOW_PRIORITY means: newsletters, promotions, automated notifications, social media digests, marketing.

Email:
From: {safe_sender}
Subject: {safe_subject}
Body excerpt: {safe_body}

Reply with exactly one line in this format:
DECISION: <IMPORTANT or LOW_PRIORITY> | REASON: <one short sentence>"""

    message = client.messages.create(
        model=os.getenv("CLASSIFIER_MODEL", cfg.MODEL),
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_decision(message.content[0].text.strip())


def classify_email(email: dict, ai=_ai_classify) -> dict:
    """Return {'priority': 'important' | 'low_priority', 'reason': str}."""
    if not _is_protected_sender(email) and _is_older_than_limit(email):
        return {"priority": "low_priority", "reason": f"email older than {cfg.MIN_AGE_YEARS} years"}
    if is_always_important(email):
        return {"priority": "important", "reason": "important override"}
    if _is_low_priority_by_rules(email):
        return {"priority": "low_priority", "reason": "matched rule-based filter"}
    return ai(email)
