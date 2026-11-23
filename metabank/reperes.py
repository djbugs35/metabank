"""Repères annuels publics, datés et sourcés : de quoi situer le rendement d'une année. MODELE § 10.

Taux en fractions (0,0263 = 2,63 %). Une valeur absente (None) n'a pas été publiée ou pas vérifiée à la source :
elle n'est jamais devinée. Mise à jour une fois par an, à la publication de chaque source.
"""

from dataclasses import dataclass
from decimal import Decimal

from metabank.banque.analyse import taux_moyen_annee


@dataclass(frozen=True)
class Reperes:
    """Les repères d'une année, en fractions ; None = non publié ou non vérifié."""

    annee: int
    fonds_euros: Decimal | None
    unites_de_compte: Decimal | None
    livret_a: Decimal | None
    inflation: Decimal | None
    msci_world: Decimal | None


SOURCES = {
    "fonds_euros": (
        "ACPR, Analyses et synthèses n° 175 (revalorisation 2024) et n° 180 (revalorisation 2025) : contrats "
        "individuels, nets de frais sur encours, avant prélèvements sociaux. 2023 à 2025 au centième (texte), 2020 à "
        "2022 au dixième (graphique « taux de revalorisation net moyen »)."
    ),
    "unites_de_compte": (
        "France Assureurs, « L'assurance vie en unités de compte, année 2025 » : performance globale des supports en "
        "UC, brute des frais des contrats, nette des coûts récurrents des fonds."
    ),
    "livret_a": "Taux réglementés en vigueur (metabank/banque/analyse.py), moyenne des 1ers de mois.",
    "inflation": (
        "Insee, indice des prix à la consommation, hausse moyenne annuelle (Informations rapides de janvier ; "
        "reprises par l'ACPR n° 175)."
    ),
    "msci_world": "MSCI World Index (EUR), fiche au 30/10/2026, « Annual performance », rendements nets en euros.",
}

_PUBLIES: dict[int, tuple[str | None, str | None, str | None, str | None]] = {
    # année : (fonds en euros, unités de compte, inflation, MSCI World), en pourcentages tels que publiés.
    2020: ("1.3", None, None, "6.33"),
    2021: ("1.3", None, None, "31.07"),
    2022: ("1.9", None, "5.2", "-12.78"),
    2023: ("2.60", "7.4", "4.9", "19.60"),
    2024: ("2.63", "5.4", "2.0", "26.60"),
    2025: ("2.63", "5.5", "0.9", "6.77"),
}


def _fraction(pourcentage: str | None) -> Decimal | None:
    return None if pourcentage is None else Decimal(pourcentage) / 100


def reperes_de(annee: int) -> Reperes:
    """Rendre les repères publics de l'année ; tous None pour une année sans publication."""
    fonds_euros, uc, inflation, msci = _PUBLIES.get(annee, (None, None, None, None))
    return Reperes(annee, _fraction(fonds_euros), _fraction(uc), taux_moyen_annee(annee), _fraction(inflation),
                   _fraction(msci))  # fmt: skip
