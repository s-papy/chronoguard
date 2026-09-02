"""Runnable demo of both chronoguard features against a mock LLM.

No API key required — `mock_llm_decision` stands in for a real model call
so this demo (and the README's example output) reproduce deterministically.
Swap it for a real call to your model provider to test the real thing.
"""

from datetime import date

from chronoguard import (
    DecisionResult,
    check_knowledge_cutoff,
    get_cutoff,
    run_stress_test,
)


def mock_llm_decision(prompt: str, context: dict, as_of_date: date) -> DecisionResult:
    """Stands in for a real LLM call. Simulates a model that memorized a
    2024-03-01 market crash during pretraining and lets it leak into any
    decision dated before the crash but after the model's own cutoff logic
    would allow it to 'know' — the exact shape of the bug in issue #805."""
    pretrain_leak_starts = date(2023, 6, 1)
    crash_date = date(2024, 3, 1)
    if pretrain_leak_starts <= as_of_date < crash_date:
        return DecisionResult(decision="SELL", score=-0.72, raw="model recalls a crash it shouldn't know about yet")
    return DecisionResult(decision="BUY", score=0.55, raw="no future knowledge available")


def main() -> None:
    print("=== 1. Knowledge-cutoff registry check ===\n")
    model = "gpt-4o"
    simulated_backtest_date = date(2023, 6, 1)
    warning = check_knowledge_cutoff(model, simulated_backtest_date)
    print(warning.message)
    print()

    print("=== 2. Empirical stress test ===\n")
    cutoff = get_cutoff(model).cutoff
    result = run_stress_test(
        mock_llm_decision,
        prompt="Given current conditions, should we buy or sell AAPL?",
        model=model,
        pre_cutoff_date=date(2023, 9, 1),
        post_cutoff_date=date(2024, 6, 1),
        context={"symbol": "AAPL"},
    )
    print(f"(model's registered knowledge cutoff: {cutoff.isoformat()})\n")
    print(result.summary())


if __name__ == "__main__":
    main()
