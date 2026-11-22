# Conventions (full text: CLAUDE.md § Conventions; shared rules: metascrap docs/CONVENTIONS.md)
- Domain identifiers in French, no accents in Python identifiers: `verbe_complement()`, predicates `est_x()`, `_prive`,
  `MAJUSCULES` consts. Booleans named by what they assert. No abbreviations outside the domain.
- Comments, docstrings, commit messages and UI text in French (accents allowed); comments explain WHY, never what.
- Docstrings: Google style; first line = what it returns, infinitive ("Rendre …"); then only the non-obvious, with unit
  of each quantity (euros, fraction, points). Every public function.
- Size: functions <=50 lines, >80 refused on new code; module >800 lines to split. ruff: max-complexity 12,
  max-statements 60, max-branches 15, max-args 6. Line length 120, double quotes (like cap-prepa, egide).
- Errors: catch the type you handle; no `except Exception` outside a logged boundary.
- Tests: one test per behaviour, named by the guarantee; no network, no real data (fixtures in `tests/exemples/`).
- Formulas: `docs/MODELE.md` § first, code cites the §.
- Git: conventional commits, French subject (`feat: …`, `fix: …`, `docs: …`, `chore: …`).
