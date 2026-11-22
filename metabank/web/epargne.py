"""Synthèse de l'épargne disponible (Livret A, LDD) du foyer et de chaque personne. MODELE § 7.8."""

from decimal import Decimal

from metabank.banque.analyse import PLAFONDS, AnalyseCompte, analyser
from metabank.banque.modele import TYPES_LIVRETS, Compte

ZERO = Decimal(0)


def syntheses_epargne(comptes: list[Compte], totaux_patrimoine: dict[str, float]) -> dict[str, dict]:
    """Rendre la synthèse des livrets pour « foyer » et chaque « p:<prénom> » qui en a, en euros et en fractions."""
    analyses = [analyser(c, []) for c in comptes if c.type_compte in TYPES_LIVRETS]
    if not analyses:
        return {}
    groupes = {"foyer": analyses}
    for titulaire in sorted({a.compte.titulaire for a in analyses}):
        groupes[f"p:{titulaire}"] = [a for a in analyses if a.compte.titulaire == titulaire]
    return {cle: _synthese(groupe, totaux_patrimoine.get(cle)) for cle, groupe in groupes.items()}


def _n(montant: Decimal | None) -> float | None:
    return None if montant is None else round(float(montant), 2)


def _t(numerateur: Decimal | None, denominateur: Decimal | None) -> float | None:
    if numerateur is None or not denominateur:
        return None
    return round(float(numerateur / denominateur), 6)


def _synthese(analyses: list[AnalyseCompte], total_patrimoine: float | None) -> dict:
    """Rendre total, intérêts de la dernière année versée, intérêts attendus et remplissage des plafonds."""
    solde = sum((a.compte.solde for a in analyses), ZERO)
    versees = [i for a in analyses for i in a.interets_par_an if i.interets is not None]
    annee = max((i.annee for i in versees), default=None)
    de_l_annee = [i for i in versees if i.annee == annee]
    interets = sum((i.interets for i in de_l_annee if i.interets is not None), ZERO)
    solde_moyen = sum((i.solde_moyen for i in de_l_annee), ZERO)
    attendus = [i for a in analyses for i in a.interets_par_an if i.estimation is not None]
    plafond = sum((PLAFONDS.get(a.compte.type_compte, ZERO) for a in analyses), ZERO)
    rempli = sum((min(a.compte.solde, PLAFONDS.get(a.compte.type_compte, ZERO)) for a in analyses), ZERO)
    return {
        "solde": _n(solde),
        "nombre": len(analyses),
        "part_patrimoine": _t(solde, Decimal(str(total_patrimoine)) if total_patrimoine else None),
        "annee_interets": annee,
        "interets": _n(interets) if annee else None,
        "taux_obtenu": _t(interets, solde_moyen) if annee else None,
        "taux_reglemente": _t(de_l_annee[0].taux_reglemente_moyen, Decimal(1)) if de_l_annee else None,
        "annee_attendue": attendus[0].annee if attendus else None,
        "attendus": _n(sum((i.estimation for i in attendus if i.estimation is not None), ZERO)) if attendus else None,
        "taux_attendu": _t(attendus[0].taux_reglemente_moyen, Decimal(1)) if attendus else None,
        "plafond": _n(plafond),
        "part_plafond": _t(rempli, plafond),
        "versements_possibles": _n(plafond - rempli),
    }
