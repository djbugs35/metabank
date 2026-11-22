"""Corrections saisies à la main dans data/corrections.json, quand les relevés ne disent pas tout.

Format (docs/FORMATS.md) :
  {"ouvertures": {"270272854": "2023-03-30", "50025784": "2019-12-08"}}
La clé est le numéro du contrat, ou sa fin : elle est comparée à la fin du numéro lu sur les relevés.
"""

import json
from datetime import date
from pathlib import Path

FICHIER = "corrections.json"


def lire_ouvertures(dossier: Path) -> dict[str, date]:
    """Rendre les dates d'ouverture par numéro de contrat (sans espaces), ou {} sans fichier."""
    chemin = dossier / FICHIER
    if not chemin.exists():
        return {}
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    return {cle.replace(" ", ""): date.fromisoformat(valeur) for cle, valeur in contenu.get("ouvertures", {}).items()}


def date_ouverture(numero: str, ouvertures: dict[str, date]) -> date | None:
    """Rendre la date d'ouverture du contrat dont le numéro finit par une des clés, ou None."""
    compact = numero.replace(" ", "")
    return next((jour for cle, jour in ouvertures.items() if compact.endswith(cle)), None)
