"""Lecture de la configuration : config/metabank.json, surchargé clé par clé par config/local.json."""

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_CONFIG = RACINE / "config" / "metabank.json"
FICHIER_LOCAL = RACINE / "config" / "local.json"


def lire_config(fichier: Path = FICHIER_CONFIG, fichier_local: Path = FICHIER_LOCAL) -> dict:
    """Rendre la configuration fusionnée, sans les clés d'aide (celles qui commencent par « _ »).

    Les chemins sont rendus absolus : relatifs à la racine du dépôt, « ~ » développé.
    """
    config = _sans_aide(json.loads(fichier.read_text(encoding="utf-8")))
    if fichier_local.exists():
        config |= _sans_aide(json.loads(fichier_local.read_text(encoding="utf-8")))
    for cle in ("dossier_donnees", "dossier_session_woob"):
        config[cle] = _chemin_absolu(config[cle], fichier.parent.parent)
    return config


def _sans_aide(valeurs: dict) -> dict:
    return {cle: valeur for cle, valeur in valeurs.items() if not cle.startswith("_")}


def _chemin_absolu(chemin: str, racine: Path) -> Path:
    resultat = Path(chemin).expanduser()
    return resultat if resultat.is_absolute() else racine / resultat
