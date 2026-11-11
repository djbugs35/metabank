"""Modèle commun à toutes les sources : un compte et les lignes qu'il détient, à la date de collecte.

Chaque connecteur (woob, Trade Republic, Revolut, saisie manuelle) traduit ses objets vers ce modèle ;
l'analyse ne connaît que lui. Les montants sont des Decimal dans la devise du compte, jamais des float.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

TYPES_COMPTE = (
    "courant",
    "livret",
    "assurance_vie",
    "capitalisation",
    "per",
    "pea",
    "cto",
    "credit",
    "autre",
)

# Enveloppes dont la valeur se lit ligne à ligne (supports détenus) plutôt que par un simple solde.
TYPES_AVEC_LIGNES = frozenset({"assurance_vie", "capitalisation", "per", "pea", "cto"})


@dataclass(frozen=True)
class Ligne:
    """Support détenu dans un compte : fonds en euros, unité de compte, ETF, action."""

    libelle: str
    valorisation: Decimal | None
    isin: str | None = None
    quantite: Decimal | None = None
    valeur_unitaire: Decimal | None = None
    prix_revient_unitaire: Decimal | None = None
    plus_value: Decimal | None = None
    date_valeur: date | None = None


@dataclass(frozen=True)
class Compte:
    """Compte ou contrat tel que vu par une source, avec ses lignes s'il en a."""

    source: str
    identifiant: str
    libelle: str
    type_compte: str
    solde: Decimal | None
    devise: str | None
    numero_masque: str | None
    lignes: tuple[Ligne, ...] = ()
