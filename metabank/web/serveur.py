"""Serveur de l'application : la page, et une petite API JSON au-dessus des fonctions de metabank.

DEUX BARRIÈRES, ET UNE SEULE EST UNE GARANTIE (comme Passerelle dans metascrap)
  1. L'écoute sur 127.0.0.1 : aucune autre machine ne joint le serveur. C'est la vraie protection.
  2. Les en-têtes : une requête dont l'hôte ou l'origine n'est pas cette adresse est refusée. Elle empêche une page
     web ouverte dans le même navigateur d'appeler l'API (DNS rebinding, formulaire caché) : l'API écrit dans data/
     et lance Claude Code, elle ne doit répondre qu'à sa propre page.
"""

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from metabank.configuration import lire_configuration
from metabank.corrections import CorrectionInvalide, ecrire_corrections
from metabank.depot_unique import dossier_depot
from metabank.web.assistant import AssistantIndisponible, contexte, demander, trouver_claude
from metabank.web.configuration_vues import enregistrer_configuration, etat_configuration
from metabank.web.depot import DepotRefuse, deposer_releve
from metabank.web.simulation import SimulationInvalide, simuler
from metabank.web.synoptique_vues import etat_synoptique
from metabank.web.vues import etat

ADRESSE = "127.0.0.1"
PORT_DEFAUT = 8770
STATIQUE = Path(__file__).resolve().parent / "statique"
FICHIERS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/graphiques.js": ("graphiques.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/rendu.js": ("rendu.js", "text/javascript; charset=utf-8"),
    "/comptes.js": ("comptes.js", "text/javascript; charset=utf-8"),
    "/configuration.js": ("configuration.js", "text/javascript; charset=utf-8"),
    "/synoptique.js": ("synoptique.js", "text/javascript; charset=utf-8"),
    "/rapport": ("rapport.html", "text/html; charset=utf-8"),
    "/rapport.js": ("rapport.js", "text/javascript; charset=utf-8"),
    "/rapport.css": ("rapport.css", "text/css; charset=utf-8"),
}
CORPS_MAX = 25 * 1024 * 1024


class EtatEnCache:
    """Calcule l'état une fois, et à nouveau seulement si un PDF ou corrections.json a changé (lire les PDF prend
    une à deux secondes)."""

    def __init__(self, dossier: Path) -> None:
        self.dossier = dossier
        self._verrou = threading.Lock()
        self._signature: tuple | None = None
        self._etat: dict | None = None

    def lire(self) -> dict:
        """Rendre l'état à jour des fichiers de data/."""
        with self._verrou:
            signature = self._signature_fichiers()
            if signature != self._signature or self._etat is None:
                self._etat, self._signature = etat(self.dossier), signature
            return self._etat

    def _signature_fichiers(self) -> tuple:
        fichiers = [
            *self.dossier.glob("*/*/**/*.pdf"),
            *self.dossier.glob("*/*/**/*.csv"),
            self.dossier / "corrections.json",
            self.dossier / "categories.json",
            self.dossier / "configuration.json",
            *dossier_depot(self.dossier, lire_configuration(self.dossier)).glob("*.*"),
        ]
        return tuple(sorted((str(f), f.stat().st_mtime_ns) for f in fichiers if f.exists()))


def creer_serveur(dossier: Path, port: int = PORT_DEFAUT) -> ThreadingHTTPServer:
    """Rendre le serveur prêt à tourner, lié à 127.0.0.1 ; port 0 = un port libre (tests)."""
    cache = EtatEnCache(dossier)

    class Gestionnaire(_Gestionnaire):
        pass

    Gestionnaire.cache = cache
    serveur = ThreadingHTTPServer((ADRESSE, port), Gestionnaire)
    Gestionnaire.hotes = {f"{ADRESSE}:{serveur.server_port}", f"localhost:{serveur.server_port}"}
    return serveur


def _assistant_actif(dossier: Path) -> bool:
    return bool(lire_configuration(dossier)["parametres"]["assistant_actif"])


