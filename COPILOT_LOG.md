# GitHub Copilot log

Rule: write ONLY what really happened. Judges read this. Add an entry every time you use Copilot.

| Time | Who | Task | Prompt we typed | What Copilot produced | What we changed |
|------|-----|------|-----------------|-----------------------|-----------------|
|      |     |      |                 |                       |                 |

## Starter code disclosure
The starter skeleton in guard/ (models, parsers, resolver with MockRegistry, heuristics, verdict,
explain, cli) was drafted with Claude before the build started, then reviewed by the team.
GitHub Copilot use is listed ONLY in the table rows above. If a task has no row, Copilot was not used for it.

- Live npm/PyPI registries (resolver.py) and the Phase 3 extra fixtures plus fixtures test (extra_registry.json, extra-app, tests/test_extra_fixtures.py) were written with Claude and tested by the team. GitHub Copilot was NOT used for these.

- The pytest suite in tests/ (47 tests) was written with Claude and run by the team. GitHub Copilot was NOT used for it.
