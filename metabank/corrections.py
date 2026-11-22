"""Corrections saisies à la main dans data/corrections.json, quand les relevés ne disent pas tout.

Format :
  {"ouvertures": {"270272854": "2023-03-30", "50025784": "2019-12-08"},
   "versements_verifies": {"270549974": [2024, 2025]}}
La clé est le numéro du contrat, ou sa fin : elle est comparée à la fin du numéro lu sur les relevés.
« versements_verifies » : années où le titulaire a confirmé, par ses virements, le montant de la synthèse des
mouvements (celui que metabank retient) ; l'écart avec le tableau « évolution du plan » n'est alors plus signalé.
"""

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

from metabank.releves import ReleveRange

FICHIER = "corrections.json"


ANOMALIE_VERSEMENTS = "versements de l'année"


def _lire(dossier: Path) -> dict:
    chemin = dossier / FICHIER
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


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
