#!/bin/sh
# Installe metabank : double-clic dans le Finder (macOS) ou ./installer.command. Peut être relancé sans risque.
cd "$(dirname "$0")" || exit 1

pause_finale() {
  if [ -t 0 ]; then
    printf '\nAppuyer sur Entrée pour fermer. '
    read -r _
  fi
}

# Un double-clic dans le Finder ne reçoit pas le PATH du terminal : uv peut être dans ~/.local/bin ou Homebrew.
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installation de uv (gestionnaire Python)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh || { echo "Échec de l'installation de uv."; pause_finale; exit 1; }
  PATH="$HOME/.local/bin:$PATH"
fi

echo "Dépendances…"
uv sync || { pause_finale; exit 1; }

echo "Modules woob…"
uv run woob config update || { echo "Échec : vérifier la connexion internet."; pause_finale; exit 1; }

if uv run woob config list 2>/dev/null | grep -q bnporc; then
  echo "Accès BNP déjà déclaré (backend bnporc)."
else
  printf 'Déclarer maintenant votre accès BNP (identifiant, mot de passe, site « pp ») ? [o/N] '
  read -r reponse
  case "$reponse" in o|O|oui) uv run woob config add bnporc ;; esac
fi

# woob range les mots de passe dans ce fichier : il ne doit être lisible que par vous.
FICHIER_BACKENDS="${XDG_CONFIG_HOME:-$HOME/.config}/woob/backends"
[ -f "$FICHIER_BACKENDS" ] && chmod 600 "$FICHIER_BACKENDS"

echo
echo "Prêt. Premier inventaire : uv run python -m metabank inventaire --interactif"
pause_finale
