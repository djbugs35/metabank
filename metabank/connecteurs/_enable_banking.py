"""Client Enable Banking (DSP2), en lecture seule : jeton signé, accord du titulaire, comptes, soldes, opérations.

https://enablebanking.com/docs/api/quick-start/ : chaque appel porte un jeton JWT RS256 signé par la clé privée de
l'application (« kid » = identifiant de l'application), valable une heure. La signature passe par la commande openssl
(présente sur le Mac et le NAS) : aucune dépendance Python.

Secrets et accord, hors du dépôt et de data/ : ~/.config/metabank/enable_banking.pem (clé privée, téléchargée par le
navigateur à la création de l'application) et ~/.config/metabank/enable_banking.json (identifiant de l'application,
session, comptes autorisés), tous deux à droits 600. Aucun paiement : seules des lectures sont appelées.
"""

import base64
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

API = "https://api.enablebanking.com"
DOSSIER_SECRETS = Path("~/.config/metabank").expanduser()
CLE = DOSSIER_SECRETS / "enable_banking.pem"
ACCORD = DOSSIER_SECRETS / "enable_banking.json"
REDIRECTION = "https://localhost:8770/enable-banking/retour"
DUREE_JETON_S = 3600
DELAI_S = 30
PAGES_MAX = 50

# (méthode, adresse complète, en-têtes, corps JSON ou None) -> réponse JSON ; remplacée dans les tests (pas de réseau).
Transport = Callable[[str, str, dict, bytes | None], dict]


class EnableBankingIndisponible(RuntimeError):
    """Appel refusé ou impossible (réseau, accord expiré, clé absente) : le message dit quoi faire."""


def _base64url(donnees: bytes) -> str:
    return base64.urlsafe_b64encode(donnees).rstrip(b"=").decode()


def jeton(application: str, cle: Path = CLE, maintenant: int | None = None) -> str:
    """Rendre le jeton JWT RS256 d'une heure qui authentifie l'application auprès de l'API.

    Raises:
        EnableBankingIndisponible: clé privée ou openssl absents, signature impossible.
    """
    if not cle.exists():
        raise EnableBankingIndisponible(f"clé privée absente : rangez le .pem téléchargé dans {cle}")
    if shutil.which("openssl") is None:
        raise EnableBankingIndisponible("openssl absent")
    iat = int(time.time()) if maintenant is None else maintenant
    entete = {"typ": "JWT", "alg": "RS256", "kid": application}
    charge = {"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": iat, "exp": iat + DUREE_JETON_S}
    signe = f"{_base64url(json.dumps(entete).encode())}.{_base64url(json.dumps(charge).encode())}"
    resultat = subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(cle)], input=signe.encode(),
                              capture_output=True, check=False)  # fmt: skip
    if resultat.returncode != 0:
        raise EnableBankingIndisponible("signature du jeton impossible : la clé privée est-elle la bonne ?")
    return f"{signe}.{_base64url(resultat.stdout)}"


def _transport_reseau(methode: str, adresse: str, entetes: dict, corps: bytes | None) -> dict:
    requete = urllib.request.Request(adresse, data=corps, headers=entetes, method=methode)
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_S) as reponse:
            return json.loads(reponse.read() or b"{}")
    except urllib.error.HTTPError as erreur:
        detail = erreur.read().decode(errors="replace")[:300]
        raise EnableBankingIndisponible(f"Enable Banking a refusé l'appel ({erreur.code}) : {detail}") from erreur
    except (urllib.error.URLError, TimeoutError) as erreur:
        raise EnableBankingIndisponible(f"Enable Banking injoignable : {erreur}") from erreur


class Client:
    """Les appels de lecture à l'API, pour une application donnée."""

    def __init__(self, application: str, cle: Path = CLE, transport: Transport = _transport_reseau) -> None:
        self.application, self.cle, self.transport = application, cle, transport

    def _appeler(self, methode: str, chemin: str, corps: dict | None = None) -> dict:
        entetes = {"Authorization": f"Bearer {jeton(self.application, self.cle)}", "Content-Type": "application/json"}
        donnees = None if corps is None else json.dumps(corps).encode()
        return self.transport(methode, f"{API}{chemin}", entetes, donnees)

    def banques(self, pays: str = "FR") -> list[dict]:
        """Rendre les banques du pays (« aspsps ») : nom exact à donner pour l'accord."""
        return self._appeler("GET", f"/aspsps?{urlencode({'country': pays})}").get("aspsps", [])

    def demander_accord(self, banque: str, pays: str, jours: int, etat: str, retour: str = REDIRECTION) -> str:
        """Rendre l'adresse où le titulaire donne son accord, pour jours de lecture de ses comptes.

        Args:
            retour: adresse de retour, identique caractère pour caractère à celle déclarée dans l'application.
        """
        fin = (datetime.now(tz=UTC) + timedelta(days=jours)).isoformat(timespec="seconds")
        corps = {"access": {"valid_until": fin}, "aspsp": {"name": banque, "country": pays}, "state": etat,
                 "redirect_url": retour, "psu_type": "personal"}  # fmt: skip
        return str(self._appeler("POST", "/auth", corps)["url"])

    def ouvrir_session(self, code: str) -> dict:
        """Rendre la session ouverte par le code de retour : identifiant, comptes autorisés, fin de l'accord."""
        return self._appeler("POST", "/sessions", {"code": code})

    def soldes(self, compte: str) -> list[dict]:
        """Rendre les soldes du compte (uid de la session)."""
        return self._appeler("GET", f"/accounts/{compte}/balances").get("balances", [])

    def operations(self, compte: str, depuis: date) -> list[dict]:
        """Rendre les opérations du compte depuis la date, toutes pages comprises."""
        operations: list[dict] = []
        suite = ""
        for _ in range(PAGES_MAX):
            parametres = {"date_from": depuis.isoformat(), **({"continuation_key": suite} if suite else {})}
            page = self._appeler("GET", f"/accounts/{compte}/transactions?{urlencode(parametres)}")
            operations += page.get("transactions", [])
            suite = page.get("continuation_key") or ""
            if not suite:
                return operations
        raise EnableBankingIndisponible("trop de pages d'opérations : réduisez la période demandée")


def code_de_retour(adresse: str) -> str:
    """Rendre le code d'autorisation de l'adresse où la banque a renvoyé le navigateur.

    Raises:
        ValueError: adresse sans code (accord refusé ou adresse incomplète).
    """
    parametres = parse_qs(urlsplit(adresse.strip()).query)
    if "error" in parametres:
        raise ValueError(f"accord refusé par la banque : {parametres['error'][0]}")
    if "code" not in parametres:
        raise ValueError("adresse sans code : copiez toute l'adresse de la page d'arrivée")
    return parametres["code"][0]


def lire_accord(chemin: Path = ACCORD) -> dict:
    """Rendre l'accord enregistré (application, session, comptes), ou {} s'il n'y en a pas."""
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def enregistrer_accord(accord: dict, chemin: Path = ACCORD) -> None:
    """Écrire l'accord atomiquement, lisible par le seul titulaire (droits 600)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(".json.tmp")
    descripteur = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
        json.dump(accord, fichier, ensure_ascii=False, indent=2)
    temporaire.replace(chemin)


def masquer_iban(iban: str) -> str:
    """Rendre « ****1234 » : les 4 derniers chiffres du numéro de compte, comme l'export BNP.

    Un IBAN français finit par le numéro de compte (11 caractères) puis la clé RIB (2 chiffres).
    """
    compact = iban.replace(" ", "")
    return "****" + compact[-6:-2] if len(compact) >= 6 else ""
