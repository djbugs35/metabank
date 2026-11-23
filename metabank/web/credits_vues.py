"""Crédits pour l'application : chiffres de banque.credit en JSON prêt à afficher. MODELE § 7.9."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from metabank.banque.credit import AnalyseCredit, analyser_credit, jour_echeance, projeter_credit
from metabank.banque.credit_simulation import comparer_remboursement, cout_assurance, echeancier
from metabank.banque.modele import Compte
from metabank.donnees import charger

ZERO = Decimal(0)


def _n(montant: Decimal | None) -> float | None:
    return None if montant is None else round(float(montant), 2)


def _t(taux: Decimal | None) -> float | None:
    return None if taux is None else round(float(taux), 6)


def etat_credits(comptes: list[Compte], revenus_mois_foyer: float | None, biens: dict) -> dict:
    """Rendre chaque crédit et leur synthèse ; mensualités rapportées aux revenus mensuels du foyer (fraction)."""
    analyses = [analyser_credit(c, comptes) for c in comptes if c.type_compte == "credit"]
    if not analyses:
        return {"credits": [], "synthese": None}
    revenus = Decimal(str(revenus_mois_foyer)) if revenus_mois_foyer else None
    mensualites = sum((a.mensualite_prelevee or a.mensualite or ZERO for a in analyses), ZERO)
    interets = sum((a.interets_restants or ZERO for a in analyses), ZERO)
    capital = sum((a.capital_restant for a in analyses), ZERO)
    fins = [a.fin_estimee for a in analyses if a.fin_estimee]
    return {
        "credits": [_credit(a, revenus, biens) for a in analyses],
        "synthese": {
            "capital_restant": _n(capital),
            "mensualites": _n(mensualites),
            "part_revenus": _t(mensualites / revenus) if revenus else None,
            "interets_restants": _n(interets),
            "part_interets": _t(interets / capital) if capital else None,
            "derniere_fin": max(fins).isoformat() if fins else None,
            "capital_rembourse": _n(sum((a.capital_rembourse for a in analyses), ZERO)),
        },
    }


def _credit(a: AnalyseCredit, revenus: Decimal | None, biens: dict) -> dict:
    c = a.compte
    mensualite = a.mensualite_prelevee or a.mensualite
    bien = biens.get(c.numero_masque.lstrip("*")) or {}
    valeur = Decimal(str(bien["valeur"])) if bien.get("valeur") else None
    return {
        "cle": c.numero_masque.lstrip("*"),
        "nom": c.libelle,
        "titulaire": c.titulaire,
        "date": c.date_solde.isoformat(),
        "projete_depuis": c.projete_depuis.isoformat() if c.projete_depuis else None,
        "capital_restant": _n(a.capital_restant),
        "amortissement_mensuel": _n(a.amortissement_mensuel),
        "interets_du_mois": _n(a.interets_du_mois),
        "taux_annuel": _t(a.taux_annuel),
        "mensualite": _n(a.mensualite),
        "mensualite_prelevee": _n(a.mensualite_prelevee),
        "part_revenus": _t(mensualite / revenus) if revenus and mensualite else None,
        "mois_restants": a.mois_restants,
        "fin_estimee": a.fin_estimee.isoformat() if a.fin_estimee else None,
        "interets_restants": _n(a.interets_restants),
        "capital_rembourse": _n(a.capital_rembourse),
        "bien_nom": bien.get("nom"),
        "bien_valeur": _n(valeur),
        "part_bien": _t(a.capital_restant / valeur) if valeur else None,
        **_assurance_et_echeancier(a),
    }


def _assurance_et_echeancier(a: AnalyseCredit) -> dict:
    """Rendre le coût estimé de l'assurance et le tableau d'amortissement par année. MODELE § 7.11."""
    assurance = cout_assurance(a)
    annees = []
    if a.taux_annuel is not None and a.mensualite is not None and a.capital_restant > 0:
        tableau = echeancier(
            a.capital_restant, a.taux_annuel / 12, a.mensualite, a.compte.date_solde, jour_echeance(a.compte)
        )
        annees = [{"annee": x.annee, "interets": _n(x.interets), "capital": _n(x.capital), "restant": _n(x.restant_fin)}
                  for x in tableau.annees]  # fmt: skip
    return {
        "assurance_mensuelle": _n(assurance[0]) if assurance else None,
        "assurance_restante": _n(assurance[1]) if assurance else None,
        "echeancier": annees,
    }


def simuler_remboursement(dossier: Path, saisie: dict, aujourd_hui: date | None = None) -> dict:
    """Rendre « rembourser par anticipation ou placer » pour le crédit saisi (clé = fin de son numéro). MODELE § 7.11.

    Args:
        saisie: {"cle", "montant" (euros), "rendement" (% net par an)}.

    Raises:
        ValueError: crédit inconnu, montant ou rendement hors bornes.
    """
    aujourd_hui = aujourd_hui or datetime.now().astimezone().date()
    comptes = charger(dossier).comptes
    cle = str(saisie.get("cle") or "")
    credit = next((c for c in comptes if c.type_compte == "credit" and c.numero_masque.lstrip("*") == cle), None)
    if credit is None:
        raise ValueError("crédit inconnu")
    try:
        montant, rendement = Decimal(str(saisie.get("montant") or 0)), Decimal(str(saisie.get("rendement") or 0))
    except InvalidOperation as erreur:
        raise ValueError("montant et rendement : nombres attendus") from erreur
    if not Decimal(-10) <= rendement <= Decimal(20):
        raise ValueError("rendement entre -10 et 20 % par an")
    analyse = analyser_credit(projeter_credit(credit, aujourd_hui), comptes)
    r = comparer_remboursement(analyse, montant, rendement / 100, aujourd_hui)
    return {
        "montant": _n(r.montant), "interets_economises": _n(r.interets_economises), "mois_gagnes": r.mois_gagnes,
        "indemnites_max": _n(r.indemnites_max), "patrimoine_si_rembourse": _n(r.patrimoine_si_rembourse),
        "patrimoine_si_place": _n(r.patrimoine_si_place), "ecart": _n(r.ecart),
        "fin_actuelle": analyse.fin_estimee.isoformat() if analyse.fin_estimee else None,
    }  # fmt: skip
