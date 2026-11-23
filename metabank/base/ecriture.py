"""Enregistrer un lot en base : comptes, opérations sans doublon, soldes, relevés d'assureurs et leurs supports."""

import sqlite3

from metabank.base.lot import Lot
from metabank.base.montants import en_centimes
from metabank.releves.serialisation import releve_en_json


def enregistrer_lot(connexion: sqlite3.Connection, lot: Lot, archive_id: int | None) -> int:
    """Rendre le nombre d'opérations ajoutées, de soldes et de relevés enregistrés.

    Une opération déjà connue (même compte, même identifiant) est ignorée, comme celle qu'une autre source a déjà
    apportée (même montant, à 5 jours au plus : MODELE § 7.1 bis). Un compte déjà en base prend la
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


ECART_JUMELLE_JOURS = 5


def _enregistrer_operations(connexion: sqlite3.Connection, lot: Lot, ids: dict, archive_id: int | None) -> int:
    ajoutees = 0
    for operation in lot.operations:
        compte_id, centimes = ids[operation.compte_cle], en_centimes(operation.montant)
        deja = connexion.execute(
            "SELECT 1 FROM operations WHERE compte_id = ? AND identifiant = ? UNION ALL "
            "SELECT 1 FROM jumelles WHERE compte_id = ? AND identifiant = ?",
            (compte_id, operation.identifiant, compte_id, operation.identifiant),
        ).fetchone()
        if deja:
            continue
        jumelle = _jumelle(connexion, compte_id, operation.jour.isoformat(), centimes, lot.connecteur)
        if jumelle is not None:
            connexion.execute(
                "INSERT INTO jumelles (operation_id, compte_id, identifiant, archive_id) VALUES (?, ?, ?, ?)",
                (jumelle, compte_id, operation.identifiant, archive_id),
            )
            continue
        connexion.execute(
            "INSERT INTO operations (compte_id, identifiant, jour, libelle, nature, sous_nature, montant_centimes, "
            "devise, archive_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (compte_id, operation.identifiant, operation.jour.isoformat(), operation.libelle, operation.nature,
             operation.sous_nature, centimes, operation.devise, archive_id),
        )  # fmt: skip
        ajoutees += 1
    return ajoutees


def _jumelle(connexion: sqlite3.Connection, compte_id: int, jour: str, centimes: int, connecteur: str) -> int | None:
    """Rendre l'opération d'une autre source, même montant, à 5 jours au plus et encore libre. MODELE § 7.1 bis."""
    ligne = connexion.execute(
        "SELECT o.id FROM operations o JOIN imports i ON i.archive_id = o.archive_id "
        "WHERE o.compte_id = ? AND o.montant_centimes = ? AND i.connecteur != ? "
        "AND abs(julianday(o.jour) - julianday(?)) <= ? AND o.id NOT IN (SELECT operation_id FROM jumelles) "
        "ORDER BY abs(julianday(o.jour) - julianday(?)), o.id LIMIT 1",
        (compte_id, centimes, connecteur, jour, ECART_JUMELLE_JOURS, jour),
    ).fetchone()
    return None if ligne is None else int(ligne[0])


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
