"""Règles de classement des dépenses depuis la page : proposer, tester, enregistrer, appliquer (MODELE § 7.2)."""

import json

import pytest

from metabank.banque.categories import RegleInvalide, ecrire_regles, lire_regles, motif_suggere
from metabank.web import vues
from metabank.web.regles_vues import enregistrer_regles, essayer_regle, etat_regles
from tests.conftest import ranger

pytestmark = pytest.mark.usefixtures("pdf_simules")


EXPORT_AVEC_INCONNU = (
    "Compte Bruno;Compte Bruno;****7777;31/03/2026;;500,00\n"
    "05/03/2026;PAIEMENT CB;FACTURE CARTE;FACTURE CARTE DU 040326 TY VORN QUIMPER   CARTE   4974XXXXXXXX0000;-42,00\n"
    "06/03/2026;PAIEMENT CB;FACTURE CARTE;FACTURE CARTE DU 050326 TY VORN QUIMPER   CARTE   4974XXXXXXXX0000;-18,00\n"
)


def _courant(etat: dict) -> dict:
    return next(v for v in etat["banque"] if ":courant:****7777" in v["id"])


@pytest.fixture
def avec_inconnu(donnees):
    ranger(donnees, "Bruno/CC - BNP - 7777/export.csv", EXPORT_AVEC_INCONNU.encode())
    return donnees


def test_le_motif_propose_garde_le_marchand_sans_date_ni_carte():
    motif = motif_suggere("FACTURE CARTE DU 170226 AMAZON EU SARL   CARTE   4974XXXXXXXX0000")
    assert motif == r"AMAZON\s+EU\s+SARL"
    assert motif_suggere("FACTURE CARTE DU 040326 TY VORN QUIMPER   CARTE   4974XXXX") == r"TY\s+VORN\s+QUIMPER"


def test_tester_une_regle_dit_combien_d_operations_elle_classerait(donnees):
    resultat = essayer_regle(donnees, {"motif": "CARREFOUR"})
    assert resultat["nombre"] == 4 and resultat["montant"] == -800.0
    assert resultat["exemples"][0].startswith("FACTURE CARTE")


@pytest.mark.parametrize(("motif", "attendu"), [("", "vide"), ("(", "illisible"), ("x" * 201, "vide ou de plus")])
def test_un_motif_hors_format_est_refuse(donnees, motif, attendu):
    with pytest.raises(RegleInvalide, match=attendu):
        essayer_regle(donnees, {"motif": motif})


def test_une_regle_enregistree_classe_la_depense_dans_les_chiffres(avec_inconnu):
    avant = _courant(vues.etat(avec_inconnu))
    motif = next(o["motif"] for o in avant["non_classees"] if "TY VORN" in o["libelle"])
    assert essayer_regle(avec_inconnu, {"motif": motif})["nombre"] == 2
    enregistrer_regles(avec_inconnu, {"regles": [{"motif": motif, "categorie": "Crêperies"}]})
    apres = _courant(vues.etat(avec_inconnu))
    assert apres["non_classees"] == []
    assert [(c["nom"], c["montant"]) for c in apres["categories"]] == [("Crêperies", 60.0)]


def test_les_regles_gardent_leur_ordre_et_les_autres_cles_du_fichier(tmp_path):
    (tmp_path / "categories.json").write_text(json.dumps({"note": "à garder", "regles": []}))
    ecrire_regles(tmp_path, [{"motif": " A ", "categorie": "Un"}, {"motif": "B", "categorie": "Deux"}])
    assert lire_regles(tmp_path) == [("A", "Un"), ("B", "Deux")]
    assert json.loads((tmp_path / "categories.json").read_text())["note"] == "à garder"


@pytest.mark.parametrize("regles", [{"motif": "A"}, ["pas un objet"], [{"motif": "A", "categorie": ""}]])
def test_une_liste_de_regles_hors_format_est_refusee_sans_rien_ecrire(tmp_path, regles):
    with pytest.raises(RegleInvalide):
        ecrire_regles(tmp_path, regles)
    assert not (tmp_path / "categories.json").exists()


def test_l_onglet_propose_les_categories_connues_et_les_personnelles(tmp_path):
    ecrire_regles(tmp_path, [{"motif": "TY VORN", "categorie": "Crêperies"}])
    etat = etat_regles(tmp_path)
    assert etat["regles"] == [{"motif": "TY VORN", "categorie": "Crêperies"}]
    assert {"Crêperies", "Restaurants", "Autres dépenses"} <= set(etat["categories"])


def test_chaque_depense_non_classee_porte_un_motif_propose(avec_inconnu):
    non_classees = _courant(vues.etat(avec_inconnu))["non_classees"]
    assert non_classees and all(o["motif"] for o in non_classees)
