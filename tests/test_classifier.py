import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import classifier  # noqa: E402


def make_email(subject, sender="someone@example.org", days_old=1):
    return {
        "id": "x", "subject": subject, "sender": sender, "snippet": "", "body": "",
        "date": datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=days_old),
    }


def ai_important(_email):
    return {"priority": "important", "reason": "stub model"}


class RuleOrderTests(unittest.TestCase):
    def classify(self, email):
        return classifier.classify_email(email, ai=ai_important)

    def test_security_override_beats_low_priority_rules(self):
        e = make_email("Security alert: new sign-in", sender="newsletter@newsletters.example.com")
        self.assertEqual(self.classify(e)["priority"], "important")

    def test_job_offer_is_never_demoted(self):
        e = make_email("Your job offer from Acme", sender="hr@acme.example")
        self.assertEqual(self.classify(e)["priority"], "important")

    def test_marketing_offer_is_low_priority(self):
        e = make_email("Special offer inside, 50% off")
        self.assertEqual(self.classify(e)["priority"], "low_priority")

    def test_keywords_match_whole_words_only(self):
        # "deal" must not match "ideal"; falls through to the (stubbed) model
        e = make_email("An ideal day out")
        self.assertEqual(self.classify(e)["reason"], "stub model")

    def test_low_priority_domain(self):
        e = make_email("Your update", sender="Digest <hi@newsletters.example.com>")
        self.assertEqual(self.classify(e)["priority"], "low_priority")

    def test_sender_subject_rule_with_and_without_keywords(self):
        stmt = make_email("Your statement is ready", sender="no-reply@bank.example.com")
        other = make_email("Fraud warning", sender="no-reply@bank.example.com")
        promo = make_email("Anything at all", sender="x@promo.example.com")
        self.assertEqual(self.classify(stmt)["priority"], "low_priority")
        self.assertEqual(self.classify(other)["reason"], "stub model")
        self.assertEqual(self.classify(promo)["priority"], "low_priority")

    def test_subject_prefix_override(self):
        e = make_email("Action required: confirm your booking", sender="x@promo.example.com")
        self.assertEqual(self.classify(e)["priority"], "important")


class AgeRuleTests(unittest.TestCase):
    def test_old_mail_is_demoted(self):
        e = make_email("Hello", days_old=6 * 365)
        self.assertEqual(classifier.classify_email(e, ai=ai_important)["priority"], "low_priority")

    def test_protected_sender_is_not_demoted_by_age(self):
        e = make_email("Hello", sender="Partner <partner@example.com>", days_old=6 * 365)
        self.assertEqual(classifier.classify_email(e, ai=ai_important)["reason"], "stub model")


class ParseDecisionTests(unittest.TestCase):
    def test_low_priority(self):
        r = classifier.parse_decision("DECISION: LOW_PRIORITY | REASON: marketing blast")
        self.assertEqual(r, {"priority": "low_priority", "reason": "marketing blast"})

    def test_important(self):
        self.assertEqual(
            classifier.parse_decision("DECISION: IMPORTANT | REASON: from a person")["priority"],
            "important",
        )

    def test_unparseable_output_fails_safe_to_important(self):
        self.assertEqual(classifier.parse_decision("I am not sure")["priority"], "important")


if __name__ == "__main__":
    unittest.main()
