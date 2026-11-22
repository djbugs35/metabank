"""Crédits pour l'application : chiffres de banque.credit en JSON prêt à afficher. MODELE § 7.9."""

from decimal import Decimal

from metabank.banque.credit import AnalyseCredit, analyser_credit
from metabank.banque.modele import Compte

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
    }
