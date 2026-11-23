"""Schéma de data/metabank.db, versionné par PRAGMA user_version et migré à l'ouverture.

On n'édite jamais une migration publiée : une base existante ne la rejouerait pas. On en ajoute une à la fin.
Montants en centimes entiers (base/montants.py), dates en texte ISO 8601, devise sur chaque ligne qui porte un montant.
Quantités (parts, valeurs liquidatives) et détail des relevés en texte décimal : aucun flottant.
"""

import sqlite3
from pathlib import Path

MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE archives (
        id INTEGER PRIMARY KEY,
        chemin TEXT NOT NULL UNIQUE,
        empreinte TEXT NOT NULL UNIQUE,
        taille INTEGER NOT NULL,
        archivee_le TEXT NOT NULL
    );
    CREATE TABLE imports (
        id INTEGER PRIMARY KEY,
        le TEXT NOT NULL,
        connecteur TEXT NOT NULL,
        compte_cle TEXT NOT NULL DEFAULT '',
        archive_id INTEGER REFERENCES archives(id),
        resultat TEXT NOT NULL CHECK (resultat IN ('ok', 'refus', 'erreur')),
        elements INTEGER NOT NULL DEFAULT 0,
        message TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX imports_par_date ON imports (le);
    CREATE TABLE comptes (
        id INTEGER PRIMARY KEY,
        cle TEXT NOT NULL UNIQUE,
        titulaire TEXT NOT NULL,
        etablissement TEXT NOT NULL,
        type_compte TEXT NOT NULL,
        numero_masque TEXT NOT NULL,
        libelle TEXT NOT NULL,
        devise TEXT NOT NULL
    );
    CREATE TABLE operations (
        id INTEGER PRIMARY KEY,
        compte_id INTEGER NOT NULL REFERENCES comptes(id),
        identifiant TEXT NOT NULL,
        jour TEXT NOT NULL,
        libelle TEXT NOT NULL,
        nature TEXT NOT NULL DEFAULT '',
        montant_centimes INTEGER NOT NULL,
        devise TEXT NOT NULL,
        archive_id INTEGER REFERENCES archives(id),
        UNIQUE (compte_id, identifiant)
    );
    CREATE INDEX operations_par_jour ON operations (compte_id, jour);
    CREATE TABLE soldes (
        compte_id INTEGER NOT NULL REFERENCES comptes(id),
        jour TEXT NOT NULL,
        montant_centimes INTEGER NOT NULL,
        devise TEXT NOT NULL,
        archive_id INTEGER REFERENCES archives(id),
        PRIMARY KEY (compte_id, jour)
    );
    """,
    # 2 : relevés d'assureurs (le relevé complet en JSON, ses supports à part) ; sous-type des opérations bancaires.
    """
    ALTER TABLE operations ADD COLUMN sous_nature TEXT NOT NULL DEFAULT '';
    CREATE TABLE releves (
        id INTEGER PRIMARY KEY,
        compte_id INTEGER NOT NULL REFERENCES comptes(id),
        date_arrete TEXT NOT NULL,
        est_annuel INTEGER NOT NULL,
        valeur_centimes INTEGER NOT NULL,
        devise TEXT NOT NULL,
        detail TEXT NOT NULL,
        archive_id INTEGER REFERENCES archives(id),
        UNIQUE (compte_id, date_arrete, est_annuel)
    );
    CREATE TABLE positions (
        releve_id INTEGER NOT NULL REFERENCES releves(id) ON DELETE CASCADE,
        rang INTEGER NOT NULL,
        libelle TEXT NOT NULL,
        isin TEXT,
        parts TEXT,
        valeur_part TEXT,
        valeur_centimes INTEGER NOT NULL,
        devise TEXT NOT NULL,
        PRIMARY KEY (releve_id, rang)
    );
    """,
    # 3 : une opération déjà reçue par une autre source (CSV et DSP2) n'est pas ajoutée deux fois. MODELE § 7.1 bis.
    """
    CREATE TABLE jumelles (
        operation_id INTEGER PRIMARY KEY REFERENCES operations(id),
        compte_id INTEGER NOT NULL REFERENCES comptes(id),
        identifiant TEXT NOT NULL,
        archive_id INTEGER REFERENCES archives(id),
        UNIQUE (compte_id, identifiant)
    );
    """,
)

VERSION = len(MIGRATIONS)


class BaseTropRecente(RuntimeError):
    """La base a été écrite par une version de metabank plus récente que celle qui l'ouvre."""


def ouvrir(chemin: Path) -> sqlite3.Connection:
    """Rendre une connexion à la base, créée ou migrée jusqu'à VERSION.

    Raises:
        BaseTropRecente: la base porte une version de schéma que ce code ne connaît pas.
    """
    connexion = sqlite3.connect(chemin)
    connexion.execute("PRAGMA foreign_keys = ON")
    version = connexion.execute("PRAGMA user_version").fetchone()[0]
    if version > VERSION:
        connexion.close()
        raise BaseTropRecente(f"{chemin.name} est au schéma {version}, ce code s'arrête au schéma {VERSION}")
    for numero in range(version, VERSION):
        # executescript valide d'abord toute transaction en cours : BEGIN et COMMIT rendent chaque migration
        # atomique, version comprise, pour qu'une migration interrompue soit rejouée en entier.
        connexion.executescript(f"BEGIN;{MIGRATIONS[numero]};PRAGMA user_version = {numero + 1};COMMIT;")
    return connexion
