"""Bien locatif : loyers, charges, échéances du prêt ; rendement brut et net, trésorerie mensuelle. MODELE § 7.12.

Montants en euros par an (trésorerie : par mois), rendements en fractions de la valeur saisie du bien.
Avant impôts et prélèvements sociaux.
"""

from dataclasses import dataclass
from decimal import Decimal

from metabank.banque.analyse import AnalyseCompte
from metabank.banque.credit import AnalyseCredit

ZERO = Decimal(0)
DOUZE = Decimal(12)
CATEGORIE_CREDITS = "Crédits"


@dataclass(frozen=True)
class BienLocatif:
    """Le bien locatif sur un an ; rendements None sans valeur saisie, intérêts None sans crédit estimé."""

    nom: str
    valeur: Decimal | None
    loyers: Decimal
    charges: Decimal
    echeances: Decimal
    interets: Decimal | None
    mois_couverts: Decimal

    def _part(self, montant: Decimal | None) -> Decimal | None:
        return None if montant is None or not self.valeur else montant / self.valeur

    @property
    def rendement_brut(self) -> Decimal | None:
        """Rendre loyers / valeur du bien."""
        return self._part(self.loyers)

    @property
    def rendement_net(self) -> Decimal | None:
        """Rendre (loyers - charges) / valeur du bien."""
        return self._part(self.loyers - self.charges)

    @property
    def rendement_apres_interets(self) -> Decimal | None:
        """Rendre (loyers - charges - intérêts d'emprunt) / valeur du bien."""
        return None if self.interets is None else self._part(self.loyers - self.charges - self.interets)

    @property
    def tresorerie_mensuelle(self) -> Decimal:
        """Rendre (loyers - charges - échéances) / 12 : ce que le bien rapporte (ou coûte, négatif) chaque mois."""
        return (self.loyers - self.charges - self.echeances) / DOUZE


def analyser_locatif(
    nom: str, comptes: list[AnalyseCompte], credit: AnalyseCredit | None, valeur: Decimal | None
) -> BienLocatif:
    """Rendre le bien locatif sur un an, depuis les analyses de ses comptes locatifs. MODELE § 7.12."""
    loyers = charges = echeances = ZERO
    mois = ZERO
    for a in comptes:
        annuel = DOUZE / a.nombre_mois
        credits = sum((m for c, m in a.depenses_par_categorie if c == CATEGORIE_CREDITS), ZERO)
        loyers += a.revenus * annuel
        echeances += credits * annuel
        charges += (a.depenses - credits) * annuel
        mois = max(mois, a.nombre_mois)
    return BienLocatif(nom, valeur, loyers, charges, echeances, _interets_annuels(credit), mois)


def _interets_annuels(credit: AnalyseCredit | None) -> Decimal | None:
    """Rendre les intérêts des 12 prochaines échéances du crédit (MODELE § 7.11), ou None s'ils sont inconnus."""
    if credit is None or credit.taux_annuel is None or credit.mensualite is None:
        return None
    capital, taux, total = credit.capital_restant, credit.taux_annuel / DOUZE, ZERO
    for _ in range(12):
        if capital <= 0:
            break
        interets = capital * taux
        total += interets
        capital -= min(credit.mensualite - interets, capital)
    return total
