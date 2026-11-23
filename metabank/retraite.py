"""Projection retraite : capital au départ et retrait mensuel possible, en trois scénarios. MODELE § 12.

Montants en euros (capital au départ en euros courants et en euros d'aujourd'hui), taux en fractions annuelles.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

ZERO = Decimal(0)
DOUZE = Decimal(12)


@dataclass(frozen=True)
class Scenario:
    """Un scénario : rendement net supposé, capital au départ, en euros d'aujourd'hui, et retrait mensuel possible."""

    rendement: Decimal
    capital: Decimal
    capital_reel: Decimal
    retrait_mensuel: Decimal


def mois_jusqu_au_depart(aujourd_hui: date, annee_depart: int) -> int:
    """Rendre le nombre de mois entiers d'aujourd'hui au 1er janvier de l'année de départ (0 si passé)."""
    return max((annee_depart - aujourd_hui.year) * 12 - (aujourd_hui.month - 1), 0)


def _mensuel(annuel: Decimal) -> Decimal:
    return (1 + annuel) ** (Decimal(1) / DOUZE) - 1


def projeter(capital: Decimal, versement: Decimal, mois: int, rendement: Decimal, inflation: Decimal,
             duree_retrait: int) -> Scenario:  # fmt: skip
    """Rendre le scénario de rendement annuel net donné. MODELE § 12.

    Args:
        capital: valeur actuelle des contrats retenus, en euros.
        versement: versement mensuel supposé, en euros.
        duree_retrait: années de retraits mensuels égaux.
    """
    r = _mensuel(rendement)
    croissance = (1 + r) ** mois
    futur = capital * croissance + (versement * (croissance - 1) / r if r else versement * mois)
    reel = futur / (1 + inflation) ** (Decimal(mois) / DOUZE)
    retraits = DOUZE * duree_retrait
    retrait = reel * r / (1 - (1 + r) ** -retraits) if r else reel / retraits
    return Scenario(rendement, futur, reel, retrait)
