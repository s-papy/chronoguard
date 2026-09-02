import unittest
from datetime import date

from chronoguard.registry import (
    KNOWLEDGE_CUTOFFS,
    UnknownModelError,
    check_knowledge_cutoff,
    get_cutoff,
)


class TestRegistryLookup(unittest.TestCase):
    def test_known_model_case_insensitive(self):
        entry = get_cutoff("GPT-4o")
        self.assertEqual(entry.model, "gpt-4o")
        self.assertEqual(entry.cutoff, date(2023, 10, 1))

    def test_unknown_model_lists_alternatives(self):
        with self.assertRaises(UnknownModelError) as ctx:
            get_cutoff("not-a-real-model")
        self.assertIn("gpt-4o", str(ctx.exception))

    def test_registry_is_not_empty(self):
        self.assertGreater(len(KNOWLEDGE_CUTOFFS), 0)

    def test_every_entry_has_a_confidence_label(self):
        for key, entry in KNOWLEDGE_CUTOFFS.items():
            self.assertIn(
                entry.confidence,
                ("documented", "approximate"),
                f"{key} has an unrecognized confidence label: {entry.confidence!r}",
            )


class TestCheckKnowledgeCutoff(unittest.TestCase):
    def test_simulated_date_before_cutoff_is_at_risk(self):
        warning = check_knowledge_cutoff("gpt-4o", date(2023, 1, 1))
        self.assertTrue(warning.at_risk)
        self.assertEqual(warning.days_of_exposure, (date(2023, 10, 1) - date(2023, 1, 1)).days)
        self.assertIn("RISK", warning.message)

    def test_simulated_date_after_cutoff_is_not_at_risk(self):
        warning = check_knowledge_cutoff("gpt-4o", date(2025, 1, 1))
        self.assertFalse(warning.at_risk)
        self.assertEqual(warning.days_of_exposure, 0)
        self.assertIn("OK", warning.message)

    def test_simulated_date_equal_to_cutoff_is_not_at_risk(self):
        warning = check_knowledge_cutoff("gpt-4o", date(2023, 10, 1))
        self.assertFalse(warning.at_risk)

    def test_unknown_model_propagates(self):
        with self.assertRaises(UnknownModelError):
            check_knowledge_cutoff("not-a-real-model", date(2023, 1, 1))


if __name__ == "__main__":
    unittest.main()
