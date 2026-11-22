"""Crédits immobiliers : capital restant dû, taux, mensualité, fin et intérêts restants estimés. MODELE § 7.9.

L'export BNP d'un prêt donne le capital restant dû (solde négatif) et une ligne « AMORTISSEMENT PRET » par mois :
la part de capital remboursée. Dans un prêt à mensualité constante, cette part croît chaque mois du taux mensuel ;
on en déduit le taux, puis la mensualité, la durée restante et les intérêts encore à payer.
"""

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise
from statistics import median

from metabank.banque.modele import Compte

ZERO = Decimal(0)
DOUZE = Decimal(12)


@dataclass(frozen=True)
class AnalyseCredit:
    """Un crédit à la date de l'export, en euros ; taux en fractions annuelles."""

    compte: Compte
    capital_restant: Decimal
    amortissement_mensuel: Decimal | None
    taux_annuel: Decimal | None
    mensualite: Decimal | None
    mensualite_prelevee: Decimal | None
    mois_restants: int | None
    fin_estimee: date | None
    interets_restants: Decimal | None
    capital_rembourse: Decimal

    @property
    def interets_du_mois(self) -> Decimal | None:
        """Rendre la part d'intérêts de la prochaine mensualité : capital restant dû fois taux mensuel."""
        return None if self.taux_annuel is None else self.capital_restant * self.taux_annuel / DOUZE


def analyser_credit(credit: Compte, comptes: list[Compte]) -> AnalyseCredit:
    """Rendre l'analyse du crédit ; la mensualité prélevée est cherchée dans les autres comptes par numéro de prêt."""
    amortissements = [o for o in credit.operations if o.montant > 0 and "AMORTISSEMENT" in o.libelle.upper()]
    capital = -credit.solde
    taux_mensuel = _taux_mensuel([o.montant for o in amortissements])
    dernier = amortissements[-1].montant if amortissements else None
    mensualite = mois = fin = interets = None
    if taux_mensuel is not None and dernier is not None and capital > 0:
        interets_mois = capital * taux_mensuel
        mensualite = dernier * (1 + taux_mensuel) + interets_mois
        mois = math.ceil(math.log(float(mensualite / (mensualite - interets_mois))) / math.log(1 + float(taux_mensuel)))
        fin = _ajouter_mois(credit.date_solde, mois)
        interets = mensualite * mois - capital
    return AnalyseCredit(
        compte=credit,
        capital_restant=capital,
        amortissement_mensuel=dernier,
        taux_annuel=None if taux_mensuel is None else taux_mensuel * DOUZE,
        mensualite=mensualite,
        mensualite_prelevee=_mensualite_prelevee(credit, comptes),
        mois_restants=mois,
        fin_estimee=fin,
        interets_restants=interets,
        capital_rembourse=sum((o.montant for o in amortissements), ZERO),
    )


def _taux_mensuel(amortissements: list[Decimal]) -> Decimal | None:
    """Rendre la médiane des hausses d'un mois sur l'autre de la part de capital : le taux mensuel du prêt."""
    hausses = [b / a - 1 for a, b in pairwise(amortissements) if a > 0]
    return Decimal(median(hausses)) if hausses and median(hausses) > 0 else None


def _mensualite_prelevee(credit: Compte, comptes: list[Compte]) -> Decimal | None:
    """Rendre la dernière « ECHEANCE PRET » qui porte la fin du numéro du prêt, sur un autre compte."""
    chiffres = credit.numero_masque.lstrip("*")
    echeances = [o for c in comptes if c is not credit for o in c.operations
                 if "ECHEANCE PRET" in o.libelle.upper() and chiffres and chiffres in o.libelle.replace(" ", "")]  # fmt: skip
    return -max(echeances, key=lambda o: o.jour).montant if echeances else None


def _ajouter_mois(jour: date, mois: int) -> date:
    total = jour.month - 1 + mois
    return date(jour.year + total // 12, total % 12 + 1, 1)
