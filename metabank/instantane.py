"""Instantané : photo datée de tous les comptes d'une source, écrite en JSON (format dans docs/FORMATS.md).

Les instantanés bruts sont gardés tels quels : la base d'analyse pourra toujours être reconstruite à partir d'eux.
"""

import json
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from metabank.modele import Compte

VERSION_FORMAT = 1


def ecrire_instantane(comptes: list[Compte], dossier: Path, source: str, moment: datetime) -> Path:
    """Rendre le chemin de l'instantané écrit dans dossier/instantanes/AAAA-MM-JJ_HHMM_<source>.json.

    L'écriture est atomique (temporaire puis renommage) : une collecte interrompue ne laisse pas de fichier tronqué.
    """
    dossier_instantanes = dossier / "instantanes"
    dossier_instantanes.mkdir(parents=True, exist_ok=True)
    chemin = dossier_instantanes / f"{moment:%Y-%m-%d_%H%M}_{source}.json"
    contenu = {
        "format": VERSION_FORMAT,
        "source": source,
        "date_collecte": moment.isoformat(timespec="seconds"),
        "comptes": [asdict(compte) for compte in comptes],
    }
    temporaire = chemin.with_suffix(".json.tmp")
    temporaire.write_text(json.dumps(contenu, ensure_ascii=False, indent=2, default=_en_json), encoding="utf-8")
    temporaire.replace(chemin)
    return chemin


def _en_json(valeur) -> str:
    # Decimal en texte : un float perdrait des centimes ; date au format ISO.
    if isinstance(valeur, Decimal):
        return str(valeur)
    if isinstance(valeur, date):
        return valeur.isoformat()
    raise TypeError(f"type non sérialisable : {type(valeur).__name__}")
