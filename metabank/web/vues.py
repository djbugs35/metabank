"""Chiffres de l'application web : foyer, personnes et contrats, en JSON prêt à afficher.

Les montants partent en nombres arrondis au centime et les taux en fractions (0,028 = 2,8 %) : ils viennent tous du
code testé (synthese, frais) ; la page ne fait que les mettre en forme.
"""

from datetime import date, datetime
from decimal import Decimal

from metabank.banque.analyse import analyser
from metabank.banque.categories import lire_regles
from metabank.banque.credit import analyser_credit, projeter_credit
from metabank.banque.locatif import analyser_locatif
from metabank.base.archives import DOSSIERS_RESERVES
from metabank.bilan import BilanContrat, faire_bilans
from metabank.configuration import lire_configuration
from metabank.corrections import appliquer_verifications, cle_contrat, lire_corrections, lire_ouvertures
from metabank.depot_unique import dossier_depot
from metabank.donnees import charger
from metabank.fiscalite import echeances
from metabank.frais import AnalyseFrais, analyser_frais
from metabank.frais_historique import historiques_frais
from metabank.historique import historique_patrimoine
from metabank.rapport import nom_contrat
from metabank.reperes import SOURCES, reperes_de
from metabank.synthese import Synthese, synthetiser
from metabank.web.banque_vues import etat_banque
from metabank.web.credits_vues import etat_credits
from metabank.web.epargne import syntheses_epargne
from metabank.web.patrimoine import patrimoines

ZERO = Decimal(0)


def etat(dossier, aujourd_hui: date | None = None) -> dict:
    """Rendre tout ce qu'affiche l'application : vues, fonds, points d'attention, contrats et corrections.

    Args:
        aujourd_hui: date des projections (capital des crédits, MODELE § 7.10) ; par défaut, la date locale.
    """
    aujourd_hui = aujourd_hui or datetime.now().astimezone().date()
    donnees = charger(dossier)
    releves = appliquer_verifications(donnees.releves, dossier)
    bilans = faire_bilans(releves, lire_ouvertures(dossier))
    historiques = historiques_frais(releves)
    analyses = analyser_frais(releves)
    foyer = synthetiser("Foyer", bilans, historiques)
    comptes = [projeter_credit(c, aujourd_hui) if c.type_compte == "credit" else c for c in donnees.comptes]
    banque = etat_banque(dossier, comptes)
    corrections = lire_corrections(dossier)
    patrimoine = patrimoines(bilans, comptes, corrections["biens"])
    historique = _historique(releves, donnees.comptes, corrections["biens"], aujourd_hui, patrimoine)
    vues = [_vue("foyer", "foyer", None, foyer, foyer)]
    for titulaire in sorted({b.titulaire for b in bilans} | {c.titulaire for c in comptes}):
        des_siens = [b for b in bilans if b.titulaire == titulaire]
        vues.append(_vue(f"p:{titulaire}", "personne", None, synthetiser(titulaire, des_siens, historiques), foyer))
        for bilan in sorted(des_siens, key=lambda b: -b.valeur):
            synthese = synthetiser(nom_contrat(bilan), [bilan], historiques)
            vue = _vue(f"c:{cle_contrat(bilan.numero)}", "contrat", f"p:{titulaire}", synthese, foyer)
            vues.append({**vue, "court": f"{bilan.titulaire} · {bilan.produit}"})
    return {
        "vues": vues,
        "contrats": [_contrat(b, analyses) for b in bilans],
        "fonds": _fonds(analyses),
        "points": _points(bilans),
        "erreurs": donnees.erreurs,
        "banque": banque,
        "patrimoine": patrimoine,
        "historique": historique,
        "reperes": _reperes(vues),
        "locatif": _locatif(dossier, comptes, corrections["biens"]),
        "echeances": [
            {
                "jour": e.jour.isoformat() if e.jour else None,
                "titulaire": e.titulaire,
                "contrat": e.contrat,
                "quoi": e.quoi,
                "detail": e.detail,
            }
            for e in echeances(bilans, aujourd_hui, lire_configuration(dossier)["parametres"]["imposition_commune"])
        ],
        "sources_reperes": SOURCES,
        "epargne": syntheses_epargne(comptes, {cle: p["total"] for cle, p in patrimoine.items()}),
        "corrections": corrections,
        "dossier_depot": str(dossier_depot(dossier, lire_configuration(dossier))),
        **_credits(comptes, banque, corrections["biens"]),
        "titulaires": sorted(
            {
                p.name
                for p in dossier.iterdir()
                if p.is_dir() and not p.name.startswith(".") and p.name not in DOSSIERS_RESERVES
            }
        )
        if dossier.exists()
        else [],
    }


def _nombre(montant: Decimal | None) -> float | None:
    return None if montant is None else round(float(montant), 2)


def _taux(taux: Decimal | None) -> float | None:
    return None if taux is None else round(float(taux), 6)


def _division(numerateur: Decimal, denominateur: Decimal) -> float | None:
    return _taux(numerateur / denominateur) if denominateur else None


