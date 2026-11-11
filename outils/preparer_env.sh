#!/bin/sh
# Crée .env pour Wealthfolio : clé secrète, empreinte Argon2id du mot de passe, origine autorisée.
# Le mot de passe n'est ni affiché ni écrit : seule son empreinte va dans .env (droits 600, ignoré par git).
#   ./outils/preparer_env.sh            # accès depuis cette machine (http://localhost:8088)
#   ./outils/preparer_env.sh reseau     # accès depuis le réseau local (NAS) : demande l'adresse
cd "$(dirname "$0")/.." || exit 1
PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ -f .env ]; then
  printf '.env existe déjà. Le remplacer (nouveau mot de passe, sessions coupées) ? [o/N] '
  read -r reponse
  case "$reponse" in o|O|oui) ;; *) echo "Rien n'a changé."; exit 0 ;; esac
fi

for outil in openssl argon2; do
  if ! command -v "$outil" >/dev/null 2>&1; then
    echo "Il manque « $outil ». Sur Mac : brew install $outil"
    exit 1
  fi
done

PORT=8088
BIND=127.0.0.1
ORIGINE="http://localhost:$PORT"
if [ "$1" = reseau ]; then
  printf "Adresse de cette machine sur le réseau (ex. 192.168.1.20) : "
  read -r adresse
  BIND=0.0.0.0
  ORIGINE="http://$adresse:$PORT"
fi

printf 'Mot de passe Wealthfolio (rien ne s affiche) : '
stty -echo; read -r mot_de_passe; stty echo; echo
printf 'Le retaper : '
stty -echo; read -r confirmation; stty echo; echo
if [ -z "$mot_de_passe" ] || [ "$mot_de_passe" != "$confirmation" ]; then
  echo "Mots de passe vides ou différents : recommencer."
  exit 1
fi

# Sel aléatoire de 16 caractères (argon2 en exige au moins 16).
SEL=$(openssl rand -hex 8)
EMPREINTE=$(printf '%s' "$mot_de_passe" | argon2 "$SEL" -id -e)
SECRET=$(openssl rand -base64 32)
unset mot_de_passe confirmation

umask 077
# Guillemets simples : docker compose interpréterait sinon les « $ » de l'empreinte Argon2id.
cat > .env <<FIN
WF_VERSION=latest
WF_PORT=$PORT
WF_BIND=$BIND
WF_CORS_ALLOW_ORIGINS=$ORIGINE
WF_SECRET_KEY='$SECRET'
WF_AUTH_PASSWORD_HASH='$EMPREINTE'
WF_REQUEST_TIMEOUT_MS=30000
FIN
chmod 600 .env
echo ".env créé. Adresse de Wealthfolio : $ORIGINE"
echo "Garder WF_SECRET_KEY : sans elle, les secrets enregistrés dans data/ deviennent illisibles."
