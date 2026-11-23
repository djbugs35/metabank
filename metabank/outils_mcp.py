"""Outils du serveur MCP : les chiffres de metabank en lecture seule, choisis champ par champ.

Chaque outil rend des chiffres déjà calculés par le code testé (web/vues.py et les simulations) ; Claude les commente,
il n'en calcule aucun. Les comptes et contrats sont désignés par leur nom (« Alice · Patrimoine Vie Plus »), jamais
par un numéro : ni identifiant de contrat ni numéro de compte, pas même les 4 derniers chiffres que la page affiche
(CLAUDE.md : l'IA ne reçoit ni identifiant ni numéro). Aucun outil n'écrit quoi que ce soit dans data/.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from metabank.web import vues
from metabank.web.allocation_vues import etat_allocation
from metabank.web.credits_vues import simuler_remboursement
from metabank.web.retraite_vues import simuler_retraite
from metabank.web.simulation import simuler

# « ****1234 » d'un compte, « …9974 » d'un contrat : retirés de tout texte rendu à Claude.
NUMERO_MASQUE = re.compile(r"\s*(?:\*+|…)\d{1,4}\b")


def sans_numero(valeur: object) -> object:
    """Rendre la valeur (dict, liste, texte) sans aucun numéro masqué dans ses textes."""
    if isinstance(valeur, str):
        return NUMERO_MASQUE.sub("", valeur)
    if isinstance(valeur, dict):
        return {cle: sans_numero(v) for cle, v in valeur.items()}
    if isinstance(valeur, list):
        return [sans_numero(v) for v in valeur]
    return valeur


class OutilInconnu(KeyError):
    """Aucun outil ne porte ce nom."""


@dataclass(frozen=True)
class Outil:
    """Un outil : nom, description pour Claude, schéma JSON des arguments, et ce qu'il calcule."""

    nom: str
    description: str
    schema: dict
    calculer: Callable[[Path, dict], dict]


def _vue(etat: dict, nom: str) -> dict:
    """Rendre la vue de ce nom (« Foyer », un prénom, ou « prénom · contrat »)."""
    vue = next((v for v in etat["vues"] if v["nom"] == (nom or "Foyer")), None)
    if vue is None:
        noms = ", ".join(v["nom"] for v in etat["vues"])
        raise ValueError(f"vue inconnue « {nom} » ; vues possibles : {noms}")
    return vue


def _cle_patrimoine(vue: dict) -> str:
    return "foyer" if vue["niveau"] == "foyer" else f"p:{vue['nom'] if vue['niveau'] == 'personne' else ''}"


def _patrimoine(dossier: Path, arguments: dict) -> dict:
    etat = vues.etat(dossier)
    vue = _vue(etat, arguments.get("vue", ""))
    if vue["niveau"] == "contrat":
        raise ValueError("le patrimoine se lit au foyer ou par personne")
    cle = _cle_patrimoine(vue)
    p = etat["patrimoine"].get(cle) or {}
    historique = etat["historique"].get(cle, {})
    return {
        "vue": vue["nom"],
        "actifs": p.get("total"),
        "credits": p.get("credits"),
        "patrimoine_net": None if p.get("credits_sans_bien") else p.get("net"),
        "familles": [{"famille": f["famille"], "montant": f["montant"], "part": f["part"]} for f in p.get("familles", [])],
        "comptes": [{"nom": ligne["nom"], "famille": ligne["famille"], "valeur": ligne["valeur"], "date": ligne["date"]}
                    for ligne in p.get("lignes", [])],
        "fins_de_mois": historique.get("points", []),
        "unites": "euros ; parts en fractions",
    }  # fmt: skip


def _placements(dossier: Path, arguments: dict) -> dict:
    etat = vues.etat(dossier)
    v = _vue(etat, arguments.get("vue", ""))
    champs = ("verse", "valeur", "gain", "gain_taux", "gain_par_an", "frais", "frais_taux", "frais_par_an")
    return {
        "vue": v["nom"],
        **{c: v[c] for c in champs},
        "annees": [{**a, "reperes": etat["reperes"].get(str(a["annee"]))} for a in v["annees"]],
        "contrats_de_la_vue": [w["nom"] for w in etat["vues"] if w["parent"] == v["id"]],
        "unites": "euros ; taux en fractions (0,028 = 2,8 %)",
    }


def _budget(dossier: Path, _arguments: dict) -> dict:
    etat = vues.etat(dossier)
    champs = ("nom", "type", "solde", "date_solde", "revenus_mois", "depenses_mois", "epargne_mois", "frais_an",
              "argent_qui_dort", "categories", "abonnements", "objectifs", "comparaison")  # fmt: skip
    return {"comptes": [{c: b.get(c) for c in champs} for b in etat["banque"]], "unites": "euros ; parts en fractions"}


def _credits(dossier: Path, _arguments: dict) -> dict:
    etat = vues.etat(dossier)
    champs = ("nom", "date", "projete_depuis", "capital_restant", "taux_annuel", "mensualite", "mensualite_prelevee",
              "fin_estimee", "mois_restants", "interets_restants", "assurance_mensuelle", "assurance_restante",
              "echeancier", "bien_nom", "bien_valeur")  # fmt: skip
    return {
        "credits": [{c: x.get(c) for c in champs} for x in etat["credits"]],
        "synthese": etat.get("synthese_credits"),
    }


