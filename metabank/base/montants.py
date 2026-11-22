"""Montants en base : entiers de centimes, pour que SQLite ne passe jamais par un nombre à virgule flottante."""

from decimal import Decimal

CENTIME = Decimal("0.01")


class MontantInexact(ValueError):
    """Un montant a plus de deux décimales : l'arrondir perdrait de l'argent sans le dire."""


def en_centimes(montant: Decimal) -> int:
    """Rendre le montant en centimes entiers.

    Raises:
        MontantInexact: le montant a une fraction de centime.
    """
    centimes = montant * 100
    if centimes != centimes.to_integral_value():
        raise MontantInexact(f"{montant} n'est pas un nombre entier de centimes")
    return int(centimes)


def depuis_centimes(centimes: int) -> Decimal:
    """Rendre le montant en unités de la devise (euros pour EUR), avec deux décimales."""
    return (Decimal(centimes) / 100).quantize(CENTIME)
