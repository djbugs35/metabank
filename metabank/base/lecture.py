"""Relire la base sous la forme qu'attendent les analyses : relevés rangés par titulaire, comptes bancaires fusionnés.

Mêmes objets, mêmes chiffres que releves.lire_dossier() et banque.lire_comptes(), qui relisent les fichiers.
"""

import sqlite3
from datetime import date
from pathlib import PurePosixPath

from metabank.banque.modele import Compte, Operation
from metabank.base.montants import depuis_centimes
from metabank.releves import ReleveRange
from metabank.releves.serialisation import releve_depuis_json

TYPES_BANCAIRES = ("courant", "locatif", "livret_a", "ldd", "credit")


def lire_releves(connexion: sqlite3.Connection) -> list[ReleveRange]:
    """Rendre les relevés d'assureurs, dans l'ordre de leurs archives (celui de releves.lire_dossier)."""
    lignes = connexion.execute(
        "SELECT c.titulaire, r.detail, coalesce(a.chemin, '') FROM releves r JOIN comptes c ON c.id = r.compte_id "
        "LEFT JOIN archives a ON a.id = r.archive_id"
    ).fetchall()
    lignes.sort(key=lambda ligne: PurePosixPath(ligne[2]))
    return [ReleveRange(titulaire, releve_depuis_json(detail)) for titulaire, detail, _ in lignes]


def lire_comptes_bancaires(connexion: sqlite3.Connection) -> list[Compte]:
    """Rendre les comptes bancaires et les crédits, dans l'ordre de leurs dossiers (celui de banque.lire_comptes).

    Le solde est celui du jour le plus récent ; les soldes des autres exports servent de contrôle. MODELE § 7.1.
    """
    comptes = []
    for compte_id, titulaire, banque, type_compte, nom, masque in connexion.execute(
        "SELECT id, titulaire, etablissement, type_compte, libelle, numero_masque FROM comptes "
        f"WHERE type_compte IN ({', '.join('?' * len(TYPES_BANCAIRES))})",
        TYPES_BANCAIRES,
    ).fetchall():
        operations = tuple(
            Operation(date.fromisoformat(jour), nature, sous_nature, libelle, depuis_centimes(centimes))
            for jour, nature, sous_nature, libelle, centimes in connexion.execute(
                "SELECT jour, nature, sous_nature, libelle, montant_centimes FROM operations WHERE compte_id = ? "
                "ORDER BY jour, id",
                (compte_id,),
            )
        )
        soldes = [
            (date.fromisoformat(jour), depuis_centimes(centimes), chemin)
            for jour, centimes, chemin in connexion.execute(
                "SELECT s.jour, s.montant_centimes, coalesce(a.chemin, '') FROM soldes s "
                "LEFT JOIN archives a ON a.id = s.archive_id WHERE s.compte_id = ? ORDER BY s.jour",
                (compte_id,),
            )
        ]
        if not soldes:
            continue
        jour_solde, solde, _ = soldes[-1]
        compte = Compte(titulaire, banque, type_compte, nom, masque, jour_solde, solde, operations,
                        _anomalies_de_solde(operations, soldes))  # fmt: skip
        comptes.append((min(PurePosixPath(chemin).parts[:2] for _, _, chemin in soldes), compte))
    return [compte for _, compte in sorted(comptes, key=lambda paire: paire[0])]


def _anomalies_de_solde(operations: tuple[Operation, ...], soldes: list) -> tuple[str, ...]:
    reference_jour, reference_solde, _ = soldes[-1]
    anomalies = []
    for jour, solde, chemin in soldes[:-1]:
        apres = sum((o.montant for o in operations if jour < o.jour <= reference_jour), start=0)
        attendu = reference_solde - apres
        if attendu != solde:
            anomalies.append(f"solde de {PurePosixPath(chemin).name} : {solde} € annoncé, {attendu} € recalculé")
    return tuple(anomalies)
