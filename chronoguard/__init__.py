# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - ChronoGuard

"""chronoguard — catch temporal contamination in LLM trading-agent backtests.

See TauricResearch/TradingAgents#805: even a backtest with perfectly
date-sliced data can leak the future through the model itself, because an
LLM's pretraining corpus is frozen at some knowledge-cutoff date. Two tools:

- registry.check_knowledge_cutoff(model, simulated_date) — static risk flag
  from a model/cutoff registry.
- stress_test.run_stress_test(decision_fn, prompt, ...) — empirical replay
  that measures whether a decision actually changes across the cutoff.
"""

from .registry import (
    KNOWLEDGE_CUTOFFS,
    ContaminationWarning,
    ModelCutoff,
    UnknownModelError,
    check_knowledge_cutoff,
    get_cutoff,
)
from .stress_test import (
    DecisionResult,
    StressTestResult,
    run_stress_test,
)

__all__ = [
    "KNOWLEDGE_CUTOFFS",
    "ModelCutoff",
    "ContaminationWarning",
    "UnknownModelError",
    "check_knowledge_cutoff",
    "get_cutoff",
    "DecisionResult",
    "StressTestResult",
    "run_stress_test",
]

__version__ = "0.1.0"
