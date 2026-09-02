# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - ChronoGuard

"""chronoguard.stress_test — measure whether a trading decision actually
changes when the same prompt is replayed across a model's knowledge cutoff.

registry.check_knowledge_cutoff() flags risk from the calendar alone: "this
backtest date is before the model's cutoff, so contamination is possible."
It cannot tell you whether contamination actually happened.

run_stress_test() gets the empirical answer the registry check can't: call
the exact same decision function, with the exact same prompt and context,
once with an as-of date before the model's cutoff and once after — and
report whether the decision (or its score) moved. A model reasoning only
from what it's told should answer the same way regardless of which side of
its own training cutoff the simulated date falls on; a decision that flips
is direct, measured evidence of leakage through the weights, not a
theoretical concern.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class DecisionResult:
    """What a decision_fn must return: the decision itself, plus an
    optional numeric score (confidence, expected return, position size...)
    so a stress test can measure how far a decision moved, not just
    whether it moved at all."""

    decision: str
    score: Optional[float] = None
    raw: Any = None


DecisionFn = Callable[[str, dict, date], DecisionResult]


@dataclass(frozen=True)
class StressTestResult:
    model: str
    prompt: str
    pre_cutoff_date: date
    post_cutoff_date: date
    pre_result: DecisionResult
    post_result: DecisionResult
    decision_changed: bool
    score_delta: Optional[float]

    def summary(self) -> str:
        lines = [
            f"model:            {self.model}",
            f"pre-cutoff date:  {self.pre_cutoff_date.isoformat()} -> "
            f"decision: {self.pre_result.decision!r}"
            + (
                f" (score {self.pre_result.score})"
                if self.pre_result.score is not None
                else ""
            ),
            f"post-cutoff date: {self.post_cutoff_date.isoformat()} -> "
            f"decision: {self.post_result.decision!r}"
            + (
                f" (score {self.post_result.score})"
                if self.post_result.score is not None
                else ""
            ),
        ]
        if self.decision_changed:
            lines.append(
                "-> DECISION CHANGED: same prompt, same context, only the simulated "
                "date moved across the model's knowledge cutoff. This is measured "
                "evidence of temporal contamination, not a theoretical risk."
            )
        else:
            lines.append(
                "-> decision unchanged. No contamination detected on THIS prompt — "
                "this does not clear the model in general, only this one replay."
            )
        if self.score_delta is not None:
            lines.append(f"-> score delta: {self.score_delta:+.4f}")
        return "\n".join(lines)


def run_stress_test(
    decision_fn: DecisionFn,
    prompt: str,
    *,
    model: str,
    pre_cutoff_date: date,
    post_cutoff_date: date,
    context: Optional[dict] = None,
) -> StressTestResult:
    """Replay `decision_fn` on the same prompt/context at two simulated
    dates and report whether the decision moved.

    decision_fn(prompt, context, as_of_date) -> DecisionResult
        Your wrapper around the actual model call. It must actually use
        `as_of_date` (e.g. inject it into the prompt or a system message) —
        this function has no way to verify that it does; a wrapper that
        ignores the date will trivially agree on every replay and the test
        will report nothing.

    pre_cutoff_date / post_cutoff_date
        Two simulated "as of" dates for the same trading decision. For
        this to test contamination rather than something else, one should
        be before and one after the model's knowledge cutoff — pass them
        explicitly (e.g. from registry.get_cutoff(model).cutoff) rather
        than relying on this function to know the registry, since you may
        be testing a model, or a custom cutoff, that isn't in it.

    context
        Whatever else your decision_fn needs (price history, headlines,
        prior positions...). Passed through unchanged to both calls, so
        the only thing that differs between the two runs is the date.
    """
    if pre_cutoff_date >= post_cutoff_date:
        raise ValueError(
            f"pre_cutoff_date ({pre_cutoff_date.isoformat()}) must be strictly "
            f"before post_cutoff_date ({post_cutoff_date.isoformat()}) — otherwise "
            "the two replays aren't testing opposite sides of anything."
        )

    ctx = context or {}
    pre_result = decision_fn(prompt, ctx, pre_cutoff_date)
    post_result = decision_fn(prompt, ctx, post_cutoff_date)

    for label, result in (("pre_cutoff", pre_result), ("post_cutoff", post_result)):
        if not isinstance(result, DecisionResult):
            raise TypeError(
                f"decision_fn must return a DecisionResult, got "
                f"{type(result).__name__} for the {label} call. Wrap your model's "
                "output: DecisionResult(decision=..., score=...)."
            )

    decision_changed = pre_result.decision != post_result.decision
    score_delta = (
        post_result.score - pre_result.score
        if pre_result.score is not None and post_result.score is not None
        else None
    )

    return StressTestResult(
        model=model,
        prompt=prompt,
        pre_cutoff_date=pre_cutoff_date,
        post_cutoff_date=post_cutoff_date,
        pre_result=pre_result,
        post_result=post_result,
        decision_changed=decision_changed,
        score_delta=score_delta,
    )
