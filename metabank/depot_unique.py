"""Dépôt unique : un fichier posé dans le dossier surveillé, ou glissé dans la page sans titulaire, se range seul.

Le connecteur qui reconnaît le fichier dit de quel compte il s'agit (établissement, numéro masqué, type) ; si ce compte
est déjà connu de la base, le fichier rejoint le dossier de ses archives. Un compte jamais vu ne peut pas être deviné
(à qui est-il ?) : le fichier attend, et la page demande son titulaire.

Dossier surveillé : data/depot/ par défaut (onglet Configuration). Un fichier pris en compte y est déplacé dans
importes/ : l'archive en garde une copie, et le dossier ne montre que ce qui reste à faire.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from metabank.base.integration import importer_fichier, ouvrir_base
from metabank.base.lot import LectureImpossible
from metabank.connecteurs.contrat import Connecteur, Reconnaissance
from metabank.connecteurs.registre import composer_lecteur, reconnaitre

DOSSIER_DEPOT = "depot"
SOUS_DOSSIER_TRAITES = "importes"
EXTENSIONS = (".pdf", ".csv")


class CompteInconnu(ValueError):
    """Le fichier est reconnu, mais son compte n'est pas encore dans la base : son titulaire est à indiquer."""


@dataclass
class BilanDepot:
    """Fichiers du dossier surveillé : importés, déjà archivés, ou laissés en place avec la raison."""

    importes: list[str] = field(default_factory=list)
    deja_presents: list[str] = field(default_factory=list)
    en_attente: list[str] = field(default_factory=list)


def dossier_depot(dossier_data: Path, configuration: dict) -> Path:
    """Rendre le dossier surveillé : celui de la configuration, sinon data/depot/."""
    saisi = configuration.get("dossiers", {}).get("depot", "")
    return Path(saisi).expanduser() if saisi else dossier_data / DOSSIER_DEPOT


def provenance_du_compte(connexion: sqlite3.Connection, reconnaissance: Reconnaissance) -> str:
    """Rendre le dossier d'archives où ranger un fichier de ce compte (« Alice/CC - BNP - 1234[/2025] »).

    Raises:
        CompteInconnu: aucun compte, ou plusieurs, ne correspondent ; ou le connecteur ne dit pas le numéro.
    """
    if not reconnaissance.numero_masque:
        raise CompteInconnu("numéro du compte illisible dans le fichier")
    candidats = [
        cle
        for cle, type_compte in connexion.execute(
            "SELECT cle, type_compte FROM comptes WHERE etablissement = ? AND numero_masque = ?",
            (reconnaissance.etablissement, reconnaissance.numero_masque),
        )
        # Un export BNP ne dit pas s'il vient d'un compte courant ou d'un livret ; il dit seulement s'il est un prêt.
        if type_compte == reconnaissance.type_compte or (not reconnaissance.type_compte and type_compte != "credit")
    ]
    if len(candidats) != 1:
        raise CompteInconnu(
            f"compte {reconnaissance.etablissement} {reconnaissance.numero_masque} "
            + ("encore inconnu : indiquez son titulaire" if not candidats else "ambigu : indiquez son titulaire")
        )
    chemin = connexion.execute(
        "SELECT a.chemin FROM imports i JOIN archives a ON a.id = i.archive_id WHERE i.resultat = 'ok' "
        "AND ',' || i.compte_cle || ',' LIKE '%,' || ? || ',%' ORDER BY i.le DESC LIMIT 1",
        (candidats[0],),
    ).fetchone()
    if chemin is None:
        raise CompteInconnu(f"compte {candidats[0]} sans archive : indiquez son titulaire")
    provenance = "/".join(PurePosixPath(chemin[0]).parts[:2])
    return f"{provenance}/{reconnaissance.sous_dossier}" if reconnaissance.sous_dossier else provenance


def importer_sans_titulaire(dossier_data: Path, connecteurs: list[Connecteur], nom: str, contenu: bytes):
    """Rendre le résultat de l'import (base/integration.Resultat) d'un fichier rangé d'après son contenu seul.

    Raises:
        CompteInconnu: compte encore inconnu ou ambigu.
        ValueError: fichier non reconnu (FichierNonReconnu) ou illisible (LectureImpossible).
    """
    lire = composer_lecteur(connecteurs)
    reconnaissance = reconnaitre(connecteurs, nom, contenu)
    if reconnaissance is None:
        raise LectureImpossible(f"{nom} : aucun connecteur ne reconnaît ce fichier")
    connexion = ouvrir_base(dossier_data, lire)
    try:
        provenance = provenance_du_compte(connexion, reconnaissance)
    finally:
        connexion.close()
    return importer_fichier(dossier_data, provenance, nom, contenu, lire)


def traiter_dossier_depot(dossier_data: Path, depot: Path, connecteurs: list[Connecteur]) -> BilanDepot:
    """Rendre le bilan du dossier surveillé, après avoir importé et mis de côté chaque fichier pris en compte."""
    bilan = BilanDepot()
    if not depot.is_dir():
        return bilan
    for fichier in sorted(f for f in depot.iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONS):
        try:
            resultat = importer_sans_titulaire(dossier_data, connecteurs, fichier.name, fichier.read_bytes())
        except ValueError as erreur:
            # Compte inconnu, fichier non reconnu ou illisible : le fichier reste, la page dit pourquoi.
            bilan.en_attente.append(f"{fichier.name} : {erreur}")
            continue
        (bilan.deja_presents if resultat.deja_present else bilan.importes).append(fichier.name)
        _mettre_de_cote(fichier, depot / SOUS_DOSSIER_TRAITES)
    return bilan


def _mettre_de_cote(fichier: Path, traites: Path) -> None:
    traites.mkdir(exist_ok=True)
    cible, rang = traites / fichier.name, 2
    while cible.exists():
        cible = traites / f"{fichier.stem} ({rang}){fichier.suffix}"
        rang += 1
    fichier.replace(cible)
