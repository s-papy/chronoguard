import unittest
from datetime import date
from unittest.mock import MagicMock

from chronoguard.stress_test import DecisionResult, run_stress_test


def _contaminated_decision_fn(prompt, context, as_of_date):
    """Simulates a model that 'knows' about a crash on 2024-03-01 even when
    asked to decide as of a date before the crash — the exact failure mode
    chronoguard exists to catch."""
    knows_about_crash = as_of_date >= date(2023, 1, 1)  # leaks knowledge early
    if knows_about_crash and as_of_date < date(2024, 3, 1):
        return DecisionResult(decision="SELL", score=-0.8)
    return DecisionResult(decision="BUY", score=0.6)


def _clean_decision_fn(prompt, context, as_of_date):
    """Simulates a model whose decision genuinely does not depend on
    information from beyond as_of_date."""
    return DecisionResult(decision="BUY", score=0.5)


class TestRunStressTest(unittest.TestCase):
    def test_detects_decision_change_across_cutoff(self):
        result = run_stress_test(
            _contaminated_decision_fn,
            "Should we buy AAPL?",
            model="mock-contaminated",
            pre_cutoff_date=date(2023, 6, 1),
            post_cutoff_date=date(2024, 6, 1),
        )
        self.assertTrue(result.decision_changed)
        self.assertEqual(result.pre_result.decision, "SELL")
        self.assertEqual(result.post_result.decision, "BUY")
        self.assertAlmostEqual(result.score_delta, 0.6 - (-0.8))
        self.assertIn("DECISION CHANGED", result.summary())

    def test_no_change_for_a_clean_decision_fn(self):
        result = run_stress_test(
            _clean_decision_fn,
            "Should we buy AAPL?",
            model="mock-clean",
            pre_cutoff_date=date(2023, 6, 1),
            post_cutoff_date=date(2024, 6, 1),
        )
        self.assertFalse(result.decision_changed)
        self.assertAlmostEqual(result.score_delta, 0.0)
        self.assertIn("decision unchanged", result.summary())

    def test_calls_decision_fn_exactly_twice_with_correct_dates(self):
        mock_fn = MagicMock(return_value=DecisionResult(decision="HOLD", score=0.0))
        pre = date(2023, 1, 1)
        post = date(2024, 1, 1)
        run_stress_test(
            mock_fn,
            "prompt",
            model="mock",
            pre_cutoff_date=pre,
            post_cutoff_date=post,
            context={"symbol": "AAPL"},
        )
        self.assertEqual(mock_fn.call_count, 2)
        mock_fn.assert_any_call("prompt", {"symbol": "AAPL"}, pre)
        mock_fn.assert_any_call("prompt", {"symbol": "AAPL"}, post)

    def test_rejects_pre_date_not_before_post_date(self):
        with self.assertRaises(ValueError):
            run_stress_test(
                _clean_decision_fn,
                "prompt",
                model="mock",
                pre_cutoff_date=date(2024, 1, 1),
                post_cutoff_date=date(2023, 1, 1),
            )

    def test_rejects_non_decision_result_return_value(self):
        bad_fn = lambda prompt, context, as_of_date: "BUY"  # noqa: E731
        with self.assertRaises(TypeError):
            run_stress_test(
                bad_fn,
                "prompt",
                model="mock",
                pre_cutoff_date=date(2023, 1, 1),
                post_cutoff_date=date(2024, 1, 1),
            )

    def test_score_delta_is_none_when_scores_missing(self):
        def no_score_fn(prompt, context, as_of_date):
            return DecisionResult(decision="BUY", score=None)

        result = run_stress_test(
            no_score_fn,
            "prompt",
            model="mock",
            pre_cutoff_date=date(2023, 1, 1),
            post_cutoff_date=date(2024, 1, 1),
        )
        self.assertIsNone(result.score_delta)


if __name__ == "__main__":
    unittest.main()
