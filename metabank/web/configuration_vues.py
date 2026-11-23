"""Onglet Configuration : registre des comptes, fiches des connecteurs et paramètres, en JSON prêt à afficher."""

from pathlib import Path

from metabank.archivage import archiver_donnees
from metabank.banque.modele import LIBELLES_TYPES
from metabank.base.integration import ouvrir_base
from metabank.base.lecture import lire_registre
from metabank.configuration import FREQUENCES_PAR_TYPE, ecrire_configuration, lire_configuration
from metabank.connecteurs.contrat import Connecteur
from metabank.connecteurs.registre import composer_lecteur, lister_connecteurs
from metabank.depot_unique import dossier_depot

LIBELLES_CONTRATS = {
    "assurance_vie": "Assurance vie",
    "per": "PER",
    "perp": "PERP",
    "pea": "PEA",
    "cto": "Compte-titres",
}


def etat_configuration(dossier: Path) -> dict:
    """Rendre les comptes (saisie et valeurs par défaut), les connecteurs et les paramètres.

    Un réglage secret n'est jamais renvoyé : seulement s'il est renseigné ou non.
    """
    connecteurs = lister_connecteurs()
    configuration = lire_configuration(dossier)
    return {
        "comptes": [_compte(c, configuration["comptes"].get(c["cle"], {}), connecteurs) for c in _registre(dossier)],
        "connecteurs": [_connecteur(c, configuration["reglages"]) for c in connecteurs],
        "parametres": configuration["parametres"],
        "dossiers": configuration["dossiers"],
        "dossier_depot": str(dossier_depot(dossier, configuration)),
        "dossier_donnees": str(dossier),
    }


def enregistrer_configuration(dossier: Path, saisie: dict) -> dict:
    """Rendre l'état de l'onglet après avoir validé et enregistré la saisie.

    Raises:
        ConfigurationInvalide: saisie hors format (rien n'est écrit).
    """
    cles = {c["cle"] for c in _registre(dossier)}
    ecrire_configuration(dossier, saisie, lister_connecteurs(), cles)
    return etat_configuration(dossier)


def _registre(dossier: Path) -> list[dict]:
    if not dossier.is_dir():
        return []
    # Les fichiers rangés à la main depuis le dernier chargement doivent apparaître ici aussi.
    connecteurs = lister_connecteurs()
    archiver_donnees(dossier, connecteurs)
    connexion = ouvrir_base(dossier, composer_lecteur(connecteurs))
    try:
        return lire_registre(connexion)
    finally:
        connexion.close()


def _compte(compte: dict, saisie: dict, connecteurs: list[Connecteur]) -> dict:
    type_compte = compte["type_compte"]
    possibles = [c.nom for c in connecteurs if type_compte in c.types_comptes]
    return {
        **compte,
        "libelle_type": LIBELLES_TYPES.get(type_compte) or LIBELLES_CONTRATS.get(type_compte, type_compte),
        "titulaire_saisi": saisie.get("titulaire", ""),
        "principal": saisie.get("principal") or compte["dernier_connecteur"],
        "secours": saisie.get("secours", ""),
        "frequence_jours": saisie.get("frequence_jours") or FREQUENCES_PAR_TYPE.get(type_compte),
        "connecteurs_possibles": possibles,
    }


def _connecteur(connecteur: Connecteur, valeurs: dict) -> dict:
    return {
        "nom": connecteur.nom,
        "libelle": connecteur.libelle,
        "famille": connecteur.famille,
        "reseau": connecteur.reseau,
        "etablissements": list(connecteur.etablissements),
        "types_comptes": list(connecteur.types_comptes),
        "actif": connecteur.est_actif(valeurs),
        "reglages": [
            {
                "nom": r.nom,
                "libelle": r.libelle,
                "secret": r.secret,
                "valeur": "" if r.secret else valeurs.get(r.nom, ""),
                "renseigne": bool(valeurs.get(r.nom)),
            }
            for r in connecteur.reglages
        ],
    }
