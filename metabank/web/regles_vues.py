"""Règles de classement des dépenses depuis la page : lister, tester, enregistrer (data/categories.json). MODELE § 7.2."""

from pathlib import Path

from metabank.banque.categories import categories_connues, ecrire_regles, essayer_motif, lire_regles
from metabank.banque.modele import TYPES_COURANTS
from metabank.donnees import charger


def etat_regles(dossier: Path) -> dict:
    """Rendre les règles personnelles, dans leur ordre d'application, et les catégories proposées."""
    regles = lire_regles(dossier)
    return {
        "regles": [{"motif": motif, "categorie": categorie} for motif, categorie in regles],
        "categories": categories_connues(regles),
    }


def enregistrer_regles(dossier: Path, saisie: dict) -> dict:
    """Rendre l'état des règles après avoir enregistré la liste saisie (elle remplace la précédente).

    Raises:
        RegleInvalide: une règle est hors format ; rien n'est écrit.
    """
    ecrire_regles(dossier, saisie.get("regles", []))
    return etat_regles(dossier)


def essayer_regle(dossier: Path, saisie: dict) -> dict:
    """Rendre ce que le motif saisi classerait parmi les opérations des comptes courants (nombre, montant, exemples).

    Raises:
        RegleInvalide: motif vide, trop long ou invalide.
    """
    operations = [o for c in charger(dossier).comptes if c.type_compte in TYPES_COURANTS for o in c.operations]
    return essayer_motif(str(saisie.get("motif") or ""), operations)
