# chronoguard

Detect **temporal contamination** — an LLM trading agent "hallucinating"
knowledge of the future because it was already there at pretraining time,
not because the backtest leaked any data — in a backtest or hackathon
submission before you ship it.

## The problem

A backtest can slice its *data* perfectly by simulated date — no candle,
headline, or filing dated after "now" ever reaches the agent — and still
leak the future, because the LLM doing the reasoning was pretrained on a
corpus frozen at some knowledge-cutoff date. Anything the model memorized
from before that cutoff is available to it even when the backtest's
simulated clock says the event hasn't happened yet.

That's a different bug from the classic data look-ahead bias that tools
like backtesting frameworks already guard against: the data was never
stale or wrong, it just isn't the only channel the future can leak
through. [TauricResearch/TradingAgents#805](https://github.com/TauricResearch/TradingAgents/issues/805)
describes exactly this failure mode for LLM trading agents — a real,
currently open, unanswered issue. There is no existing free, developer-facing,
standalone tool that checks specifically for it. chronoguard is a first
attempt: a static registry of model knowledge cutoffs, plus an empirical
stress test that actually measures whether a decision moves across one.

## Install

```bash
git clone <this-repo-url>
cd chronoguard
pip install -e .
```

No third-party dependencies — standard library only.

## Usage

### 1. Registry check: is this backtest date even at risk?

```python
from datetime import date
from chronoguard import check_knowledge_cutoff

warning = check_knowledge_cutoff("gpt-4o", simulated_date=date(2023, 6, 1))
print(warning.message)
print(warning.at_risk)  # True — the backtest date is before gpt-4o's cutoff
```

`check_knowledge_cutoff(model, simulated_date)` looks up `model` in a
static registry (`chronoguard.registry.KNOWLEDGE_CUTOFFS`) and flags risk
when `simulated_date` falls before that model's documented knowledge
cutoff — i.e. the model may already "know" about events in between. This is
a calendar-only check: it tells you the risk is *possible*, not that it
*happened*. Unknown models raise `UnknownModelError` listing what's
registered; add rows to the registry as you need them, and verify dates
against the vendor's own model page — they're maintained by hand and go
stale as new models ship.

### 2. Empirical stress test: did it actually happen?

```python
from datetime import date
from chronoguard import DecisionResult, run_stress_test

def my_decision_fn(prompt, context, as_of_date):
    # Wrap your real model call here — inject as_of_date into the prompt
    # or system message so the model actually sees which "now" it's at.
    response = call_my_llm(prompt, context, as_of_date)
    return DecisionResult(decision=response.action, score=response.confidence)

result = run_stress_test(
    my_decision_fn,
    prompt="Given current conditions, should we buy or sell AAPL?",
    model="gpt-4o",
    pre_cutoff_date=date(2023, 9, 1),   # before the model's cutoff
    post_cutoff_date=date(2024, 6, 1),  # after it
    context={"symbol": "AAPL"},
)
print(result.summary())
print(result.decision_changed)  # True/False
```

`run_stress_test` replays the exact same prompt and context through your
`decision_fn` at two simulated dates straddling a model's knowledge cutoff,
and reports whether the decision (and optionally its score) changed. A
model reasoning only from what it's told should answer the same way on
both sides; a decision that flips is measured evidence of contamination on
that specific prompt — not a theoretical risk.

## Example output

Running [`examples/demo.py`](examples/demo.py) (a mock LLM stands in for a
real model call, so this reproduces deterministically without an API key):

```
=== 1. Knowledge-cutoff registry check ===

RISK: gpt-4o's knowledge cutoff (2023-10-01) is 122 day(s) after the backtest's simulated date (2023-06-01). The model may already 'know' things that happen in that window, which the backtest treats as unknowable future. (documented cutoff, source: OpenAI model docs)

=== 2. Empirical stress test ===

(model's registered knowledge cutoff: 2023-10-01)

model:            gpt-4o
pre-cutoff date:  2023-09-01 -> decision: 'SELL' (score -0.72)
post-cutoff date: 2024-06-01 -> decision: 'BUY' (score 0.55)
-> DECISION CHANGED: same prompt, same context, only the simulated date moved across the model's knowledge cutoff. This is measured evidence of temporal contamination, not a theoretical risk.
-> score delta: +1.2700
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The stress-test suite mocks `decision_fn` — no LLM API calls or API keys
are needed to verify the logic.

## Status

Early. The knowledge-cutoff registry (`chronoguard/registry.py`) is a
hand-maintained table, not a live feed — check entries against the
vendor's own docs before relying on one. Contributions adding models or
tightening dates are welcome.

## License

MIT — see [LICENSE](LICENSE).
