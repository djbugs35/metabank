#!/bin/sh
# Lance Wealthfolio (Docker) et ouvre le navigateur : double-clic dans le Finder, ou ./lancer.command.
#   ./lancer.command arreter      # arrête le conteneur (les données restent dans data/)
cd "$(dirname "$0")" || exit 1
PATH="/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Docker n'est pas lancé (ou pas installé). Ouvrir Docker Desktop, puis relancer."
  exit 1
fi
if [ "$1" = arreter ]; then
  exec docker compose down
fi
[ -f .env ] || ./outils/preparer_env.sh || exit 1
mkdir -p data
docker compose up -d || exit 1

ORIGINE=$(sed -n 's/^WF_CORS_ALLOW_ORIGINS=//p' .env)
echo "Wealthfolio : $ORIGINE"
(sleep 2 && open "$ORIGINE") &
