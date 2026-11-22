"""Ligne de commande : « uv run python -m metabank bilan »."""

import argparse
import sys
from pathlib import Path

from metabank.bilan import faire_bilans
from metabank.rapport import en_json, formater_texte
from metabank.releves import lire_dossier

RACINE = Path(__file__).resolve().parent.parent


def main(arguments: list[str] | None = None) -> int:
    """Rendre le code de sortie : 0 si tous les PDF ont été lus, 1 sinon."""
    analyseur = argparse.ArgumentParser(prog="metabank", description="Patrimoine financier, en local.")
    commandes = analyseur.add_subparsers(dest="commande", required=True)
    bilan = commandes.add_parser("bilan", help="lire les relevés PDF de data/ et afficher le bilan par contrat")
    bilan.add_argument("--donnees", type=Path, default=RACINE / "data", help="dossier data/<titulaire>/<contrat>/")
    options = analyseur.parse_args(arguments)
    return _bilan(options.donnees)


def _bilan(dossier: Path) -> int:
    releves, erreurs = lire_dossier(dossier)
    bilans = faire_bilans(releves)
    print(formater_texte(bilans, erreurs))
    sortie = dossier / "bilan.json"
    temporaire = sortie.with_suffix(".json.tmp")
    temporaire.write_text(en_json(bilans), encoding="utf-8")
    temporaire.replace(sortie)
    print(f"\nBilan détaillé : {sortie}")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
