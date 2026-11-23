"""Fiscalité et échéances des contrats : 8 ans des assurances vie, abattement, transfert des PER. MODELE § 11.

Montants en euros. Des faits datés et un ordre de grandeur, jamais une recommandation.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from metabank.bilan import BilanContrat

ABATTEMENT_SEUL = Decimal(4600)
ABATTEMENT_COUPLE = Decimal(9200)
ANS_ASSURANCE_VIE = 8
ANS_TRANSFERT_PER = 5
JOURS_AFFICHES_APRES = 365


@dataclass(frozen=True)
class Echeance:
    """Une date à connaître ; jour None quand la date d'ouverture du contrat manque."""

    jour: date | None
    titulaire: str
    contrat: str
    quoi: str
    detail: str


def _anniversaire(ouverture: date, ans: int) -> date:
    try:
        return ouverture.replace(year=ouverture.year + ans)
    except ValueError:
        return ouverture.replace(year=ouverture.year + ans, day=28)


def rachat_couvert(bilan: BilanContrat, abattement: Decimal) -> Decimal | None:
    """Rendre le rachat dont les gains tiennent dans l'abattement (euros), ou None sans gain positif. MODELE § 11."""
    if bilan.gain_cumule is None or bilan.gain_cumule <= 0 or bilan.valeur <= 0:
        return None
    return min(abattement * bilan.valeur / bilan.gain_cumule, bilan.valeur)


def echeances(bilans: list[BilanContrat], aujourd_hui: date, imposition_commune: bool) -> list[Echeance]:
    """Rendre les échéances des contrats, datées d'abord par ordre chronologique, puis celles à saisir. MODELE § 11."""
    abattement = ABATTEMENT_COUPLE if imposition_commune else ABATTEMENT_SEUL
    liste = []
    for b in bilans:
        nom = f"{b.produit} {b.numero_masque}"
        if b.type_contrat == "assurance_vie":
            liste.append(_echeance(b, nom, ANS_ASSURANCE_VIE, "8 ans de l'assurance vie", _detail_av(b, abattement)))
        elif b.type_contrat == "per":
            liste.append(_echeance(b, nom, ANS_TRANSFERT_PER, "Transfert du PER sans frais",
                                   "avant : frais de transfert d'au plus 1 % de l'épargne"))  # fmt: skip
    if any(b.type_contrat == "per" for b in bilans):
        fin_annee = date(aujourd_hui.year, 12, 31)
        liste.append(Echeance(fin_annee, "Foyer", "PER", "Versements déductibles de l'année",
                              "dernier jour pour qu'un versement compte dans le plafond de cette année"))  # fmt: skip
    visibles = [e for e in liste if e.jour is None or (aujourd_hui - e.jour).days <= JOURS_AFFICHES_APRES]
    return sorted(visibles, key=lambda e: (e.jour is None, e.jour or aujourd_hui))


def _echeance(b: BilanContrat, nom: str, ans: int, quoi: str, detail: str) -> Echeance:
    if b.date_ouverture is None:
        return Echeance(None, b.titulaire, nom, quoi, "date d'ouverture à saisir dans Corrections")
    return Echeance(_anniversaire(b.date_ouverture, ans), b.titulaire, nom, quoi, detail)


def _detail_av(b: BilanContrat, abattement: Decimal) -> str:
    couvert = rachat_couvert(b, abattement)
    if couvert is None:
        return f"ensuite, abattement annuel de {abattement:.0f} € sur les gains rachetés"
    return (f"ensuite, abattement annuel de {abattement:.0f} € sur les gains : un rachat d'environ "
            f"{couvert:,.0f} € reste sans impôt sur le revenu (prélèvements sociaux dus)").replace(",", " ")  # fmt: skip
