# Task completion
1. `uv run ruff check metabank tests` and `uv run ruff format metabank tests`.
2. `uv run mypy` — zero errors.
3. `uv run pytest -q --cov` — all green, coverage >= 80 %.
4. JS touched: `node --check` on each `metabank/web/statique/*.js`; UI change: check the page with fictitious data
   (never screenshots of real data in the repo or the conversation).
5. New formula: `docs/MODELE.md` § first. New suggestion: `docs/PLAN.md` § Suggestions retenues.
6. README only when a version tag is set. Conventional commit in French; never commit `data/`.