def _vue(ident: str, niveau: str, parent: str | None, s: Synthese, foyer: Synthese) -> dict:
    """Rendre une vue : les quatre chiffres de la période et les années, en euros et en taux. MODELE § 6."""
    verse_suivi = sum((a.verse for a in s.annees), ZERO)
    frais_connus = bool(s.annees and verse_suivi)
    return {
        "id": ident,
        "niveau": niveau,
        "parent": parent,
        "nom": s.nom,
        "verse": _nombre(s.verse),
        "ecart_verse": _nombre(s.ecart_verse) if abs(s.ecart_verse) > 1 else None,
        "valeur": _nombre(s.valeur),
        "gain": _nombre(s.gain),
        "frais": _nombre(s.frais_cumules) if frais_connus else None,
        "part_verse": _division(s.verse, foyer.verse),
        "part_valeur": _division(s.valeur, foyer.valeur),
        "gain_taux": _division(s.gain, s.verse),
        "gain_par_an": _taux(s.rendement_annualise),
        "frais_taux": _division(s.frais_cumules, verse_suivi) if frais_connus else None,
        "frais_par_an": _taux(s.frais_par_an) if frais_connus else None,
        "frais_sur_partie": bool(s.sans_historique) and frais_connus,
        "sans_historique": list(s.sans_historique),
        "valeur_sans_historique": _nombre(s.valeur_sans_historique),
        "verse_sans_historique": _nombre(s.verse_sans_historique),
        "gain_sans_historique": _nombre(s.gain_sans_historique),
        "tableau": [
            {
                "nom": ligne.nom,
                "niveau": ligne.niveau,
                "annees": {
                    str(an): {
                        "verse": _nombre(c.verse),
                        "gain_avant_frais": _nombre(c.gain_avant_frais),
                        "frais": _nombre(c.frais),
                        "gain": _nombre(c.gain),
                        "valeur": _nombre(c.valeur),
                    }
                    for an, c in ligne.annees.items()
                },
                "valeur_actuelle": _nombre(ligne.valeur_actuelle),
                "depuis_ouverture": {
                    "verse": _nombre(ligne.verse),
                    "gain_avant_frais": None if ligne.gain_avant_frais is None else _nombre(ligne.gain_avant_frais),
                    "frais": None if ligne.frais is None else _nombre(ligne.frais),
                    "ecart": _nombre(ligne.ecart),
                    "gain": _nombre(ligne.gain),
                    "valeur": _nombre(ligne.valeur_actuelle),
                },
            }
            for ligne in s.tableau
        ],
        "progression": [
            {
                "annee": p.annee,
                "valeur": _nombre(p.valeur),
                "variation": _nombre(p.variation),
                "verse_cumule": _nombre(p.verse_cumule),
                "gain_cumule": _nombre(p.gain_cumule),
                "verse_net_annee": _nombre(p.verse_net_annee),
                "gain_annee": _nombre(p.gain_annee),
                "en_cours_au": p.en_cours_au.isoformat() if p.en_cours_au else None,
            }
            for p in s.progression
        ],
        "annees": [
            {
                "annee": a.annee,
                "verse": _nombre(a.verse),
                "gain": _nombre(a.gain),
                "frais": _nombre(a.frais),
                "capital": _nombre(a.capital),
                "gain_taux": _taux(a.rendement),
                "frais_taux": _taux(a.rendement_frais),
                "en_cours_au": a.en_cours_au.isoformat() if a.en_cours_au else None,
            }
            for a in s.annees
        ],
    }


def _contrat(bilan: BilanContrat, analyses: list[AnalyseFrais]) -> dict:
    """Rendre ce que les onglets Corrections et Simulation savent d'un contrat (sans son numéro complet)."""
    analyse = next((a for a in analyses if a.titulaire == bilan.titulaire and a.produit == bilan.produit), None)
    return {
        "cle": cle_contrat(bilan.numero),
        "nom": nom_contrat(bilan),
        "titulaire": bilan.titulaire,
        "numero_masque": bilan.numero_masque,
        "annees": [a.annee for a in bilan.annees],
        "date_valeur": bilan.date_valeur.isoformat(),
        "valeur": _nombre(bilan.valeur),
        "encours_frais_connus": _nombre(analyse.encours_connu) if analyse else None,
        "taux_frais": _taux(analyse.taux_moyen / 100) if analyse and analyse.taux_moyen is not None else None,
        "taux_frais_fonds_moins_chers": _taux(_taux_cible(analyse)) if analyse else None,
        "produit": bilan.produit,
        "cout_frais_annuel": _nombre(analyse.cout_total) if analyse else None,
        "retrocessions_annuelles": _nombre(analyse.retrocessions) if analyse else None,
    }


def _taux_cible(analyse: AnalyseFrais) -> Decimal | None:
    """Rendre le taux moyen si chaque fonds coûtait au plus la cible (0,20 %). MODELE § 4.2."""
    if analyse.taux_moyen is None or not analyse.encours_connu:
        return None
    return (analyse.taux_moyen - analyse.economie_annuelle / analyse.encours_connu * 100) / 100


