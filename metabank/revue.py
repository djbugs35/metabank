"""Revue mensuelle : une courte liste d'actions, tirée des chiffres déjà calculés (synoptique, échéances, budget,
allocation, fichiers non lus). Rien n'est décidé ici : la revue dit quoi regarder, pas quoi faire de son argent.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from metabank.synoptique import EN_RETARD, JAMAIS, TRES_EN_RETARD
from metabank.web import vues
from metabank.web.allocation_vues import etat_allocation
from metabank.web.synoptique_vues import etat_synoptique

HORIZON_ECHEANCES_JOURS = 90
SUJETS = ("Fichiers à déposer", "Échéances", "Budget", "Allocation", "Fichiers non lus")


@dataclass(frozen=True)
class Action:
    """Une chose à regarder ce mois-ci : son sujet (un de SUJETS), le texte, et le détail utile pour la faire."""

    sujet: str
    texte: str
    detail: str = ""


@dataclass(frozen=True)
class Revue:
    """La revue d'un mois (« AAAA-MM ») et ses actions, dans l'ordre de SUJETS."""

    mois: str
    actions: list[Action]


def faire_revue(dossier: Path, aujourd_hui: date | None = None) -> Revue:
    """Rendre la revue du mois en cours, à partir de data/."""
    aujourd_hui = aujourd_hui or datetime.now().astimezone().date()
    etat = vues.etat(dossier, aujourd_hui)
    actions = (
        _fichiers_a_deposer(etat_synoptique(dossier, aujourd_hui))
        + _echeances(etat["echeances"], aujourd_hui)
        + _budget(etat["banque"])
        + _allocation(etat_allocation(dossier))
        + [Action("Fichiers non lus", e) for e in etat["erreurs"]]
    )
    return Revue(f"{aujourd_hui:%Y-%m}", actions)


def _fichiers_a_deposer(synoptique: dict) -> list[Action]:
    retards = {EN_RETARD: "en retard", TRES_EN_RETARD: "très en retard", JAMAIS: "jamais mis à jour"}
    return [
        Action("Fichiers à déposer", f"{c['nom']} : {retards[c['fraicheur']]}"
               + (f" (dernière donnée {c['derniere_donnee']})" if c["derniere_donnee"] else ""), c["mode_emploi"])
        for c in synoptique["comptes"]
        if c["fraicheur"] in retards
    ]  # fmt: skip


def _echeances(echeances: list[dict], aujourd_hui: date) -> list[Action]:
    limite = (aujourd_hui + timedelta(days=HORIZON_ECHEANCES_JOURS)).isoformat()
    proches = [e for e in echeances if e["jour"] is None or aujourd_hui.isoformat() <= e["jour"] <= limite]
    return [
        Action("Échéances", f"{e['quoi']} : {e['titulaire']} · {e['contrat']}, "
               + (f"le {e['jour']}" if e["jour"] else "date d'ouverture à saisir"), e["detail"])
        for e in proches
    ]  # fmt: skip


def _budget(banque: list[dict]) -> list[Action]:
    return [
        Action("Budget", f"{b['nom']} : objectif {o['categorie']} dépassé en {o['mois']}",
               f"{o['depense_mois']:.0f} € dépensés pour {o['objectif']:.0f} € visés")
        for b in banque
        for o in b.get("objectifs", [])
        if o["depasse"]
    ]  # fmt: skip


def _allocation(allocation: dict) -> list[Action]:
    actions = [
        Action("Allocation", f"{c['libelle']} ({c['contrat']}) pèse {c['part']:.0%} du patrimoine financier")
        for c in allocation["concentrations"]
    ]
    actions += [Action("Allocation", f"{classe} s'écarte de sa cible de {ecart:+.0%}")
                for classe, ecart in allocation["derives"].items()]  # fmt: skip
    a_classer = sum(1 for p in allocation["positions"] if p["classe"] == "À classer")
    if a_classer:
        actions.append(Action("Allocation", f"{a_classer} fonds à classer dans l'onglet Allocation"))
    return actions


DOSSIER_REVUES = "revues"


def en_texte(revue: Revue) -> str:
    """Rendre la revue en Markdown lisible, un titre par sujet."""
    lignes = [f"# Revue de {revue.mois}", ""]
    if not revue.actions:
        lignes.append("Rien à signaler ce mois-ci.")
    for sujet in SUJETS:
        actions = [a for a in revue.actions if a.sujet == sujet]
        if actions:
            lignes += [f"## {sujet}", ""] + [
                f"- {a.texte}" + (f"  \n  {a.detail}" if a.detail else "") for a in actions
            ]
            lignes.append("")
    return "\n".join(lignes).rstrip() + "\n"


def enregistrer_revue(dossier: Path, revue: Revue, remplacer: bool = True) -> Path:
    """Rendre le chemin de data/revues/AAAA-MM.md, écrit (atomiquement) s'il manque ou si remplacer est vrai."""
    chemin = dossier / DOSSIER_REVUES / f"{revue.mois}.md"
    if remplacer or not chemin.exists():
        chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire = chemin.with_suffix(".md.tmp")
        temporaire.write_text(en_texte(revue), encoding="utf-8")
        temporaire.replace(chemin)
    return chemin
