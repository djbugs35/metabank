"""Onglet Allocation : répartition, concentration, cible et versements de rééquilibrage, en JSON. MODELE § 13."""

from decimal import Decimal, InvalidOperation
from pathlib import Path

from metabank.allocation import CLASSES, concentrations, derives, positions, reequilibrer, repartir
from metabank.arbitrage import simuler_arbitrage
from metabank.banque.modele import TYPES_COURANTS, TYPES_LIVRETS
from metabank.configuration import ecrire_allocation, lire_configuration
from metabank.corrections import appliquer_verifications
from metabank.donnees import charger

ZERO = Decimal(0)
CENT = Decimal(100)


def _n(montant: Decimal) -> float:
    return round(float(montant), 2)


def etat_allocation(dossier: Path, titulaire: str = "") -> dict:
    """Rendre l'allocation du foyer, ou d'une personne si titulaire est donné (montants en euros, parts en fractions)."""
    donnees = charger(dossier)
    configuration = lire_configuration(dossier)
    garder = lambda nom: not titulaire or nom == titulaire
    releves = [r for r in appliquer_verifications(donnees.releves, dossier) if garder(r.titulaire)]
    supports = positions(releves, configuration["classes"])
    comptes = [c for c in donnees.comptes if garder(c.titulaire)]
    liquidites = {
        "Livrets": sum((c.solde for c in comptes if c.type_compte in TYPES_LIVRETS), ZERO),
        "Comptes courants": sum((c.solde for c in comptes if c.type_compte in TYPES_COURANTS), ZERO),
    }
    repartition = repartir(supports, liquidites)
    total = sum((m for _, m, _ in repartition), ZERO)
    cible = {c: Decimal(str(p)) / CENT for c, p in configuration["cible"].items()}
    valeurs = {c: sum((p.valeur for p in supports if p.classe == c), ZERO) for c in CLASSES}
    total_supports = sum(valeurs.values(), ZERO)
    a_verser = reequilibrer(valeurs, cible)
    return {
        "titulaires": sorted({r.titulaire for r in donnees.releves} | {c.titulaire for c in donnees.comptes}),
        "titulaire": titulaire,
        "total": _n(total),
        "repartition": [
            {"nom": nom, "montant": _n(m), "part": round(float(part), 6), "cible": configuration["cible"].get(nom),
             "part_supports": round(float(m / total_supports), 6) if nom in valeurs and total_supports else None}
            for nom, m, part in repartition
        ],
        "concentrations": [{"libelle": p.libelle, "contrat": p.contrat, "part": round(float(p.valeur / total), 6)}
                           for p in concentrations(supports, total)],
        "a_verser": {c: _n(m) for c, m in a_verser.items()},
        "derives": {c: round(float(e), 6) for c, e in derives(
            {c: v / total_supports for c, v in valeurs.items()} if total_supports else {}, cible).items()},
        "total_a_verser": _n(sum(a_verser.values(), ZERO)),
        "positions": [
            {"cle": p.cle, "libelle": p.libelle, "titulaire": p.titulaire, "contrat": p.contrat, "classe": p.classe,
             "choisie": p.classe_choisie, "valeur": _n(p.valeur),
             "frais_totaux": float(p.frais_totaux) if p.frais_totaux is not None else None}
            for p in supports
        ],
        "classes": CLASSES,
        "cible": configuration["cible"],
        "par_contrat": _par_contrat(supports),
    }  # fmt: skip


def enregistrer_allocation(dossier: Path, saisie: dict) -> dict:
    """Rendre l'allocation du foyer après avoir enregistré classes choisies et cible.

    Raises:
        ConfigurationInvalide: classe inconnue ou cible dont la somme n'est pas 100 %.
    """
    ecrire_allocation(dossier, saisie.get("classes") or {}, saisie.get("cible") or {})
    return etat_allocation(dossier, str(saisie.get("titulaire") or ""))


def simuler_arbitrage_saisi(_dossier: Path, saisie: dict) -> dict:
    """Rendre garder et arbitrer année par année (euros), l'écart, le coût immédiat et le point mort. MODELE § 14.

    Raises:
        ValueError: nombre illisible ou hors bornes.
    """
    bornes = {"montant": (0, 10_000_000), "frais_source": (0, 10), "frais_cible": (0, 10), "frais_arbitrage": (0, 5),
              "rendement": (-10, 20), "horizon": (1, 40)}  # fmt: skip
    valeurs = {}
    for cle, (mini, maxi) in bornes.items():
        try:
            valeur = Decimal(str(saisie.get(cle, "")))
        except InvalidOperation as erreur:
            raise ValueError(f"{cle} : nombre attendu") from erreur
        if not mini <= valeur <= maxi:
            raise ValueError(f"{cle} : entre {mini} et {maxi}")
        valeurs[cle] = valeur
    a = simuler_arbitrage(valeurs["montant"], valeurs["frais_source"], valeurs["frais_cible"],
                          valeurs["frais_arbitrage"], valeurs["rendement"], int(valeurs["horizon"]))  # fmt: skip
    return {"garder": [_n(v) for v in a.garder], "arbitrer": [_n(v) for v in a.arbitrer], "ecart": _n(a.ecart),
            "cout_immediat": _n(a.cout_immediat), "point_mort": a.point_mort}  # fmt: skip


def _par_contrat(supports: list) -> list[dict]:
    """Rendre la répartition par classe de chaque contrat (montants en euros, parts du contrat en fractions)."""
    contrats: dict[tuple[str, str], list] = {}
    for p in supports:
        contrats.setdefault((p.titulaire, p.contrat), []).append(p)
    resultat = []
    for (titulaire, contrat), fonds in contrats.items():
        total = sum((p.valeur for p in fonds), ZERO)
        classes = {c: sum((p.valeur for p in fonds if p.classe == c), ZERO) for c in CLASSES}
        resultat.append({"titulaire": titulaire, "contrat": contrat, "total": _n(total), "classes": [
            {"classe": c, "montant": _n(m), "part": round(float(m / total), 6) if total else None}
            for c, m in classes.items() if m
        ]})  # fmt: skip
    return resultat
