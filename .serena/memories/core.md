# metabank — core

Local, read-only household wealth tool (French): life insurance (assurance vie), PER/PERP, PEA, bank accounts,
savings books (Livret A, LDD), mortgages. Reads insurer PDF statements and bank CSV exports, computes returns/fees
with tested code, serves a local web app. Repo `djbugs35/metabank`; runs on the Mac (`./lancer.command`), NAS later.

## Source map
- `metabank/__main__.py` — CLI: `web` (app on 127.0.0.1:8770), `bilan`, `frais`, `tableau`.
- `metabank/releves/` — insurer statement readers: `suravenir.py` (annual PDF), `cardif.py` (situation PDF),
  `frais_supports.py` (fund fee table), `texte.py` (pdftotext, French amounts), `modele.py` (Releve, Support…).
- `metabank/bilan.py`, `synthese.py`, `frais.py`, `frais_historique.py` — per-contract and aggregate returns, fees.
- `metabank/banque/` — bank exports: `bnp.py` (CSV), `__init__.py` (read folders, merge exports, credits dir),
  `categories.py` (spending rules), `analyse.py` (budget, balances, livrets, regulated rates), `credit.py` (loans).
- `metabank/base/` — SQLite `data/metabank.db`, rebuilt from raw files in `data/archives/` only: `schema.py`
  (migrations via PRAGMA user_version), `archives.py`, `lot.py` (what a connector returns), `integration.py`
  (`importer_fichier`, `reconstruire`, `ouvrir_base`), `montants.py` (integer cents). User input stays in JSON files.
- `metabank/connecteurs/` — plug-ins: `contrat.py` (families fichier/direct/calcul/reference, `est_actif` = all
  settings filled), `registre.py` (auto-discovers modules exposing `CONNECTEUR`, `composer_lecteur`,
  `synchroniser_compte` principal then fallback). Journal: `metabank/base/journal.py`. Real connectors: `bnp_csv.py`,
  `suravenir_pdf.py`, `cardif_pdf.py` (shared `_releves.py`, `_provenance.py`; `_`-modules are not plug-ins).
- `metabank/base/lecture.py` — base back to domain objects (`lire_releves`, `lire_comptes_bancaires`), same figures
  as `releves.lire_dossier` / `banque.lire_comptes`. `metabank/archivage.py` + CLI `archiver` (copy old layout into
  archives, then compare), `reconstruire`.
- `metabank/corrections.py` — `data/corrections.json` (opening dates, verified payments, property values).
- `metabank/web/` — `serveur.py` (stdlib HTTP server, host/origin guard), `vues.py` (state JSON), `banque_vues.py`,
  `credits_vues.py`, `epargne.py`, `patrimoine.py`, `depot.py` (upload), `simulation.py`, `assistant.py` (`claude -p`,
  no tools, empty dir); `statique/` — vanilla JS pages (`app.js`, `rendu.js`, `graphiques.js`, `comptes.js`, `rapport.*`).
- `tests/` — pytest, fictitious fixtures in `tests/exemples/` only.
- Docs: `docs/PLAN.md` (roadmap, decisions), `docs/MODELE.md` (every formula, cited by § in code), `CLAUDE.md`.

## Invariants (never break)
- Read-only: no transfer, order or arbitrage, ever.
- `data/` (statements, exports, corrections, categories) is personal: never versioned, never copied into the repo,
  tests, commits, logs or prompts. No full account number or IBAN in outputs (masked `****1234`).
- Every figure comes from tested code; formula written in `docs/MODELE.md` first; the assistant comments, never computes.
- Amounts in `Decimal`; atomic file writes; the web server binds 127.0.0.1 and rejects foreign Host/Origin.
- No personalised investment advice: facts, comparisons and simulations only.

Further: stack/versions `mem:tech_stack`; commands `mem:suggested_commands`; style & naming `mem:conventions`;
done-checklist `mem:task_completion`.
