from __future__ import annotations

import unittest

from dtm.sigma import matches_rule


class SigmaTest(unittest.TestCase):
    def test_contains_modifier_and_boolean_condition(self) -> None:
        event = {"class_uid": 1007, "process": {"cmd_line": "WHOAMI && CURL example.invalid"}}
        rule = {
            "detection": {
                "selection": {
                    "class_uid": 1007,
                    "process.cmd_line|contains": "curl",
                },
                "filter": {"process.cmd_line|contains": "approved-script"},
                "condition": "selection and not filter",
            }
        }
        self.assertTrue(matches_rule(event, rule))

    def test_filter_suppresses_match(self) -> None:
        event = {"message": "approved-script curl example.invalid"}
        rule = {
            "detection": {
                "selection": {"message|contains": "curl"},
                "filter": {"message|contains": "approved-script"},
                "condition": "selection and not filter",
            }
        }
        self.assertFalse(matches_rule(event, rule))


if __name__ == "__main__":
    unittest.main()

