"""Ligne de commande : « uv run python -m metabank web | bilan | frais | tableau »."""

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from metabank.bilan import faire_bilans
from metabank.corrections import appliquer_verifications, lire_ouvertures
from metabank.frais import analyser_frais
from metabank.frais_historique import historiques_frais
from metabank.rapport import en_json, formater_texte
from metabank.rapport_frais import formater_frais
from metabank.releves import lire_dossier
from metabank.tableau import Tableau, generer_html
from metabank.web.serveur import PORT_DEFAUT, creer_serveur

RACINE = Path(__file__).resolve().parent.parent


def main(arguments: list[str] | None = None) -> int:
    """Rendre le code de sortie : 0 si tous les PDF ont été lus, 1 sinon."""
    analyseur = argparse.ArgumentParser(prog="metabank", description="Patrimoine financier, en local.")
    commandes = analyseur.add_subparsers(dest="commande", required=True)
    bilan = commandes.add_parser("bilan", help="lire les relevés PDF de data/ et afficher le bilan par contrat")
    bilan.add_argument("--donnees", type=Path, default=RACINE / "data", help="dossier data/<titulaire>/<contrat>/")
    frais = commandes.add_parser("frais", help="frais support par support et simulation de supports moins chers")
    frais.add_argument("--donnees", type=Path, default=RACINE / "data", help="dossier data/<titulaire>/<contrat>/")
    frais.add_argument("--cible", type=Decimal, default=Decimal("0.20"), help="frais d'un support peu cher, en %%")
    frais.add_argument("--rendement", type=Decimal, default=Decimal(5), help="rendement brut supposé, en %% par an")
    frais.add_argument("--horizon", type=int, default=15, help="durée de la projection, en années")
    tableau = commandes.add_parser("tableau", help="générer le tableau de bord data/tableau.html et l'ouvrir")
    tableau.add_argument("--donnees", type=Path, default=RACINE / "data", help="dossier data/<titulaire>/<contrat>/")
    tableau.add_argument("--sans-ouvrir", action="store_true", help="générer la page sans ouvrir le navigateur")
    web = commandes.add_parser("web", help="lancer l'application web locale et l'ouvrir dans le navigateur")
    web.add_argument("--donnees", type=Path, default=RACINE / "data", help="dossier data/<titulaire>/<contrat>/")
    web.add_argument("--port", type=int, default=PORT_DEFAUT, help="port local (127.0.0.1 seulement)")
    web.add_argument("--sans-ouvrir", action="store_true", help="ne pas ouvrir le navigateur")
    options = analyseur.parse_args(arguments)
    if options.commande == "frais":
        return _frais(options)
    if options.commande == "web":
        return _web(options.donnees, options.port, ouvrir=not options.sans_ouvrir)
    if options.commande == "tableau":
        return _tableau(options.donnees, ouvrir=not options.sans_ouvrir)
    return _bilan(options.donnees)


def _frais(options) -> int:
    releves, erreurs = lire_dossier(options.donnees)
    analyses = analyser_frais(releves, options.cible, options.rendement, options.horizon)
    print(formater_frais(analyses))
    anomalies = [a for r in releves for a in r.releve.anomalies if "frais du support" in a]
    for message in erreurs + anomalies:
        print(f"  ⚠ {message}")
    return 1 if erreurs else 0


def _tableau(dossier: Path, ouvrir: bool) -> int:
    releves, erreurs = lire_dossier(dossier)
    releves = appliquer_verifications(releves, dossier)
    page = generer_html(
        Tableau(
            faire_bilans(releves, lire_ouvertures(dossier)),
            analyser_frais(releves),
            datetime.now().astimezone().date(),
            historiques_frais(releves),
        )
    )
    sortie = dossier / "tableau.html"
    _ecrire(sortie, page)
    print(f"Tableau de bord : {sortie}")
    for erreur in erreurs:
        print(f"  ⚠ {erreur}")
    # « open » (macOS) ouvre la page dans le navigateur par défaut ; ailleurs, on donne juste le chemin.
    if ouvrir and shutil.which("open"):
        subprocess.run(["open", str(sortie)], check=False)
    return 1 if erreurs else 0


def _web(dossier: Path, port: int, ouvrir: bool) -> int:
    dossier.mkdir(exist_ok=True)
    serveur = creer_serveur(dossier, port)
    adresse = f"http://127.0.0.1:{serveur.server_port}"
    print(f"metabank : {adresse} (ce Mac seulement). Ctrl-C ou fermer la fenêtre pour arrêter.")
    if ouvrir and shutil.which("open"):
        subprocess.run(["open", adresse], check=False)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nmetabank arrêté.")
    finally:
        serveur.server_close()
    return 0


def _ecrire(sortie: Path, contenu: str) -> None:
    temporaire = sortie.with_suffix(sortie.suffix + ".tmp")
    temporaire.write_text(contenu, encoding="utf-8")
    temporaire.replace(sortie)


def _bilan(dossier: Path) -> int:
    releves, erreurs = lire_dossier(dossier)
    releves = appliquer_verifications(releves, dossier)
    bilans = faire_bilans(releves, lire_ouvertures(dossier))
    print(formater_texte(bilans, erreurs))
    sortie = dossier / "bilan.json"
    _ecrire(sortie, en_json(bilans))
    print(f"\nBilan détaillé : {sortie}")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