class _Gestionnaire(BaseHTTPRequestHandler):
    cache: EtatEnCache
    hotes: set[str]

    def log_message(self, format: str, *args) -> None:
        """Ne rien journaliser : les URL et réponses peuvent contenir des montants."""

    def do_GET(self) -> None:
        """Servir la page, le rapport à enregistrer en PDF, l'état ou le texte envoyé à Claude."""
        if not self._requete_sure():
            return
        chemin = urlsplit(self.path).path
        if chemin in FICHIERS:
            nom, type_ = FICHIERS[chemin]
            self._envoyer(HTTPStatus.OK, (STATIQUE / nom).read_bytes(), type_)
        elif chemin == "/api/etat":
            disponible = _assistant_actif(self.cache.dossier) and trouver_claude() is not None
            self._json(HTTPStatus.OK, {**self.cache.lire(), "assistant_disponible": disponible})
        elif chemin == "/api/configuration":
            self._json(HTTPStatus.OK, etat_configuration(self.cache.dossier))
        elif chemin == "/api/synoptique":
            self._json(HTTPStatus.OK, etat_synoptique(self.cache.dossier))
        elif chemin == "/api/assistant/contexte":
            self._envoyer(HTTPStatus.OK, contexte(self.cache.lire()).encode(), "text/plain; charset=utf-8")
        else:
            self._json(HTTPStatus.NOT_FOUND, {"erreur": "introuvable"})

    def do_POST(self) -> None:
        """Déposer un relevé, enregistrer les corrections ou la configuration, simuler, interroger Claude."""
        if not self._requete_sure():
            return
        longueur = int(self.headers.get("Content-Length") or 0)
        if longueur > CORPS_MAX:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"erreur": "fichier trop gros"})
            return
        corps = self.rfile.read(longueur)
        try:
            self._json(HTTPStatus.OK, self._traiter(corps))
        except (DepotRefuse, CorrectionInvalide, SimulationInvalide, ValueError, TypeError) as erreur:
            self._json(HTTPStatus.BAD_REQUEST, {"erreur": str(erreur)})
        except AssistantIndisponible as erreur:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"erreur": str(erreur)})

    def _traiter(self, corps: bytes) -> dict:
        dossier = self.cache.dossier
        if self.path == "/api/releves":
            titulaire = unquote(self.headers.get("X-Titulaire", ""))
            nom = unquote(self.headers.get("X-Nom-Fichier", "releve.pdf"))
            return deposer_releve(dossier, titulaire, nom, corps)
        donnees = json.loads(corps or b"{}")
        if not isinstance(donnees, dict):
            raise TypeError("objet JSON attendu")
        if self.path == "/api/corrections":
            return ecrire_corrections(dossier, donnees)
        if self.path == "/api/simulation":
            return simuler(donnees)
        if self.path == "/api/configuration":
            return enregistrer_configuration(dossier, donnees)
        if self.path == "/api/assistant":
            if not _assistant_actif(dossier):
                raise AssistantIndisponible("assistant désactivé dans l'onglet Configuration")
            reponse = demander(
                str(donnees.get("question", "")), list(donnees.get("historique") or []), self.cache.lire()
            )
            return {"reponse": reponse}
        raise ValueError("adresse inconnue")

    def _requete_sure(self) -> bool:
        """Rendre vrai si la requête vient de la page servie ici ; sinon répondre 403. Voir l'en-tête du module."""
        origine = self.headers.get("Origin")
        hote_ok = self.headers.get("Host") in self.hotes
        origine_ok = origine is None or origine.removeprefix("http://") in self.hotes
        envoi_ok = self.command == "GET" or self.headers.get("X-Metabank") == "1"
        if hote_ok and origine_ok and envoi_ok and self.client_address[0] == ADRESSE:
            return True
        self._json(HTTPStatus.FORBIDDEN, {"erreur": "requête refusée"})
        return False

    def _json(self, statut: HTTPStatus, donnees: dict) -> None:
        self._envoyer(statut, json.dumps(donnees, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _envoyer(self, statut: HTTPStatus, corps: bytes, type_: str) -> None:
        self.send_response(statut)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(corps)
