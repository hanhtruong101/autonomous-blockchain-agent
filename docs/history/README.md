# Historical verification

These reports describe the code, seed balances and environment at their recorded
dates. They are evidence of earlier runs, not current test results or startup instructions.
Evaluation/benchmark UI has since been removed, and the current seed is 500/500.

- [Initial verification](verification.md)
- [2026-10-11 verification](verification-2026-10-11.md)
- [AI trade verification, 2026-10-12](verification-ai-trades.md)
- [Provider integration history](ai-integration.md)

Use the [root README](../../README.md) and [demo](../demo.md) for current instructions.

## Cleanup verification — 2026-10-14

The retired HOLD/REBALANCE generator and benchmark-only prompt branches were
removed. Live generation uses AITradingAgent directly; historical metadata and
REBALANCE activity remain readable. Seed balances remain 500/500.

- Ordinary Python suite: 237 passed, 6 opt-in integrations skipped.
- Four real-Anvil suites passed separately on isolated port 18549, with fresh
  deployment for each: adapter/bypass, offline fixture flow, mocked-AI reverse
  swaps with approval, and scheduling/freeze/resume.
- Ruff lint/format and mypy (49 application/deployment source files) passed.
- PostgreSQL-specific integrations, Docker, live model calls and browser checks
  were not run in this cleanup. Contracts and UI were not changed.
- Two existing dependency deprecation warnings remain.

The interactive chain and application database were not reset.
