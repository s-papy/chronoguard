# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - ChronoGuard

"""chronoguard.registry — known LLM knowledge-cutoff dates, and the check
that flags temporal contamination risk in a trading-agent backtest.

The failure this catches: a backtest can slice its *data* perfectly by
date — no candle, headline, or filing dated after the simulated "now" ever
reaches the agent — and still leak the future, because the LLM itself was
pretrained on a corpus frozen at some cutoff date. Anything the model
memorized from before that cutoff is available to it even when the
backtest's simulated clock says the event hasn't happened yet. That is a
different bug from data look-ahead, and no amount of careful data slicing
fixes it. See TauricResearch/TradingAgents#805 for the report that named it
"temporal contamination at the weight level".

check_knowledge_cutoff() does the one useful mechanical thing a static
registry can do: look up the model's documented cutoff and say whether the
backtest's simulated date sits before it. It cannot tell you whether
contamination actually *influenced* a given decision — that needs the
empirical replay in stress_test.py.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ModelCutoff:
    """One registry entry: a model's documented knowledge cutoff.

    `confidence` distinguishes a date the vendor states outright
    ("documented") from one inferred from release notes, benchmarks, or
    community reporting ("approximate") — treat the latter as a starting
    point, not a guarantee, and verify against the vendor's own model page
    before relying on it for anything consequential.
    """

    model: str
    cutoff: date
    source: str
    confidence: str  # "documented" | "approximate"


# Dates below reflect vendor-published documentation as of 2026-09. Model
# providers revise, clarify, or backdate these after release, and new
# models ship faster than any static table can track. Treat this as a
# starting point you maintain, not a live feed: re-check the vendor's model
# page before trusting an entry for anything consequential, and add rows as
# you need them — the keys are free-form strings, lowercased on lookup.
KNOWLEDGE_CUTOFFS: dict[str, ModelCutoff] = {
    "gpt-3.5-turbo": ModelCutoff(
        "gpt-3.5-turbo", date(2021, 9, 1), "OpenAI model docs", "documented"
    ),
    "gpt-4": ModelCutoff(
        "gpt-4", date(2021, 9, 1), "OpenAI model docs", "documented"
    ),
    "gpt-4-turbo": ModelCutoff(
        "gpt-4-turbo", date(2023, 12, 1), "OpenAI model docs", "documented"
    ),
    "gpt-4o": ModelCutoff(
        "gpt-4o", date(2023, 10, 1), "OpenAI model docs", "documented"
    ),
    "gpt-4o-mini": ModelCutoff(
        "gpt-4o-mini", date(2023, 10, 1), "OpenAI model docs", "documented"
    ),
    "o1": ModelCutoff(
        "o1", date(2023, 10, 1), "OpenAI model docs", "documented"
    ),
    "o3-mini": ModelCutoff(
        "o3-mini", date(2023, 10, 1), "OpenAI model docs", "documented"
    ),
    "claude-3-haiku": ModelCutoff(
        "claude-3-haiku", date(2023, 8, 1), "Anthropic model docs", "documented"
    ),
    "claude-3-sonnet": ModelCutoff(
        "claude-3-sonnet", date(2023, 8, 1), "Anthropic model docs", "documented"
    ),
    "claude-3-opus": ModelCutoff(
        "claude-3-opus", date(2023, 8, 1), "Anthropic model docs", "documented"
    ),
    "claude-3-5-sonnet": ModelCutoff(
        "claude-3-5-sonnet", date(2024, 4, 1), "Anthropic model docs", "documented"
    ),
    "claude-3-5-haiku": ModelCutoff(
        "claude-3-5-haiku", date(2024, 7, 1), "Anthropic model docs", "documented"
    ),
    "claude-3-7-sonnet": ModelCutoff(
        "claude-3-7-sonnet", date(2024, 11, 1), "Anthropic model docs", "approximate"
    ),
    "gemini-1.5-pro": ModelCutoff(
        "gemini-1.5-pro", date(2023, 11, 1), "Google model docs", "documented"
    ),
    "gemini-1.5-flash": ModelCutoff(
        "gemini-1.5-flash", date(2023, 11, 1), "Google model docs", "documented"
    ),
    "gemini-2.0-flash": ModelCutoff(
        "gemini-2.0-flash", date(2024, 8, 1), "Google model docs", "approximate"
    ),
    "llama-3-70b": ModelCutoff(
        "llama-3-70b", date(2023, 12, 1), "Meta model card", "documented"
    ),
    "llama-3.1-70b": ModelCutoff(
        "llama-3.1-70b", date(2023, 12, 1), "Meta model card", "documented"
    ),
    "llama-3.1-405b": ModelCutoff(
        "llama-3.1-405b", date(2023, 12, 1), "Meta model card", "documented"
    ),
    "mistral-large": ModelCutoff(
        "mistral-large", date(2024, 1, 1), "Mistral community reporting", "approximate"
    ),
}


class UnknownModelError(KeyError):
    """Raised when `model` has no registry entry. Lists what does, and how
    to add one — an unknown model is a missing row, not a dead end."""


def get_cutoff(model: str) -> ModelCutoff:
    """Look up a model's registry entry (case-insensitive)."""
    key = model.strip().lower()
    try:
        return KNOWLEDGE_CUTOFFS[key]
    except KeyError:
        known = ", ".join(sorted(KNOWLEDGE_CUTOFFS))
        raise UnknownModelError(
            f"no knowledge-cutoff entry for {model!r}. Known models: {known}. "
            "Add it to KNOWLEDGE_CUTOFFS in chronoguard/registry.py if you need it."
        ) from None


@dataclass(frozen=True)
class ContaminationWarning:
    """Result of a registry-only contamination check. `at_risk=True` is a
    possibility flagged from the calendar alone — pair it with
    stress_test.run_stress_test() for measured evidence, not just risk."""

    model: str
    simulated_date: date
    cutoff_date: date
    at_risk: bool
    days_of_exposure: int
    confidence: str
    message: str


def check_knowledge_cutoff(model: str, simulated_date: date) -> ContaminationWarning:
    """Compare a backtest's simulated date against `model`'s knowledge cutoff.

    at_risk=True means simulated_date is BEFORE the cutoff: the model's
    pretraining already encodes whatever happened between simulated_date
    and the cutoff — a window the backtest is supposed to treat as unknown
    future. This is a static, registry-only check: it flags the
    *possibility* of contamination from the calendar alone, and says
    nothing about whether contamination actually shaped any specific
    decision. For that, run stress_test.run_stress_test().
    """
    entry = get_cutoff(model)
    at_risk = simulated_date < entry.cutoff
    exposure = (entry.cutoff - simulated_date).days if at_risk else 0

    if at_risk:
        message = (
            f"RISK: {entry.model}'s knowledge cutoff ({entry.cutoff.isoformat()}) is "
            f"{exposure} day(s) after the backtest's simulated date "
            f"({simulated_date.isoformat()}). The model may already 'know' things "
            f"that happen in that window, which the backtest treats as unknowable "
            f"future. ({entry.confidence} cutoff, source: {entry.source})"
        )
    else:
        message = (
            f"OK: simulated date ({simulated_date.isoformat()}) is on or after "
            f"{entry.model}'s knowledge cutoff ({entry.cutoff.isoformat()}); the "
            f"calendar alone gives no reason to suspect contamination. "
            f"({entry.confidence} cutoff, source: {entry.source})"
        )

    return ContaminationWarning(
        model=entry.model,
        simulated_date=simulated_date,
        cutoff_date=entry.cutoff,
        at_risk=at_risk,
        days_of_exposure=exposure,
        confidence=entry.confidence,
        message=message,
    )
