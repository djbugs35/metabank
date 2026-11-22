"""Faire entrer un fichier en base, et reconstruire la base depuis les archives seules.

Un import archive le fichier puis enregistre son lot ; une reconstruction relit toutes les archives dans leur ordre
d'entrée avec le même code. Les deux chemins produisent donc la même base, ligne pour ligne.
Seul ce qui n'a pas laissé d'archive (un import refusé avant archivage) disparaît du journal à la reconstruction.
"""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from metabank.base.archives import (
    DOSSIER,
    Archive,
    calculer_empreinte,
    choisir_chemin,
    ecrire_archive,
    lister_archives,
)
from metabank.base.lot import Lot
from metabank.base.montants import en_centimes
from metabank.base.schema import ouvrir

FICHIER_BASE = "metabank.db"

# (provenance, nom du fichier archivé, contenu) -> lot, ou None si aucun connecteur ne reconnaît le fichier.
# Lève LectureImpossible quand le fichier est reconnu mais illisible.
Lecteur = Callable[[str, str, bytes], Lot | None]


class FichierNonReconnu(ValueError):
    """Aucun connecteur ne reconnaît ce fichier : il n'est pas archivé."""


@dataclass(frozen=True)
class Resultat:
    """Ce qu'est devenu un fichier déposé.

    Attributes:
        chemin: de l'archive, relatif à data/archives/ (celle qui existait déjà si deja_present).
        elements: opérations ajoutées et soldes enregistrés ; 0 si deja_present.
    """

    chemin: str
    connecteur: str
    deja_present: bool
    elements: int = 0


def ouvrir_base(dossier_data: Path, lire: Lecteur) -> sqlite3.Connection:
    """Rendre une connexion à data/metabank.db, reconstruite depuis les archives si le fichier a disparu."""
    chemin = dossier_data / FICHIER_BASE
    if not chemin.exists() and lister_archives(dossier_data):
        reconstruire(dossier_data, lire)
    return ouvrir(chemin)


def importer_fichier(dossier_data: Path, provenance: str, nom: str, contenu: bytes, lire: Lecteur) -> Resultat:
    """Rendre le résultat de l'import : fichier reconnu, archivé une seule fois, lot enregistré en base.

    Raises:
        FichierNonReconnu: aucun connecteur ne le reconnaît (rien n'est archivé).
        ValueError: reconnu mais illisible (LectureImpossible), ou lot invalide (rien n'est archivé).
        CheminRefuse: provenance ou nom de fichier dangereux.
    """
    connexion = ouvrir_base(dossier_data, lire)
    try:
        deja = connexion.execute(
            "SELECT chemin FROM archives WHERE empreinte = ?", (calculer_empreinte(contenu),)
        ).fetchone()
        if deja:
            connecteur = connexion.execute(
                "SELECT connecteur FROM imports JOIN archives a ON a.id = archive_id WHERE a.chemin = ?", deja
            ).fetchone()
            return Resultat(chemin=deja[0], connecteur=connecteur[0] if connecteur else "", deja_present=True)
        chemin = choisir_chemin(dossier_data, provenance, nom)
        lot = lire(provenance, chemin.name, contenu)
        if lot is None:
            raise FichierNonReconnu(f"{nom} : aucun connecteur ne reconnaît ce fichier")
        archive = ecrire_archive(dossier_data, chemin, contenu)
        try:
            with connexion:
                elements = _integrer(connexion, archive, lot)
        except BaseException:
            # Une archive sans ligne en base serait réintégrée à la prochaine reconstruction : on la retire.
            chemin.unlink()
            raise
        return Resultat(chemin=archive.chemin, connecteur=lot.connecteur, deja_present=False, elements=elements)
    finally:
        connexion.close()


def reconstruire(dossier_data: Path, lire: Lecteur) -> Path:
    """Rendre le chemin de data/metabank.db, refaite depuis data/archives/ seules.

    La base est construite à côté puis renommée : l'ancienne reste intacte si la reconstruction échoue.
    Une archive illisible ou plus reconnue est notée au journal sans arrêter les autres.
    """
    cible = dossier_data / FICHIER_BASE
    temporaire = cible.with_name(FICHIER_BASE + ".tmp")
    temporaire.unlink(missing_ok=True)
    connexion = ouvrir(temporaire)
    try:
        for archive in lister_archives(dossier_data):
            _rejouer(connexion, dossier_data, archive, lire)
    finally:
        connexion.close()
    temporaire.replace(cible)
    return cible


