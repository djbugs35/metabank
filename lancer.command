#!/bin/sh
# Lance l'application metabank et l'ouvre dans le navigateur : double-clic dans le Finder, ou ./lancer.command.
# Elle tourne sur ce Mac seulement (http://127.0.0.1:8770) ; fermer cette fenêtre l'arrête.
cd "$(dirname "$0")" || exit 1
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv n'est pas installé : brew install uv, puis relancer."
  exit 1
fi
if ! command -v pdftotext >/dev/null 2>&1; then
  echo "pdftotext n'est pas installé : brew install poppler, puis relancer."
  exit 1
fi
exec uv run python -m metabank web
