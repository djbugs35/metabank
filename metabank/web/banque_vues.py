"""Comptes bancaires pour l'application : chiffres de banque.analyse en JSON prêt à afficher. MODELE § 7."""

from decimal import Decimal
from pathlib import Path

from metabank.banque import regrouper
from metabank.banque.analyse import PLAFONDS, TAUX_LIVRET_A, TAUX_LIVRET_A_DEPUIS, AnalyseCompte, analyser
from metabank.banque.budget import comparer_annees, depenses_par_mois, reperer_abonnements, suivre_objectifs
from metabank.banque.categories import classer, lire_regles, motif_suggere
from metabank.banque.modele import LIBELLES_TYPES, TYPES_COURANTS, Compte
from metabank.configuration import lire_configuration

ZERO = Decimal(0)
DOUZE = Decimal(12)


def _n(montant: Decimal | None) -> float | None:
    return None if montant is None else round(float(montant), 2)


def _t(taux: Decimal | None) -> float | None:
    return None if taux is None else round(float(taux), 6)


def _part(montant: Decimal, total: Decimal) -> float | None:
    return _t(montant / total) if total else None


def etat_banque(dossier: Path, comptes: list[Compte]) -> list[dict]:
    """Rendre une vue par compte bancaire, et une pour le foyer s'il a plusieurs comptes courants.

    Args:
        dossier: data/, pour les règles de classement des dépenses (data/categories.json).
    """
    regles = lire_regles(dossier)
    objectifs = {c: Decimal(str(m)) for c, m in lire_configuration(dossier)["objectifs"].items()}
    analyses = [analyser(compte, regles) for compte in comptes if compte.type_compte != "credit"]
    total = sum((a.compte.solde for a in analyses), ZERO)
    vues = [{**_vue(a, total), **_budget(a, regles, objectifs)} for a in analyses]
    courants = [c for c in comptes if c.type_compte in TYPES_COURANTS]
    if len(courants) > 1:
        consolide = analyser(regrouper("Foyer", courants), regles)
        foyer = {**_vue(consolide, total), **_budget(consolide, regles, objectifs)}
        vues.insert(0, {**foyer, "id": "b:foyer", "nom": "Foyer · tous les comptes courants",
                        "court": "Foyer · tous les comptes courants", "consolide": True})  # fmt: skip
    return vues


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
        "non_classees": [
            {"libelle": l, "montant": _n(m), "nombre": n, "motif": motif_suggere(l)} for l, m, n in a.non_classees
        ],
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


def _budget(a: AnalyseCompte, regles: list[tuple[str, str]], objectifs: dict[str, Decimal]) -> dict:
    """Rendre abonnements, objectifs et comparaison annuelle du compte (vides hors compte courant). MODELE § 7.13."""
    if a.compte.type_compte not in TYPES_COURANTS and a.compte.nom != "Foyer":
        return {"abonnements": [], "objectifs": [], "comparaison": [], "categories_budget": []}
    classees = classer(a.compte.operations, regles)
    par_mois = depenses_par_mois(classees)
    complets = [m.mois for m in a.mois if m.complet]
    return {
        "abonnements": [
            {"marchand": x.marchand, "categorie": x.categorie, "montant": _n(x.montant_habituel), "mois": x.mois,
             "cout_12_mois": _n(x.cout_12_mois)}
            for x in reperer_abonnements(classees, a.compte.date_solde)
        ],
        "objectifs": [
            {"categorie": o.categorie, "objectif": _n(o.objectif), "mois": o.mois, "depense_mois": _n(o.depense_mois),
             "moyenne_3_mois": _n(o.moyenne_3_mois), "depasse": o.depasse}
            for o in suivre_objectifs(par_mois, objectifs, complets)
        ],
        "comparaison": [
            {"categorie": c, "derniers_12": _n(recent), "precedents_12": _n(avant)}
            for c, recent, avant in comparer_annees(par_mois, complets)
        ],
        "categories_budget": sorted(set(par_mois) | set(objectifs)),
    }  # fmt: skip
