# Suggested commands (repo root, macOS; uv manages the venv)
- App: `./lancer.command` or `uv run python -m metabank web [--sans-ouvrir] [--port 8770]`.
- CLI: `uv run python -m metabank bilan | frais | tableau`.
- Tests: `uv run pytest -q` ; coverage: `uv run pytest -q --cov` (fails under 80 %).
- Lint/format: `uv run ruff check metabank tests` ; `uv run ruff format metabank tests`.
- Types: `uv run mypy` (zero errors tolerated).
- JS syntax: `for f in metabank/web/statique/*.js; do node --check "$f"; done`.
- API doc: `uv run pdoc metabank` (local server) or `uv run pdoc metabank -o docs/api` (ignored by git).
- PDF text: `pdftotext -layout file.pdf -` (poppler, `brew install poppler`).
- zsh: no trailing comments on command lines in docs.
