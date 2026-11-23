"""Registre des connecteurs : les trouver, lire un fichier avec le bon, synchroniser un compte par ses accès.

Un connecteur s'ajoute en écrivant un module de metabank/connecteurs/ qui expose `CONNECTEUR`, une instance d'une
classe de connecteurs/contrat.py. Rien d'autre à toucher : le registre parcourt le paquet.
"""

import importlib
import pkgutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from metabank.base.integration import Lecteur, Resultat, importer_fichier, ouvrir_base
from metabank.base.journal import noter_sans_archive
from metabank.base.lot import LectureImpossible, Lot
from metabank.connecteurs.contrat import (
    AccesIndisponible,
    Connecteur,
    ConnecteurDirect,
    ConnecteurFichier,
    Reconnaissance,
)

PAQUET = "metabank.connecteurs"
# Modules du paquet qui ne sont pas des connecteurs.
MODULES_DU_SOCLE = frozenset({"contrat", "registre"})


class ConnecteurInconnu(KeyError):
    """Aucun connecteur ne porte ce nom."""


class AucunAccesDirect(RuntimeError):
    """Ni l'accès principal ni celui de secours n'a pu interroger le service : le compte n'est pas à jour."""


@dataclass(frozen=True)
class AccesCompte:
    """Comment un compte se met à jour.

    Attributes:
        provenance: dossier de ses archives (« Alice/CC - BNP - 1234 »).
        principal: nom du connecteur essayé d'abord.
        secours: nom du connecteur essayé si le principal échoue ; vide s'il n'y en a pas.
    """

    compte_cle: str
    provenance: str
    principal: str
    secours: str = ""


def lister_connecteurs(paquet: str = PAQUET) -> list[Connecteur]:
    """Rendre les connecteurs déclarés dans les modules du paquet, triés par nom.

    Raises:
        TypeError: un module du paquet n'expose pas de CONNECTEUR.
        ValueError: deux connecteurs portent le même nom.
    """
    racine = importlib.import_module(paquet)
    connecteurs: list[Connecteur] = []
    for module in pkgutil.iter_modules(racine.__path__):
        if module.name.startswith("_") or module.name in MODULES_DU_SOCLE:
            continue
        connecteur = getattr(importlib.import_module(f"{paquet}.{module.name}"), "CONNECTEUR", None)
        if not isinstance(connecteur, Connecteur):
            raise TypeError(f"{paquet}.{module.name} n'expose pas de CONNECTEUR")
        connecteurs.append(connecteur)
    noms = [c.nom for c in connecteurs]
    doublons = sorted({n for n in noms if noms.count(n) > 1})
    if doublons:
        raise ValueError(f"connecteurs de même nom : {', '.join(doublons)}")
    return sorted(connecteurs, key=lambda c: c.nom)


def trouver(connecteurs: Sequence[Connecteur], nom: str) -> Connecteur:
    """Rendre le connecteur de ce nom.

    Raises:
        ConnecteurInconnu: aucun ne porte ce nom.
    """
    for connecteur in connecteurs:
        if connecteur.nom == nom:
            return connecteur
    raise ConnecteurInconnu(nom)


def composer_lecteur(connecteurs: Sequence[Connecteur]) -> Lecteur:
    """Rendre la fonction de lecture attendue par base/integration.py, qui confie chaque fichier à son connecteur.

    Tous les connecteurs de fichiers et directs servent, actifs ou non : relire une archive locale ne demande aucun
    réglage, et la base doit se reconstruire même si un accès a été retiré depuis.
    """
    lecteurs = [c for c in connecteurs if isinstance(c, ConnecteurFichier)]

    def lire(provenance: str, nom: str, contenu: bytes) -> Lot | None:
        candidats = [c for c in lecteurs if c.reconnaitre(nom, contenu) is not None]
        if len(candidats) > 1:
            # Choisir l'un au hasard de l'ordre des modules donnerait des chiffres différents d'une machine à l'autre.
            raise LectureImpossible(f"{nom} : reconnu à la fois par {', '.join(c.nom for c in candidats)}")
        return candidats[0].lire(provenance, nom, contenu) if candidats else None

    return lire


def synchroniser_compte(
    dossier_data: Path, connecteurs: Sequence[Connecteur], valeurs: Mapping[str, str], acces: AccesCompte, depuis: date
) -> Resultat:
    """Rendre le résultat de l'import de la réponse du premier accès direct qui répond, principal puis secours.

    Chaque échec est noté au journal. Un accès inactif (réglages manquants) ou qui n'est pas direct est passé.

    Raises:
        AucunAccesDirect: aucun accès n'a répondu.
    """
    lire = composer_lecteur(connecteurs)
    echecs: list[str] = []
    for nom in filter(None, (acces.principal, acces.secours)):
        connecteur = trouver(connecteurs, nom)
        if not isinstance(connecteur, ConnecteurDirect) or not connecteur.est_actif(valeurs):
            continue
        try:
            reponse = connecteur.synchroniser(valeurs, acces.compte_cle, depuis)
        except AccesIndisponible as erreur:
            echecs.append(f"{nom} : {erreur}")
            connexion = ouvrir_base(dossier_data, lire)
            try:
                noter_sans_archive(connexion, nom, acces.compte_cle, "erreur", str(erreur))
            finally:
                connexion.close()
            continue
        return importer_fichier(dossier_data, acces.provenance, reponse.nom, reponse.contenu, lire)
    raise AucunAccesDirect(f"{acces.compte_cle} : " + ("; ".join(echecs) or "aucun accès direct actif"))


def reconnaitre(connecteurs: Sequence[Connecteur], nom: str, contenu: bytes) -> Reconnaissance | None:
    """Rendre ce que le seul connecteur qui reconnaît le fichier en déduit, ou None si aucun ne le reconnaît.

    Raises:
        LectureImpossible: deux connecteurs le reconnaissent, ou l'outil de lecture manque (pdftotext).
    """
    trouvees = [
        (c.nom, r)
        for c in connecteurs
        if isinstance(c, ConnecteurFichier) and (r := c.reconnaitre(nom, contenu)) is not None
    ]
    if len(trouvees) > 1:
        raise LectureImpossible(f"{nom} : reconnu à la fois par {', '.join(n for n, _ in trouvees)}")
    return trouvees[0][1] if trouvees else None
