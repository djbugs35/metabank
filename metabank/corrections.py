"""Corrections saisies à la main dans data/corrections.json, quand les relevés ne disent pas tout.

Format :
  {"ouvertures": {"270272854": "2023-03-30", "50025784": "2019-12-08"},
   "versements_verifies": {"270549974": [2024, 2025]},
   "biens": {"6783": {"nom": "Résidence principale", "valeur": 450000}}}
La clé est le numéro du contrat, ou sa fin : elle est comparée à la fin du numéro lu sur les relevés.
« versements_verifies » : années où le titulaire a confirmé, par ses virements, le montant de la synthèse des
mouvements (celui que metabank retient) ; l'écart avec le tableau « évolution du plan » n'est alors plus signalé.
« biens » : valeur estimée par le titulaire du bien financé par un crédit (clé = fin du numéro du prêt).
"""

import json
import re
from dataclasses import replace
from datetime import date
from pathlib import Path

from metabank.releves import ReleveRange

FICHIER = "corrections.json"
ANOMALIE_VERSEMENTS = "versements de l'année"
CLE_VALIDE = re.compile(r"^[0-9A-Za-z]{4,20}$")
ANNEE_MIN, ANNEE_MAX = 1980, 2100
VALEUR_BIEN_MAX = 100_000_000


class CorrectionInvalide(ValueError):
    """Correction refusée : le message dit laquelle et pourquoi."""


def cle_contrat(numero: str) -> str:
    """Rendre la clé de corrections d'un contrat : le dernier groupe de son numéro (« 270549974 »)."""
    return numero.rsplit(maxsplit=1)[-1] if numero.strip() else numero


def _lire(dossier: Path) -> dict:
    chemin = dossier / FICHIER
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def lire_corrections(dossier: Path) -> dict:
    """Rendre les corrections telles qu'enregistrées, avec les deux rubriques toujours présentes."""
    contenu = _lire(dossier)
    return {
        "ouvertures": dict(contenu.get("ouvertures", {})),
        "versements_verifies": {cle: sorted(annees) for cle, annees in contenu.get("versements_verifies", {}).items()},
        "biens": dict(contenu.get("biens", {})),
    }


def ecrire_corrections(dossier: Path, corrections: dict) -> dict:
    """Rendre les corrections validées après les avoir enregistrées (écriture atomique).

    Raises:
        CorrectionInvalide: clé de contrat, date ou année hors format ; rien n'est écrit.
    """
    propres: dict[str, dict] = {"ouvertures": {}, "versements_verifies": {}, "biens": {}}
    for rubrique in propres:
        if not isinstance(corrections.get(rubrique) or {}, dict):
            raise CorrectionInvalide(f"{rubrique} : objet attendu")
    for cle, jour in (corrections.get("ouvertures") or {}).items():
        if not jour:
            continue
        _verifier_cle(cle)
        try:
            date.fromisoformat(jour)
        except (TypeError, ValueError) as erreur:
            raise CorrectionInvalide(f"date d'ouverture invalide pour {cle} : {jour}") from erreur
        propres["ouvertures"][cle] = jour
    for cle, annees in (corrections.get("versements_verifies") or {}).items():
        _verifier_cle(cle)
        if not isinstance(annees, list) or not all(isinstance(a, int) and ANNEE_MIN <= a <= ANNEE_MAX for a in annees):
            raise CorrectionInvalide(f"années invalides pour {cle} : {annees}")
        if annees:
            propres["versements_verifies"][cle] = sorted(set(annees))
    propres["biens"] = _biens(corrections.get("biens") or {})
    # Les autres rubriques éventuelles du fichier sont gardées telles quelles.
    contenu = {**_lire(dossier), **propres}
    chemin = dossier / FICHIER
    temporaire = chemin.with_suffix(".json.tmp")
    temporaire.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporaire.replace(chemin)
    return lire_corrections(dossier)


def _biens(biens: dict) -> dict:
    """Rendre les biens immobiliers validés : {clé du crédit : {"nom", "valeur" en euros}} ; valeur vide = retiré."""
    propres = {}
    for cle, bien in biens.items():
        _verifier_cle(cle)
        if not isinstance(bien, dict):
            raise CorrectionInvalide(f"bien {cle} : objet attendu")
        valeur, nom = bien.get("valeur"), str(bien.get("nom") or "").strip()[:60]
        if valeur in (None, ""):
            continue
        if not isinstance(valeur, int | float) or not 0 <= valeur <= VALEUR_BIEN_MAX:
            raise CorrectionInvalide(f"valeur du bien {cle} : nombre entre 0 et {VALEUR_BIEN_MAX} attendu")
        propres[cle] = {"nom": nom or "Bien immobilier", "valeur": valeur}
    return propres


def _verifier_cle(cle: str) -> None:
    if not isinstance(cle, str) or not CLE_VALIDE.match(cle):
        raise CorrectionInvalide(f"numéro de contrat invalide : {cle!r}")


def lire_ouvertures(dossier: Path) -> dict[str, date]:
    """Rendre les dates d'ouverture par numéro de contrat (sans espaces), ou {} sans fichier."""
    contenu = _lire(dossier)
    return {cle.replace(" ", ""): date.fromisoformat(valeur) for cle, valeur in contenu.get("ouvertures", {}).items()}


def date_ouverture(numero: str, ouvertures: dict[str, date]) -> date | None:
    """Rendre la date d'ouverture du contrat dont le numéro finit par une des clés, ou None."""
    compact = numero.replace(" ", "")
    return next((jour for cle, jour in ouvertures.items() if compact.endswith(cle)), None)


def appliquer_verifications(releves: list[ReleveRange], dossier: Path) -> list[ReleveRange]:
    """Rendre les relevés sans l'écart de versements des années vérifiées par le titulaire."""
    verifies = {
        cle.replace(" ", ""): set(annees) for cle, annees in _lire(dossier).get("versements_verifies", {}).items()
    }
    resultat = []
    for range_ in releves:
        releve = range_.releve
        compact = releve.numero.replace(" ", "")
        annees = next((a for cle, a in verifies.items() if compact.endswith(cle)), set())
        if releve.date_arrete.year in annees:
            gardees = tuple(a for a in releve.anomalies if ANOMALIE_VERSEMENTS not in a)
            resultat.append(replace(range_, releve=replace(releve, anomalies=gardees)))
        else:
            resultat.append(range_)
    return resultat
