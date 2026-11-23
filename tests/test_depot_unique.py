"""Dépôt unique : dossier surveillé et dépôt sans titulaire, rangés d'après le compte reconnu dans le fichier."""

import pytest

from metabank.configuration import ConfigurationInvalide, ecrire_configuration
from metabank.connecteurs.registre import lister_connecteurs
from metabank.depot_unique import traiter_dossier_depot
from metabank.donnees import charger
from metabank.web.depot import DepotRefuse, deposer_releve
from tests.conftest import EXEMPLES, pdf, ranger

pytestmark = pytest.mark.usefixtures("pdf_simules")
CONNECTEURS = lister_connecteurs()


def _courant_de_mai() -> bytes:
    """Rendre un export du compte courant fictif ****1234, plus récent que celui des données."""
    return (EXEMPLES / "bnp_courant.csv").read_bytes().replace(b"31/03/2026;;10 000,00", b"30/04/2026;;9 000,00")


def test_un_export_d_un_compte_connu_pose_dans_le_dossier_surveille_est_range_et_mis_de_cote(donnees):
    charger(donnees)
    ranger(donnees, "depot/mai.csv", _courant_de_mai())
    resultat = charger(donnees)
    courant = next(c for c in resultat.comptes if c.type_compte == "courant")
    assert courant.date_solde.isoformat() == "2026-04-30" and resultat.erreurs == []
    assert (donnees / "archives/Alice/CC - BNP - 1234/mai.csv").exists()
    assert (donnees / "depot/importes/mai.csv").exists() and not (donnees / "depot/mai.csv").exists()


def test_un_releve_annuel_rejoint_l_annee_de_son_contrat(donnees):
    charger(donnees)
    ranger(donnees, "depot/av.pdf", pdf("suravenir_av_2025.txt") + b"\n")
    bilan = traiter_dossier_depot(donnees, donnees / "depot", CONNECTEURS)
    assert bilan.importes == ["av.pdf"]
    assert (donnees / "archives/Alice/AV - Suravenir - Vie Plus 270549974/2025/av.pdf").exists()


def test_un_pret_va_au_dossier_du_credit_et_non_au_compte_courant_de_meme_numero(donnees):
    charger(donnees)
    pret = (donnees / "Crédits/RP - BNP - 6783/pret.csv").read_bytes() + b"\n"
    ranger(donnees, "depot/pret.csv", pret)
    traiter_dossier_depot(donnees, donnees / "depot", CONNECTEURS)
    assert (donnees / "archives/Crédits/RP - BNP - 6783/pret.csv").exists()


def test_un_fichier_deja_archive_est_mis_de_cote_sans_doublon(donnees):
    charger(donnees)
    ranger(donnees, "depot/copie.csv", (EXEMPLES / "bnp_courant.csv").read_bytes())
    bilan = traiter_dossier_depot(donnees, donnees / "depot", CONNECTEURS)
    assert (bilan.importes, bilan.deja_presents) == ([], ["copie.csv"])
    assert (donnees / "depot/importes/copie.csv").exists()


def test_un_compte_inconnu_attend_son_titulaire_dans_le_dossier(donnees):
    charger(donnees)
    inconnu = (EXEMPLES / "bnp_livret.csv").read_bytes().replace(b"****5678", b"****4321")
    ranger(donnees, "depot/inconnu.csv", inconnu)
    ranger(donnees, "depot/notes.csv", b"pas un export")
    erreurs = charger(donnees).erreurs
    assert any("inconnu.csv" in e and "encore inconnu" in e for e in erreurs)
    assert any("notes.csv" in e and "aucun connecteur" in e for e in erreurs)
    assert (donnees / "depot/inconnu.csv").exists() and (donnees / "depot/notes.csv").exists()


def test_le_dossier_surveille_peut_etre_ailleurs(donnees, tmp_path_factory):
    ailleurs = tmp_path_factory.mktemp("telechargements")
    charger(donnees)
    ecrire_configuration(donnees, {"dossiers": {"depot": str(ailleurs)}}, CONNECTEURS, set())
    (ailleurs / "mai.csv").write_bytes(_courant_de_mai())
    charger(donnees)
    assert (ailleurs / "importes/mai.csv").exists()


@pytest.mark.parametrize(("chemin", "motif"), [("relatif/depot", "chemin complet"), ("ARCHIVES", "data/archives")])
def test_un_dossier_de_depot_mal_place_est_refuse(donnees, chemin, motif):
    chemin = str(donnees / "archives" / "x") if chemin == "ARCHIVES" else chemin
    with pytest.raises(ConfigurationInvalide, match=motif):
        ecrire_configuration(donnees, {"dossiers": {"depot": chemin}}, CONNECTEURS, set())


def test_la_page_range_sans_titulaire_un_fichier_de_compte_connu(donnees):
    charger(donnees)
    resultat = deposer_releve(donnees, "", "mai.csv", _courant_de_mai())
    assert resultat["chemin"] == "archives/Alice/CC - BNP - 1234/mai.csv" and resultat["connecteur"] == "bnp_csv"


def test_la_page_demande_le_titulaire_d_un_compte_inconnu(donnees):
    charger(donnees)
    inconnu = (EXEMPLES / "bnp_livret.csv").read_bytes().replace(b"****5678", b"****4321")
    with pytest.raises(DepotRefuse, match="indiquez son titulaire"):
        deposer_releve(donnees, "", "inconnu.csv", inconnu)
