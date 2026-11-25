"""Écrans branchés sur la base : mêmes chiffres qu'avec les anciens lecteurs, fichiers rangés à la main repris."""

import sqlite3
import threading
from datetime import date

import pytest

from metabank.banque import lire_comptes
from metabank.base.integration import FICHIER_BASE
from metabank.donnees import Donnees, charger
from metabank.releves import lire_dossier
from metabank.web import vues
from metabank.web.depot import deposer_releve
from tests.conftest import EXEMPLES, pdf, ranger

pytestmark = pytest.mark.usefixtures("pdf_simules")


def test_l_application_affiche_les_memes_chiffres_que_les_anciens_lecteurs(donnees, monkeypatch):
    anciens = Donnees(lire_dossier(donnees)[0], lire_comptes(donnees)[0], [])
    depuis_la_base = vues.etat(donnees)
    monkeypatch.setattr(vues, "charger", lambda _: anciens)
    assert depuis_la_base == vues.etat(donnees)


def test_un_fichier_range_a_la_main_apparait_au_chargement_suivant(donnees):
    avant = len(charger(donnees).releves)
    # Situation d'un autre contrat Cardif, rangée chez Alice : sa fiche CSV est écrite puis lue au chargement.
    autre = pdf("cardif_situation.txt").replace(b"(N\xc2\xb0 12345678)", b"(N\xc2\xb0 12345679)")
    ranger(donnees, "Alice/PERP - Cardif - Perp 987654/situation.pdf", autre)
    assert len(charger(donnees).releves) == avant + 1


def test_un_fichier_depose_dans_la_page_entre_en_base(tmp_path):
    deposer_releve(tmp_path, "Alice", "export.csv", (EXEMPLES / "bnp_courant.csv").read_bytes())
    assert [c.titulaire for c in charger(tmp_path).comptes] == ["Alice"]
    assert not (tmp_path / "Alice").exists()


def test_un_fichier_illisible_range_a_la_main_est_signale(donnees):
    ranger(donnees, "Alice/CC - BNP - 1234/abime.csv", (EXEMPLES / "bnp_courant.csv").read_bytes() + b"x;y\n")
    erreurs = charger(donnees).erreurs
    assert len(erreurs) == 1 and erreurs[0].startswith("Alice/CC - BNP - 1234/abime.csv")


def test_une_archive_illisible_est_signalee_apres_reconstruction(donnees):
    charger(donnees)
    abime = (EXEMPLES / "bnp_courant.csv").read_bytes() + b"x;y\n"
    ranger(donnees, "archives/Alice/CC - BNP - 1234/abime.csv", abime)
    (donnees / FICHIER_BASE).unlink()
    erreurs = charger(donnees).erreurs
    assert len(erreurs) == 1 and erreurs[0].startswith("archives/Alice/CC - BNP - 1234/abime.csv")


def test_sans_dossier_de_donnees_rien_a_afficher(tmp_path):
    assert charger(tmp_path / "absent") == Donnees([], [], [])


def test_le_patrimoine_compte_le_capital_projete_au_mois_en_cours(donnees):
    a_l_export = vues.etat(donnees, date(2026, 6, 20))["patrimoine"]["foyer"]["credits"]
    trois_mois_plus_tard = vues.etat(donnees, date(2026, 9, 10))
    assert trois_mois_plus_tard["patrimoine"]["foyer"]["credits"] < a_l_export
    assert trois_mois_plus_tard["credits"][0]["projete_depuis"] == "2026-06-20"


def test_deux_chargements_simultanes_apres_un_changement_de_lecteurs_ne_se_genent_pas(donnees):
    """Au lancement, la synchronisation et la page chargent ensemble : fiches et base s'écrivent l'une après l'autre."""
    charger(donnees)
    for fiche in donnees.rglob("metabank-*.csv"):
        fiche.unlink()
    connexion = sqlite3.connect(donnees / "metabank.db")
    with connexion:
        connexion.execute("UPDATE meta SET valeur = 'ancienne' WHERE cle = 'version_des_lecteurs'")
    connexion.close()
    erreurs: list[BaseException] = []

    def charger_et_noter() -> None:
        try:
            charger(donnees)
        except Exception as erreur:  # noqa: BLE001 (le test relève toute erreur d'un fil)
            erreurs.append(erreur)

    fils = [threading.Thread(target=charger_et_noter) for _ in range(4)]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join()
    assert erreurs == []
    assert len(charger(donnees).releves) == 3
