"""Enregistrer un lot en base : comptes, opérations sans doublon, soldes, relevés d'assureurs et leurs supports."""

import sqlite3

from metabank.base.lot import Lot
from metabank.base.montants import en_centimes
from metabank.releves.serialisation import releve_en_json


def enregistrer_lot(connexion: sqlite3.Connection, lot: Lot, archive_id: int | None) -> int:
    """Rendre le nombre d'opérations ajoutées, de soldes et de relevés enregistrés.

    Une opération déjà connue (même compte, même identifiant) est ignorée. Un compte déjà en base prend la
    description du lot le plus récent ; un solde du même jour et un relevé de même date aussi.
    Ne valide pas la transaction : c'est à l'appelant de le faire.
    """
    _enregistrer_comptes(connexion, lot)
    ids = dict(connexion.execute("SELECT cle, id FROM comptes"))
    return (
        _enregistrer_operations(connexion, lot, ids, archive_id)
        + _enregistrer_soldes(connexion, lot, ids, archive_id)
        + _enregistrer_releves(connexion, lot, ids, archive_id)
    )


def _enregistrer_comptes(connexion: sqlite3.Connection, lot: Lot) -> None:
    for compte in lot.comptes:
        connexion.execute(
            "INSERT INTO comptes (cle, titulaire, etablissement, type_compte, numero_masque, libelle, devise) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (cle) DO UPDATE SET titulaire = excluded.titulaire, "
            "etablissement = excluded.etablissement, type_compte = excluded.type_compte, "
            "numero_masque = excluded.numero_masque, libelle = excluded.libelle, devise = excluded.devise",
            (compte.cle, compte.titulaire, compte.etablissement, compte.type_compte, compte.numero_masque,
             compte.libelle, compte.devise),
        )  # fmt: skip


def _enregistrer_operations(connexion: sqlite3.Connection, lot: Lot, ids: dict, archive_id: int | None) -> int:
    ajoutees = 0
    for operation in lot.operations:
        curseur = connexion.execute(
            "INSERT OR IGNORE INTO operations (compte_id, identifiant, jour, libelle, nature, sous_nature, "
            "montant_centimes, devise, archive_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ids[operation.compte_cle], operation.identifiant, operation.jour.isoformat(), operation.libelle,
             operation.nature, operation.sous_nature, en_centimes(operation.montant), operation.devise, archive_id),
        )  # fmt: skip
        ajoutees += curseur.rowcount
    return ajoutees


def _enregistrer_soldes(connexion: sqlite3.Connection, lot: Lot, ids: dict, archive_id: int | None) -> int:
    for solde in lot.soldes:
        connexion.execute(
            "INSERT INTO soldes (compte_id, jour, montant_centimes, devise, archive_id) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (compte_id, jour) DO UPDATE SET montant_centimes = excluded.montant_centimes, "
            "devise = excluded.devise, archive_id = excluded.archive_id",
            (ids[solde.compte_cle], solde.jour.isoformat(), en_centimes(solde.montant), solde.devise, archive_id),
        )
    return len(lot.soldes)


def _enregistrer_releves(connexion: sqlite3.Connection, lot: Lot, ids: dict, archive_id: int | None) -> int:
    for lu in lot.releves:
        releve = lu.releve
        releve_id = connexion.execute(
            "INSERT INTO releves (compte_id, date_arrete, est_annuel, valeur_centimes, devise, detail, archive_id) "
            "VALUES (?, ?, ?, ?, 'EUR', ?, ?) ON CONFLICT (compte_id, date_arrete, est_annuel) DO UPDATE SET "
            "valeur_centimes = excluded.valeur_centimes, detail = excluded.detail, archive_id = excluded.archive_id "
            "RETURNING id",
            (ids[lu.compte_cle], releve.date_arrete.isoformat(), int(releve.est_annuel), en_centimes(releve.valeur),
             releve_en_json(releve), archive_id),
        ).fetchone()[0]  # fmt: skip
        connexion.execute("DELETE FROM positions WHERE releve_id = ?", (releve_id,))
        connexion.executemany(
            "INSERT INTO positions (releve_id, rang, libelle, isin, parts, valeur_part, valeur_centimes, devise) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'EUR')",
            [(releve_id, rang, s.libelle, s.isin, _texte(s.parts), _texte(s.valeur_part), en_centimes(s.valeur))
             for rang, s in enumerate(releve.supports, start=1)],
        )  # fmt: skip
    return len(lot.releves)


def _texte(valeur: object) -> str | None:
    return None if valeur is None else str(valeur)
