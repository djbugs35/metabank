"""Fiche CSV d'un contrat (MODELE § 0) : écrite à côté des PDF, jamais réécrite, relue par l'application."""

from decimal import Decimal

import pytest

from metabank.connecteurs.registre import lister_connecteurs
from metabank.donnees import charger
from metabank.fiches import preparer_fiches
from metabank.releves import lire_releve
from metabank.releves.fiche import BOM, ENTETE, ecrire_fiche, lignes_du_releve, lire_fiche
from metabank.releves.suravenir_situation import lire_situation_suravenir
from metabank.web.serveur import ENVOIS_JSON
from metabank.web.vues import etat
from tests.conftest import EXEMPLES, pdf, ranger

pytestmark = pytest.mark.usefixtures("pdf_simules")
DOSSIER_AV = "Alice/AV - Suravenir - Vie Plus 270549974/2025"


def _lu(nom: str):
    texte = (EXEMPLES / nom).read_text(encoding="utf-8")
    if nom == "suravenir_situation.txt":
        return lire_situation_suravenir(texte + "\nVIE PLUS - Filière de SURAVENIR\n", "situation.pdf")
    return lire_releve(texte, f"{nom}.pdf", "perp" if "cardif" in nom else None)


@pytest.mark.parametrize("nom", ["suravenir_av_2025.txt", "suravenir_per_2024.txt", "suravenir_situation.txt",
                                 "cardif_situation.txt"])  # fmt: skip
def test_la_fiche_rend_exactement_le_releve_lu_dans_le_pdf(nom):
    releve = _lu(nom)
    assert lire_fiche(ecrire_fiche(lignes_du_releve(releve))) == [releve]


def test_la_fiche_est_au_format_excel_francais():
    texte = ecrire_fiche(lignes_du_releve(_lu("suravenir_av_2025.txt")))
    assert texte.startswith(BOM + ENTETE)
    valeur = next(ligne for ligne in texte.splitlines() if ligne.startswith("synthese;") and ";valeur;" in ligne)
    assert valeur.startswith("synthese;31/12/2025;valeur;") and "," in valeur.split(";")[8]


def test_la_fiche_est_ecrite_a_cote_du_pdf_puis_jamais_reecrite(tmp_path):
    ranger(tmp_path, f"{DOSSIER_AV}/releve.pdf", pdf("suravenir_av_2025.txt"))
    assert preparer_fiches(tmp_path, lister_connecteurs()).ecrites == [f"{DOSSIER_AV}/metabank-2025.csv"]
    fiche = tmp_path / DOSSIER_AV / "metabank-2025.csv"
    corrigee = fiche.read_text(encoding="utf-8") + "anomalie;31/12/2025;;vu à la main;;;;;;releve.pdf\n"
    fiche.write_text(corrigee, encoding="utf-8")
    assert preparer_fiches(tmp_path, lister_connecteurs()).ecrites == []
    assert fiche.read_text(encoding="utf-8") == corrigee


def test_un_pdf_que_la_fiche_ne_cite_pas_y_est_ajoute_sans_toucher_au_reste(tmp_path):
    ranger(tmp_path, f"{DOSSIER_AV}/releve.pdf", pdf("suravenir_av_2025.txt"))
    preparer_fiches(tmp_path, lister_connecteurs())
    fiche = tmp_path / DOSSIER_AV / "metabank-2025.csv"
    fiche.write_text(fiche.read_text(encoding="utf-8").replace("Patrimoine Vie Plus", "Nom corrigé"), encoding="utf-8")
    ranger(tmp_path, f"{DOSSIER_AV}/copie.pdf", pdf("suravenir_av_2025.txt"))
    preparer_fiches(tmp_path, lister_connecteurs())
    releves = lire_fiche(fiche.read_text(encoding="utf-8"))
    assert [(r.fichier, r.produit) for r in releves] == [
        ("releve.pdf", "Nom corrigé"),
        ("copie.pdf", "Patrimoine Vie Plus"),
    ]


def test_relire_les_pdf_reecrit_la_fiche_et_efface_les_corrections(tmp_path):
    ranger(tmp_path, f"{DOSSIER_AV}/releve.pdf", pdf("suravenir_av_2025.txt"))
    preparer_fiches(tmp_path, lister_connecteurs())
    fiche = tmp_path / DOSSIER_AV / "metabank-2025.csv"
    origine = fiche.read_text(encoding="utf-8")
    fiche.write_text(origine.replace("Patrimoine Vie Plus", "Nom corrigé"), encoding="utf-8")
    preparer_fiches(tmp_path, lister_connecteurs(), relire=True)
    assert fiche.read_text(encoding="utf-8") == origine


def test_une_correction_faite_dans_la_fiche_change_les_chiffres_de_l_application(tmp_path):
    ranger(tmp_path, f"{DOSSIER_AV}/releve.pdf", pdf("suravenir_av_2025.txt"))
    [avant] = charger(tmp_path).releves
    fiche = tmp_path / DOSSIER_AV / "metabank-2025.csv"
    lignes = fiche.read_text(encoding="utf-8").splitlines()
    rang = next(i for i, ligne in enumerate(lignes) if ligne.startswith("synthese;31/12/2025;valeur;"))
    colonnes = lignes[rang].split(";")
    colonnes[8] = "12345,67"
    lignes[rang] = ";".join(colonnes)
    fiche.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    [apres] = charger(tmp_path).releves
    assert (avant.releve.valeur != apres.releve.valeur, apres.releve.valeur) == (True, Decimal("12345.67"))


def test_un_montant_illisible_dans_la_fiche_est_signale_avec_sa_ligne(tmp_path):
    ranger(tmp_path, f"{DOSSIER_AV}/releve.pdf", pdf("suravenir_av_2025.txt"))
    preparer_fiches(tmp_path, lister_connecteurs())
    fiche = tmp_path / DOSSIER_AV / "metabank-2025.csv"
    lignes = fiche.read_text(encoding="utf-8").splitlines()
    rang = next(i for i, ligne in enumerate(lignes) if ligne.startswith("synthese;31/12/2025;valeur;"))
    lignes[rang] = lignes[rang].replace(lignes[rang].split(";")[8], "douze")
    fiche.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    assert any(f"ligne {rang + 1} : montant illisible" in e for e in charger(tmp_path).erreurs)


def test_le_bouton_relire_les_pdf_rend_les_fiches_reecrites(tmp_path):
    ranger(tmp_path, f"{DOSSIER_AV}/releve.pdf", pdf("suravenir_av_2025.txt"))
    preparer_fiches(tmp_path, lister_connecteurs())
    reponse = ENVOIS_JSON["/api/fiches/relire"](tmp_path, {})
    assert reponse == {"ecrites": [f"{DOSSIER_AV}/metabank-2025.csv"], "illisibles": []}


def test_chaque_contrat_montre_sa_synthese_en_distinguant_le_document_du_calcul(donnees):
    fiches = {c["produit"]: c["fiche"] for c in etat(donnees)["contrats"]}
    cardif = next(f for nom, f in fiches.items() if "Cardif" in nom or "Essentiel" in nom)
    # Situation Cardif : valeur et versé imprimés ; le gagné n'y figure pas, il est calculé et dit comme tel.
    assert [(ligne["libelle"], ligne["origine"]) for ligne in cardif["lignes"]] == [
        ("Valeur", "document"), ("Cumul des versements", "document"), ("Gagné (valeur moins versé)", "calcul"),
    ]  # fmt: skip
    assert cardif["annees"] == [] and cardif["fichier"].startswith("metabank-")
