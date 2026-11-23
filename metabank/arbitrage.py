"""Simulateur d'arbitrage : l'effet des frais d'un fonds à l'autre, à rendement brut égal. MODELE § 14.

Montants en euros ; frais et rendement en points de pourcentage par an (1,40 = 1,40 %).
"""

from dataclasses import dataclass
from decimal import Decimal

CENT = Decimal(100)


@dataclass(frozen=True)
class Arbitrage:
    """Garder ou arbitrer, année par année de 0 à H (valeurs en euros)."""

    garder: list[Decimal]
    arbitrer: list[Decimal]
    cout_immediat: Decimal
    point_mort: int | None

    @property
    def ecart(self) -> Decimal:
        """Rendre arbitrer moins garder à l'horizon, en euros."""
        return self.arbitrer[-1] - self.garder[-1]


def simuler_arbitrage(montant: Decimal, frais_source: Decimal, frais_cible: Decimal, frais_arbitrage: Decimal,
                      rendement: Decimal, horizon: int) -> Arbitrage:  # fmt: skip
    """Rendre les deux trajectoires et le point mort de l'arbitrage. MODELE § 14."""
    depart = montant * (1 - frais_arbitrage / CENT)
    garder = [montant * (1 + (rendement - frais_source) / CENT) ** annee for annee in range(horizon + 1)]
    arbitrer = [depart * (1 + (rendement - frais_cible) / CENT) ** annee for annee in range(horizon + 1)]
    point_mort = next((annee for annee in range(horizon + 1) if arbitrer[annee] >= garder[annee]), None)
    return Arbitrage(garder, arbitrer, montant * frais_arbitrage / CENT, point_mort)
