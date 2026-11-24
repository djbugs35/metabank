"""Ce que l'historique des opérations d'un document permet de refaire : flux de l'année, coupons reçus.

Les mêmes règles servent à la lecture du PDF et à la relecture de la fiche CSV (MODELE § 0) : une correction faite
à la main dans la fiche se retrouve dans les chiffres.
"""

from datetime import date
from decimal import Decimal

from metabank.releves.modele import Distribution, Operation

VERSEMENTS = ("VERSEMENT", "SOUSCRIPTION", "ADHESION")


def flux_des_operations(
    operations: tuple[Operation, ...], annee: int
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Rendre (versé, rachats, frais) de l'année d'après l'historique, en euros. MODELE § 2.4.

    Tout vaut None sans historique : l'année en cours ne se calcule pas. Les arbitrages et les coupons restent dans
    le contrat et ne sont pas des flux.
    """
    if not operations:
        return None, None, None
    verse = rachats = Decimal(0)
    frais = None
    for o in (o for o in operations if o.jour.year == annee):
        nature, montant = o.nature.upper(), abs(o.montant)
        if nature.startswith(VERSEMENTS):
            verse += montant
        elif nature.startswith("RACHAT"):
            rachats += montant
        elif nature.startswith(f"FRAIS ANNEE {annee}"):
            frais = (frais or Decimal(0)) + montant
    return verse, rachats, frais


def distributions_des_operations(operations: tuple[Operation, ...]) -> tuple[Distribution, ...]:
    """Rendre les coupons (lignes « DISTRIBUTION »), rattachés à l'ISIN du fonds nommé, sinon à son libellé. § 13.1."""
    vus: dict[tuple[date, str, Decimal], None] = {}
    for o in operations:
        if o.nature.upper().startswith("DISTRIBUTION"):
            # Les pages répètent parfois une ligne : un même coupon (jour, fonds, montant) n'est compté qu'une fois.
            vus[(o.jour, o.isin or o.libelle.upper(), o.montant)] = None
    return tuple(Distribution(jour, cle, montant) for jour, cle, montant in vus)
