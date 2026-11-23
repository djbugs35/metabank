"""Données des analyses et des écrans, lues dans la base data/metabank.db.

Avant chaque lecture, les fichiers encore rangés à la main dans data/<titulaire>/<compte>/ sont copiés dans les
archives (archivage.py) : déposer un PDF ou un CSV dans son dossier suffit toujours, et un fichier déjà archivé
n'est que reconnu à son empreinte. Les originaux ne sont jamais touchés. Le titulaire saisi dans l'onglet
Configuration l'emporte sur celui du dossier.
"""

from dataclasses import dataclass
from pathlib import Path

from metabank.archivage import archiver_donnees
from metabank.banque.modele import Compte
from metabank.base.integration import ouvrir_base
from metabank.base.lecture import lire_comptes_bancaires, lire_releves
from metabank.configuration import lire_configuration, titulaires_saisis
from metabank.connecteurs.registre import composer_lecteur, lister_connecteurs
from metabank.releves import ReleveRange


@dataclass(frozen=True)
class Donnees:
    """Relevés d'assureurs, comptes bancaires et crédits, et ce qui n'a pas pu être lu (messages en français)."""

    releves: list[ReleveRange]
    comptes: list[Compte]
    erreurs: list[str]


def charger(dossier_data: Path) -> Donnees:
    """Rendre les données de la base, après avoir archivé les fichiers rangés à la main depuis la dernière fois."""
    if not dossier_data.is_dir():
        return Donnees([], [], [])
    connecteurs = lister_connecteurs()
    bilan = archiver_donnees(dossier_data, connecteurs)
    connexion = ouvrir_base(dossier_data, composer_lecteur(connecteurs))
    try:
        titulaires = titulaires_saisis(lire_configuration(dossier_data))
        releves, comptes = lire_releves(connexion, titulaires), lire_comptes_bancaires(connexion, titulaires)
        archives_illisibles = [
            f"archives/{chemin} : {message}"
            for chemin, message in connexion.execute(
                "SELECT a.chemin, i.message FROM imports i JOIN archives a ON a.id = i.archive_id "
                "WHERE i.resultat = 'erreur' ORDER BY a.chemin"
            )
        ]
    finally:
        connexion.close()
    return Donnees(releves, comptes, bilan.refus + archives_illisibles)
