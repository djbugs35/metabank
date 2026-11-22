"""Comptes bancaires pour l'application : chiffres de banque.analyse en JSON prêt à afficher. MODELE § 7."""

from decimal import Decimal
from pathlib import Path

from metabank.banque import lire_comptes
from metabank.banque.analyse import PLAFONDS, TAUX_LIVRET_A, TAUX_LIVRET_A_DEPUIS, AnalyseCompte, analyser
from metabank.banque.categories import lire_regles
from metabank.banque.modele import LIBELLES_TYPES

ZERO = Decimal(0)
DOUZE = Decimal(12)


def _n(montant: Decimal | None) -> float | None:
    return None if montant is None else round(float(montant), 2)


def _t(taux: Decimal | None) -> float | None:
    return None if taux is None else round(float(taux), 6)


def _part(montant: Decimal, total: Decimal) -> float | None:
    return _t(montant / total) if total else None


def etat_banque(dossier: Path) -> tuple[list[dict], list[str]]:
    """Rendre une vue par compte bancaire, et les erreurs de lecture des exports."""
    comptes, erreurs = lire_comptes(dossier)
    regles = lire_regles(dossier)
    analyses = [analyser(compte, regles) for compte in comptes]
    total = sum((a.compte.solde for a in analyses), ZERO)
    return [_vue(a, total) for a in analyses], erreurs


def _vue(a: AnalyseCompte, total_liquidites: Decimal) -> dict:
    """Rendre une vue : montants en euros, taux en fractions ; flux par mois = total de la période / nombre de mois."""
    c = a.compte

    def par_mois(montant: Decimal) -> Decimal:
        return montant / a.nombre_mois

    return {
        "id": f"b:{c.titulaire}:{c.type_compte}:{c.numero_masque}",
        "nom": c.libelle,
        "court": f"{c.titulaire} · {LIBELLES_TYPES.get(c.type_compte, c.type_compte)} {c.banque}",
        "titulaire": c.titulaire,
        "type": c.type_compte,
        "numero_masque": c.numero_masque,
        "solde": _n(c.solde),
        "date_solde": c.date_solde.isoformat(),
        "debut": a.debut.isoformat(),
        "nombre_mois": _n(a.nombre_mois),
        "part_liquidites": _part(c.solde, total_liquidites),
        "solde_moyen": _n(a.solde_moyen),
        "revenus_mois": _n(par_mois(a.revenus)),
        "depenses_mois": _n(par_mois(a.depenses)),
        "epargne_mois": _n(par_mois(a.epargne)),
        "interne_mois": _n(par_mois(a.interne)),
        "part_depenses": _part(a.depenses, a.revenus),
        "part_epargne": _part(a.epargne, a.revenus),
        "taux_epargne": _t(a.taux_epargne),
        "frais_an": _n(a.frais_bancaires / a.nombre_mois * DOUZE),
        "part_frais": _part(a.frais_bancaires, a.revenus),
        "argent_qui_dort": _n(a.argent_qui_dort),
        "part_qui_dort": _part(a.argent_qui_dort, a.solde_moyen),
        "coussin": _n(a.coussin),
        "manque_a_gagner": _n(a.manque_a_gagner),
        "taux_livret_a": _t(TAUX_LIVRET_A),
        "plafond": _n(PLAFONDS.get(c.type_compte)),
        "part_plafond": _part(c.solde, PLAFONDS[c.type_compte]) if c.type_compte in PLAFONDS else None,
        "taux_livret_a_depuis": TAUX_LIVRET_A_DEPUIS.isoformat(),
        "mois": [
            {
                "mois": m.mois,
                "solde_fin": _n(m.solde_fin),
                "revenus": _n(m.revenus),
                "depenses": _n(m.depenses),
                "epargne": _n(m.epargne),
                "interne": _n(m.interne),
                "complet": m.complet,
            }
            for m in a.mois
        ],
        "categories": [
            {"nom": nom, "montant": _n(m), "part": _part(m, a.depenses)} for nom, m in a.depenses_par_categorie
        ],
        "frais_detail": [{"libelle": l, "montant": _n(m)} for l, m in a.detail_frais],
        "non_classees": [{"libelle": l, "montant": _n(m), "nombre": n} for l, m, n in a.non_classees],
        "interets": [
            {
                "annee": i.annee,
                "interets": _n(i.interets),
                "solde_moyen": _n(i.solde_moyen),
                "taux": _t(i.taux_obtenu),
                "taux_reglemente": _t(i.taux_reglemente_moyen),
                "solde_suppose": i.solde_moyen_suppose,
                "estimation": _n(i.estimation),
            }
            for i in a.interets_par_an
        ],
        "anomalies": list(c.anomalies),
    }