def _rejouer(connexion: sqlite3.Connection, dossier_data: Path, archive: Archive, lire: Lecteur) -> None:
    provenance, _, nom = archive.chemin.rpartition("/")
    contenu = (dossier_data / DOSSIER / archive.chemin).read_bytes()
    try:
        with connexion:
            lot = lire(provenance, nom, contenu)
            if lot is not None:
                _integrer(connexion, archive, lot)
                return
            _noter_echec(connexion, archive, "refus", "aucun connecteur ne reconnaît ce fichier")
    except ValueError as erreur:
        # LectureImpossible, montant à fraction de centime, numéro non masqué : l'archive reste, l'erreur est notée.
        with connexion:
            _noter_echec(connexion, archive, "erreur", str(erreur))


def _integrer(connexion: sqlite3.Connection, archive: Archive, lot: Lot) -> int:
    archive_id = _inserer_archive(connexion, archive)
    elements = enregistrer_lot(connexion, lot, archive_id)
    comptes = ",".join(c.cle for c in lot.comptes)
    _journaliser(connexion, archive, archive_id, (lot.connecteur, comptes, "ok", elements, ""))
    return elements


def _inserer_archive(connexion: sqlite3.Connection, archive: Archive) -> int:
    curseur = connexion.execute(
        "INSERT INTO archives (chemin, empreinte, taille, archivee_le) VALUES (?, ?, ?, ?)",
        (archive.chemin, archive.empreinte, archive.taille, archive.archivee_le),
    )
    return int(curseur.lastrowid or 0)


def _noter_echec(connexion: sqlite3.Connection, archive: Archive, resultat: str, message: str) -> None:
    archive_id = _inserer_archive(connexion, archive)
    _journaliser(connexion, archive, archive_id, ("", "", resultat, 0, message))


def _journaliser(
    connexion: sqlite3.Connection, archive: Archive, archive_id: int, issue: tuple[str, str, str, int, str]
) -> None:
    """Noter au journal issue = (connecteur, clés des comptes séparées par « , », résultat, éléments, message)."""
    # La date d'un import est celle de son archive, pas l'heure de la reconstruction : le journal se refait à l'identique.
    connexion.execute(
        "INSERT INTO imports (le, archive_id, connecteur, compte_cle, resultat, elements, message) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (archive.archivee_le, archive_id, *issue),
    )


def enregistrer_lot(connexion: sqlite3.Connection, lot: Lot, archive_id: int | None) -> int:
    """Rendre le nombre d'opérations ajoutées et de soldes enregistrés ; les opérations déjà connues sont ignorées.

    Un compte déjà en base prend la description du lot le plus récent ; un solde du même jour aussi.
    Ne valide pas la transaction : c'est à l'appelant de le faire.
    """
    for compte in lot.comptes:
        connexion.execute(
            "INSERT INTO comptes (cle, titulaire, etablissement, type_compte, numero_masque, libelle, devise) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (cle) DO UPDATE SET titulaire = excluded.titulaire, "
            "etablissement = excluded.etablissement, type_compte = excluded.type_compte, "
            "numero_masque = excluded.numero_masque, libelle = excluded.libelle, devise = excluded.devise",
            (compte.cle, compte.titulaire, compte.etablissement, compte.type_compte, compte.numero_masque,
             compte.libelle, compte.devise),
        )  # fmt: skip
    ids = dict(connexion.execute("SELECT cle, id FROM comptes"))
    elements = 0
    for operation in lot.operations:
        curseur = connexion.execute(
            "INSERT OR IGNORE INTO operations (compte_id, identifiant, jour, libelle, nature, montant_centimes, "
            "devise, archive_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ids[operation.compte_cle], operation.identifiant, operation.jour.isoformat(), operation.libelle,
             operation.nature, en_centimes(operation.montant), operation.devise, archive_id),
        )  # fmt: skip
        elements += curseur.rowcount
    for solde in lot.soldes:
        connexion.execute(
            "INSERT INTO soldes (compte_id, jour, montant_centimes, devise, archive_id) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (compte_id, jour) DO UPDATE SET montant_centimes = excluded.montant_centimes, "
            "devise = excluded.devise, archive_id = excluded.archive_id",
            (ids[solde.compte_cle], solde.jour.isoformat(), en_centimes(solde.montant), solde.devise, archive_id),
        )
        elements += 1
    return elements