def _echeances(dossier: Path, _arguments: dict) -> dict:
    return {"echeances": vues.etat(dossier)["echeances"]}


def _bien_locatif(dossier: Path, _arguments: dict) -> dict:
    return {"bien_locatif": vues.etat(dossier)["locatif"]}


def _allocation(dossier: Path, arguments: dict) -> dict:
    a = etat_allocation(dossier, str(arguments.get("titulaire") or ""))
    return {k: a[k] for k in ("titulaire", "total", "repartition", "concentrations", "derives", "a_verser",
                              "total_a_verser", "cible")} | {
        "fonds": [{k: p[k] for k in ("libelle", "titulaire", "contrat", "classe", "valeur")} for p in a["positions"]]
    }  # fmt: skip


def _remboursement(dossier: Path, arguments: dict) -> dict:
    etat = vues.etat(dossier)
    credit = next((c for c in etat["credits"] if sans_numero(c["nom"]) == arguments.get("credit")), None)
    if credit is None:
        raise ValueError("crédit inconnu ; crédits : " + ", ".join(str(sans_numero(c["nom"])) for c in etat["credits"]))
    return simuler_remboursement(dossier, {"cle": credit["cle"], "montant": arguments.get("montant"),
                                           "rendement": arguments.get("rendement")})  # fmt: skip


def _schema(proprietes: dict, requis: tuple[str, ...] = ()) -> dict:
    return {"type": "object", "properties": proprietes, "required": list(requis), "additionalProperties": False}


VUE = {"type": "string", "description": "« Foyer » (par défaut), un prénom, ou « prénom · contrat »"}
NOMBRE = {"type": "number"}
OUTILS: list[Outil] = [
    Outil("patrimoine", "Patrimoine du foyer ou d'une personne : actifs par famille, crédits, net, 13 fins de mois.",
          _schema({"vue": VUE}), _patrimoine),
    Outil("placements", "Assurance vie, PER, PERP : versé, valeur, gagné, frais, année par année face aux repères publics.",
          _schema({"vue": VUE}), _placements),
    Outil("budget", "Comptes courants et livrets : revenus, dépenses par catégorie, dépenses régulières, objectifs.",
          _schema({}), _budget),
    Outil("credits", "Crédits : capital restant dû (projeté au mois en cours), taux, fin, intérêts, assurance, "
          "tableau d'amortissement par année.", _schema({}), _credits),
    Outil("echeances", "Échéances datées : 8 ans des assurances vie et abattement, transfert des PER, 31 décembre.",
          _schema({}), _echeances),
    Outil("bien_locatif", "Bien locatif : loyers, charges, mensualités, rendements, trésorerie mensuelle.",
          _schema({}), _bien_locatif),
    Outil("allocation", "Répartition du patrimoine financier par classe, fonds par fonds, concentration, cible.",
          _schema({"titulaire": {"type": "string", "description": "prénom ; vide pour le foyer"}}), _allocation),
    Outil("simuler_frais", "Valeur d'un placement dans N ans avec ses frais actuels et avec des frais visés (en %).",
          _schema({"valeur": NOMBRE, "rendement_brut": NOMBRE, "frais_actuels": NOMBRE, "frais_vises": NOMBRE,
                   "horizon": {"type": "integer"}}, ("valeur", "rendement_brut", "frais_actuels", "frais_vises",
                                                     "horizon")),
          lambda _dossier, arguments: simuler(arguments)),
    Outil("rembourser_ou_placer", "Rembourser par anticipation un montant (euros) ou le placer à un rendement net "
          "supposé (% par an), comparés à la fin actuelle du prêt.",
          _schema({"credit": {"type": "string", "description": "nom du crédit, tel que l'outil credits le donne"},
                   "montant": NOMBRE, "rendement": NOMBRE}, ("credit", "montant", "rendement")), _remboursement),
    Outil("projeter_retraite", "Capital des PER et PERP d'une personne à son départ, trois rendements nets (en %), "
          "en euros d'aujourd'hui, et retrait mensuel possible.",
          _schema({"titulaire": {"type": "string"}, "annee_depart": {"type": "integer"}, "versement": NOMBRE,
                   "inflation": NOMBRE, "duree_retrait": {"type": "integer"},
                   "rendements": {"type": "array", "items": NOMBRE, "minItems": 3, "maxItems": 3},
                   "inclure_av": {"type": "boolean"}},
                  ("titulaire", "annee_depart", "versement", "inflation", "duree_retrait", "rendements")),
          simuler_retraite),
]  # fmt: skip


def appeler(dossier: Path, nom: str, arguments: dict) -> dict:
    """Rendre le résultat de l'outil nommé.

    Raises:
        OutilInconnu: aucun outil de ce nom.
        ValueError: arguments hors bornes (message pour Claude).
    """
    outil = next((o for o in OUTILS if o.nom == nom), None)
    if outil is None:
        raise OutilInconnu(nom)
    return cast(dict, sans_numero(outil.calculer(dossier, arguments)))
