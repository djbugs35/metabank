"""Crédits : tableau d'amortissement, remboursement anticipé ou placement, assurance emprunteur. MODELE § 7.11.

Montants en euros, taux en fractions. Aucun calcul ici ne décide : il chiffre deux hypothèses pour le titulaire.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from metabank.banque.credit import AnalyseCredit, echeances_a_venir, jour_echeance

ZERO = Decimal(0)
CENTIME = Decimal("0.01")
MOIS_IRA = 6
PLAFOND_IRA = Decimal("0.03")
MOIS_MAX = 600


@dataclass(frozen=True)
class AnneeAmortissement:
    """Une année civile du tableau d'amortissement, en euros."""

    annee: int
    interets: Decimal
    capital: Decimal
    restant_fin: Decimal


@dataclass(frozen=True)
class Echeancier:
    """Ce qui reste à payer : nombre de mois, intérêts totaux, et le détail par année."""

    mois: int
    interets: Decimal
    annees: tuple[AnneeAmortissement, ...]


@dataclass(frozen=True)
class RemboursementAnticipe:
    """Rembourser R aujourd'hui ou le placer, comparés à la date de fin actuelle du prêt. MODELE § 7.11."""

    montant: Decimal
    interets_economises: Decimal
    mois_gagnes: int
    indemnites_max: Decimal
    patrimoine_si_rembourse: Decimal
    patrimoine_si_place: Decimal

    @property
    def ecart(self) -> Decimal:
        """Rendre rembourser moins placer, en euros : positif, rembourser laisse plus à la fin du prêt actuel."""
        return self.patrimoine_si_rembourse - self.patrimoine_si_place


def echeancier(capital: Decimal, taux_mensuel: Decimal, mensualite: Decimal, depuis: date, jour: int) -> Echeancier:
    """Rendre le tableau d'amortissement à mensualité constante, du mois suivant depuis jusqu'au capital nul.

    Raises:
        ValueError: mensualité qui ne couvre pas les intérêts (le prêt ne finirait jamais).
    """
    if mensualite <= capital * taux_mensuel:
        raise ValueError("mensualité inférieure aux intérêts du mois : tableau impossible")
    par_annee: dict[int, list[Decimal]] = {}
    total, mois = ZERO, 0
    for echeance in echeances_a_venir(depuis, jour, MOIS_MAX):
        if capital <= 0:
            break
        interets = (capital * taux_mensuel).quantize(CENTIME)
        rembourse = min(mensualite - interets, capital)
        capital -= rembourse
        total += interets
        mois += 1
        ligne = par_annee.setdefault(echeance.year, [ZERO, ZERO, ZERO])
        ligne[0], ligne[1], ligne[2] = ligne[0] + interets, ligne[1] + rembourse, capital
    return Echeancier(mois, total, tuple(AnneeAmortissement(a, *v) for a, v in sorted(par_annee.items())))


def comparer_remboursement(
    analyse: AnalyseCredit, montant: Decimal, rendement_annuel: Decimal, aujourd_hui: date
) -> RemboursementAnticipe:
    """Rendre la comparaison « rembourser montant aujourd'hui » contre « le placer au rendement net donné ».

    Raises:
        ValueError: crédit sans taux ni mensualité estimés, ou montant hors de ]0, capital restant dû].
    """
    if analyse.taux_annuel is None or analyse.mensualite is None:
        raise ValueError("taux ou mensualité du crédit inconnus : comparaison impossible")
    capital = analyse.capital_restant
    if not ZERO < montant <= capital:
        raise ValueError("montant à rembourser entre 0 et le capital restant dû")
    i, p = analyse.taux_annuel / 12, analyse.mensualite
    jour = jour_echeance(analyse.compte)
    avant = echeancier(capital, i, p, aujourd_hui, jour)
    apres = echeancier(capital - montant, i, p, aujourd_hui, jour) if montant < capital else Echeancier(0, ZERO, ())
    r = (1 + rendement_annuel) ** (Decimal(1) / 12) - 1
    ira = min(montant * i * MOIS_IRA, capital * PLAFOND_IRA).quantize(CENTIME)
    liberees = sum((p * (1 + r) ** (avant.mois - k) for k in range(apres.mois + 1, avant.mois + 1)), ZERO)
    return RemboursementAnticipe(
        montant=montant,
        interets_economises=avant.interets - apres.interets,
        mois_gagnes=avant.mois - apres.mois,
        indemnites_max=ira,
        patrimoine_si_rembourse=(liberees - ira * (1 + r) ** avant.mois).quantize(CENTIME),
        patrimoine_si_place=(montant * (1 + r) ** avant.mois).quantize(CENTIME),
    )


def cout_assurance(analyse: AnalyseCredit) -> tuple[Decimal, Decimal] | None:
    """Rendre (coût mensuel, coût restant) estimés de l'assurance emprunteur en euros, ou None s'ils sont inconnus."""
    if analyse.mensualite_prelevee is None or analyse.mensualite is None or analyse.mois_restants is None:
        return None
    mensuel = analyse.mensualite_prelevee - analyse.mensualite
    return (mensuel, mensuel * analyse.mois_restants) if mensuel > 0 else None