def _fonds(analyses: list[AnalyseFrais]) -> list[dict]:
    lignes = [
        {
            "fonds": ligne.libelle,
            "isin": ligne.isin,
            "contrat": f"{analyse.titulaire} · {analyse.produit}",
            "valeur": _nombre(ligne.valeur),
            "frais_fonds": _taux(None if ligne.frais_support is None else ligne.frais_support / 100),
            "retrocessions": _taux(None if ligne.retrocessions is None else ligne.retrocessions / 100),
            "frais_contrat": _taux(None if ligne.frais_contrat is None else ligne.frais_contrat / 100),
            "frais_totaux": _taux(None if ligne.frais_totaux is None else ligne.frais_totaux / 100),
            "cout_annuel": _nombre(ligne.cout_annuel),
            "performance_nette": _taux(None if ligne.performance_finale is None else ligne.performance_finale / 100),
        }
        for analyse in analyses
        for ligne in analyse.lignes
    ]
    return sorted(lignes, key=lambda ligne: -(ligne["cout_annuel"] or 0))


def _points(bilans: list[BilanContrat]) -> list[str]:
    points = [f"{b.titulaire} · {b.produit} : {a.split(' : ', 1)[-1]}" for b in bilans for a in b.anomalies]
    points += [f"{b.titulaire} · {b.produit} : relevé de situation seul, frais et historique inconnus"
               for b in bilans if not b.annees]  # fmt: skip
    return points


def _credits(comptes, banque: list[dict], biens: dict) -> dict:
    """Rendre « credits » et « synthese_credits » ; revenus du foyer pris dans la vue Budget « Foyer », sinon le
    compte courant unique."""
    courants = [b for b in banque if b["type"] in ("courant", "locatif")]
    foyer = next((b for b in courants if b["id"] == "b:foyer"), courants[0] if len(courants) == 1 else None)
    resultat = etat_credits(comptes, foyer["revenus_mois"] if foyer else None, biens)
    return {"credits": resultat["credits"], "synthese_credits": resultat["synthese"]}


def _historique(releves, comptes, biens: dict, aujourd_hui: date, patrimoine: dict) -> dict[str, dict]:
    """Rendre la courbe mensuelle de chaque vue qui a un patrimoine (foyer, personnes). MODELE § 8.1."""
    resultat = {}
    for cle in patrimoine:
        titulaire = None if cle == "foyer" else cle.removeprefix("p:")
        historique = historique_patrimoine(
            [r for r in releves if titulaire in (None, r.titulaire)],
            [c for c in comptes if titulaire in (None, c.titulaire)],
            biens,
            aujourd_hui,
        )
        resultat[cle] = {
            "points": [{"jour": p.jour.isoformat(), "actifs": _nombre(p.actifs), "credits": _nombre(p.credits),
                        "net": _nombre(p.net)} for p in historique.points],
            "reportes": historique.reportes,
            "familles": {nom: [_nombre(v) for v in valeurs] for nom, valeurs in historique.familles.items()},
        }  # fmt: skip
    return resultat


def _reperes(vues: list[dict]) -> dict[str, dict]:
    """Rendre les repères publics de chaque année présente dans une vue, en fractions. MODELE § 10."""
    annees = sorted({a["annee"] for v in vues for a in v["annees"]})
    champs = ("fonds_euros", "unites_de_compte", "livret_a", "inflation", "msci_world")
    return {str(annee): {c: _taux(getattr(reperes_de(annee), c)) for c in champs} for annee in annees}


def _locatif(dossier, comptes, biens: dict) -> dict | None:
    """Rendre le bien locatif sur un an (MODELE § 7.12), ou None sans compte de type « locatif »."""
    locatifs = [c for c in comptes if c.type_compte == "locatif"]
    if not locatifs:
        return None
    vide: dict = {}
    cle, bien = next(((k, b) for k, b in biens.items() if "locatif" in str(b.get("nom", "")).lower()), ("", vide))
    credit = next((c for c in comptes if c.type_compte == "credit" and cle and c.numero_masque.endswith(cle)), None)
    regles = lire_regles(dossier)
    b = analyser_locatif(
        bien.get("nom") or "Bien locatif",
        [analyser(c, regles) for c in locatifs],
        analyser_credit(credit, comptes) if credit else None,
        Decimal(str(bien["valeur"])) if bien.get("valeur") else None,
    )
    return {
        "nom": b.nom, "titulaires": sorted({c.titulaire for c in locatifs}), "valeur": _nombre(b.valeur),
        "loyers": _nombre(b.loyers), "charges": _nombre(b.charges), "echeances": _nombre(b.echeances),
        "interets": _nombre(b.interets), "rendement_brut": _taux(b.rendement_brut), "rendement_net": _taux(b.rendement_net),
        "rendement_apres_interets": _taux(b.rendement_apres_interets), "tresorerie_mensuelle": _nombre(b.tresorerie_mensuelle),
        "mois_couverts": round(float(b.mois_couverts), 1),
    }  # fmt: skip
