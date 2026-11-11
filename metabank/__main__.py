"""Ligne de commande : « uv run python -m metabank inventaire [--interactif] »."""

import argparse
import sys
from datetime import datetime

from metabank.config import lire_config
from metabank.modele import Compte


def main(arguments: list[str] | None = None) -> int:
    """Rendre le code de sortie : 0 si toutes les sources ont répondu, 1 sinon."""
    analyseur = argparse.ArgumentParser(prog="metabank", description="Patrimoine financier, en local.")
    commandes = analyseur.add_subparsers(dest="commande", required=True)
    inventaire = commandes.add_parser("inventaire", help="collecter les comptes via woob et écrire un instantané")
    inventaire.add_argument(
        "--interactif", action="store_true", help="autoriser code SMS et validation sur téléphone (vous êtes là)"
    )
    options = analyseur.parse_args(arguments)
    return _inventaire(options.interactif)


def _inventaire(interactif: bool) -> int:
    # Import différé : charger woob coûte une seconde, inutile pour --help.
    from metabank.connecteurs.woob_collecte import ErreurCollecte, collecter  # noqa: PLC0415
    from metabank.instantane import ecrire_instantane  # noqa: PLC0415

    config = lire_config()
    try:
        resultat = collecter(config["woob_backends"], config["dossier_session_woob"], interactif)
    except ErreurCollecte as erreur:
        print(f"Collecte impossible : {erreur}", file=sys.stderr)
        return 1
    for compte in resultat.comptes:
        print(_resumer(compte))
    for nom, message in resultat.erreurs.items():
        print(f"[{nom}] {message}", file=sys.stderr)
    if resultat.comptes:
        chemin = ecrire_instantane(resultat.comptes, config["dossier_donnees"], "woob", datetime.now().astimezone())
        print(f"Instantané : {chemin}")
    return 1 if resultat.erreurs else 0


def _resumer(compte: Compte) -> str:
    solde = f"{compte.solde:>14,.2f} {compte.devise or ''}" if compte.solde is not None else f"{'?':>14}"
    lignes = f"  ({len(compte.lignes)} supports)" if compte.lignes else ""
    return f"{compte.type_compte:<15} {compte.libelle[:40]:<40} {compte.numero_masque or '':<6} {solde}{lignes}"


if __name__ == "__main__":
    sys.exit(main())
