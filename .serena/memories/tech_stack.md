# Tech stack
- Python >= 3.12 (ruff `target-version = py312`, the NAS version). uv for venv and lock (`uv.lock` pins versions).
- No runtime Python dependency. PDF text through `pdftotext` (poppler, external binary).
- Dev group: pytest, pytest-cov, ruff, mypy, pdoc (see `pyproject.toml`, locked in `uv.lock`).
- Web: stdlib `http.server` (ThreadingHTTPServer) + vanilla ES modules, inline SVG charts, no CDN, CSP self.
- Storage today: files in `data/` parsed at each start (cached by mtime); planned: SQLite `data/metabank.db`
  rebuilt from `data/archives/` (docs/PLAN.md, étape 1).
- Assistant: Claude Code CLI `claude -p` (no tools, temp dir). Planned: local MCP server, Enable Banking (DSP2).
- CI: `.github/workflows/tests.yml` (ruff, mypy, pytest --cov, node --check).
