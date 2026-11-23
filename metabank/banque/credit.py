"""Crédits immobiliers : capital restant dû, taux, mensualité, fin et intérêts restants estimés. MODELE § 7.9.

L'export BNP d'un prêt donne le capital restant dû (solde négatif) et une ligne « AMORTISSEMENT PRET » par mois :
la part de capital remboursée. Dans un prêt à mensualité constante, cette part croît chaque mois du taux mensuel ;
on en déduit le taux, puis la mensualité, la durée restante et les intérêts encore à payer.
"""

import calendar
import math
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from itertools import pairwise
from statistics import median

from metabank.banque.modele import Compte, Operation

ZERO = Decimal(0)
DOUZE = Decimal(12)
CENTIME = Decimal("0.01")
LIBELLE_PROJECTION = "AMORTISSEMENT PRET (projection metabank)"


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


def projeter_credit(credit: Compte, aujourd_hui: date) -> Compte:
    """Rendre le crédit avancé jusqu'à la dernière échéance passée, ou tel quel s'il n'y a rien à projeter. MODELE § 7.10.

    Chaque échéance passée depuis l'export ajoute une ligne d'amortissement marquée « projection metabank » : la part
    de capital croît du taux mensuel i, et le capital restant dû baisse d'autant (en euros, au centime).
    """
    amortissements = [o for o in credit.operations if o.montant > 0 and "AMORTISSEMENT" in o.libelle.upper()]
    taux_mensuel = _taux_mensuel([o.montant for o in amortissements])
    if taux_mensuel is None or credit.solde >= 0:
        return credit
    capital, part = -credit.solde, amortissements[-1].montant
    projetees = []
    for echeance in _echeances(credit.date_solde, aujourd_hui, amortissements[-1].jour.day):
        if capital <= 0:
            break
        part = min((part * (1 + taux_mensuel)).quantize(CENTIME), capital)
        capital -= part
        projetees.append(Operation(echeance, "", "", LIBELLE_PROJECTION, part))
    if not projetees:
        return credit
    return replace(credit, solde=-capital, date_solde=projetees[-1].jour, operations=credit.operations + tuple(projetees),
                   projete_depuis=credit.date_solde)  # fmt: skip


def _echeances(apres: date, jusqu_a: date, jour: int) -> list[date]:
    """Rendre les dates d'échéance (ce jour du mois, ou le dernier jour d'un mois plus court) dans ]apres, jusqu_a]."""
    echeances: list[date] = []
    annee, mois = apres.year, apres.month
    while True:
        dernier = calendar.monthrange(annee, mois)[1]
        echeance = date(annee, mois, min(jour, dernier))
        if echeance > jusqu_a:
            return echeances
        if echeance > apres:
            echeances.append(echeance)
        annee, mois = (annee + 1, 1) if mois == 12 else (annee, mois + 1)


def jour_echeance(credit: Compte) -> int:
    """Rendre le jour du mois des échéances : celui de la dernière ligne d'amortissement, sinon celui de l'export."""
    amortissements = [o for o in credit.operations if o.montant > 0 and "AMORTISSEMENT" in o.libelle.upper()]
    return amortissements[-1].jour.day if amortissements else credit.date_solde.day


def echeances_a_venir(apres: date, jour: int, nombre: int) -> list[date]:
    """Rendre les nombre prochaines échéances après la date (ce jour du mois, ou le dernier d'un mois court)."""
    echeances: list[date] = []
    annee, mois = apres.year, apres.month
    while len(echeances) < nombre:
        echeance = date(annee, mois, min(jour, calendar.monthrange(annee, mois)[1]))
        if echeance > apres:
            echeances.append(echeance)
        annee, mois = (annee + 1, 1) if mois == 12 else (annee, mois + 1)
    return echeances


def _mensualite_prelevee(credit: Compte, comptes: list[Compte]) -> Decimal | None:
    """Rendre la dernière « ECHEANCE PRET » qui porte la fin du numéro du prêt, sur un autre compte."""
    chiffres = credit.numero_masque.lstrip("*")
    echeances = [o for c in comptes if c is not credit for o in c.operations
                 if "ECHEANCE PRET" in o.libelle.upper() and chiffres and chiffres in o.libelle.replace(" ", "")]  # fmt: skip
    return -max(echeances, key=lambda o: o.jour).montant if echeances else None


def _ajouter_mois(jour: date, mois: int) -> date:
    total = jour.month - 1 + mois
    return date(jour.year + total // 12, total % 12 + 1, 1)
