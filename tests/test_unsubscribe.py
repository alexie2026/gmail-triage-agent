import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unsubscribe  # noqa: E402


def html_part(html):
    return {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(html.encode()).decode()}}


class UnsubscribeTests(unittest.TestCase):
    def test_finds_link_in_nested_html_parts(self):
        payload = {"parts": [{"mimeType": "text/plain", "body": {"data": ""}},
                             {"parts": [html_part('<a href="https://x.example/unsubscribe?id=1">stop</a>')]}]}
        self.assertTrue(unsubscribe.has_unsubscribe_href(unsubscribe.extract_html_body(payload)))

    def test_plain_word_in_text_is_not_a_link(self):
        self.assertFalse(unsubscribe.has_unsubscribe_href("<p>Click to unsubscribe</p>"))

    def test_exclusions_use_sender_and_subject(self):
        keep = {"sender": "Shop <hi@shop.example.com>", "subject": "Your order confirmation"}
        other = {"sender": "Shop <hi@shop.example.com>", "subject": "Sale ends soon"}
        self.assertTrue(unsubscribe.is_excluded(keep))
        self.assertFalse(unsubscribe.is_excluded(other))


if __name__ == "__main__":
    unittest.main()
