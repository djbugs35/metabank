"""Allocation (MODELE § 13) : classes déduites ou choisies, répartition, concentration, cible, rééquilibrage."""

from decimal import Decimal

import pytest

from metabank.allocation import A_CLASSER, Position, classe_deduite, concentrations, derives, reequilibrer
from metabank.configuration import ConfigurationInvalide, ecrire_allocation, ecrire_configuration, lire_configuration
from metabank.web.allocation_vues import enregistrer_allocation, etat_allocation

pytestmark = pytest.mark.usefixtures("pdf_simules")


@pytest.mark.parametrize(
    ("libelle", "classe"),
    [
        ("FONDS EUROS COMPARTIMENT LIBRE", "Fonds en euros"), ("FCPR ISATIS CAPITAL VIE RETRAITE", "Capital-investissement"),
        ("BGF US FLEXIBLE EQUITY E2 EUR", "Actions"), ("IVO EMERGINIG MARKETS CORPORATE", "Obligations"),
        ("Athena Degressif Quotidien Energie Avril 2026", "Produits structurés"), ("SCPI PRIMOVIE", "Immobilier"),
        ("DEDIE RENDEMENT JUIN 2024", A_CLASSER),
    ],
)  # fmt: skip
def test_la_classe_se_deduit_des_mots_du_libelle(libelle, classe):
    assert classe_deduite(libelle) == classe


def test_le_reequilibrage_par_les_versements_atteint_la_cible_sans_rien_vendre():
    valeurs = {"Actions": Decimal(30000), "Obligations": Decimal(10000)}
    a_verser = reequilibrer(valeurs, {"Actions": Decimal("0.5"), "Obligations": Decimal("0.5")})
    assert a_verser == {"Actions": Decimal(0), "Obligations": Decimal(20000)}
    assert reequilibrer(valeurs, {}) == {}


def test_la_repartition_couvre_fonds_livrets_et_comptes_courants(donnees):
    a = etat_allocation(donnees)
    noms = [r["nom"] for r in a["repartition"]]
    assert {"Livrets", "Comptes courants"} <= set(noms)
    assert sum(r["part"] for r in a["repartition"]) == pytest.approx(1)
    assert sum(r["montant"] for r in a["repartition"]) == pytest.approx(a["total"])


def test_un_fonds_de_plus_de_vingt_pour_cent_est_signale():
    fonds = [Position(str(v), "Fonds", "Alice", "AV", "Actions", False, Decimal(v)) for v in (25, 20, 55)]
    assert [p.valeur for p in concentrations(fonds, Decimal(100))] == [25, 55]


def test_la_classe_choisie_remplace_la_classe_deduite(donnees):
    fonds = etat_allocation(donnees)["positions"][0]
    autre = "Diversifiés" if fonds["classe"] != "Diversifiés" else "Actions"
    apres = enregistrer_allocation(donnees, {"classes": {fonds["cle"]: autre}, "cible": {}})
    choisi = next(p for p in apres["positions"] if p["cle"] == fonds["cle"])
    assert (choisi["classe"], choisi["choisie"]) == (autre, True)


def test_une_cible_dont_la_somme_n_est_pas_100_est_refusee(tmp_path):
    with pytest.raises(ConfigurationInvalide, match="100"):
        ecrire_allocation(tmp_path, {}, {"Actions": 60, "Obligations": 30})
    with pytest.raises(ConfigurationInvalide, match="classe inconnue"):
        ecrire_allocation(tmp_path, {"FR0000000000": "Crypto"}, {})


def test_classes_et_cible_survivent_a_l_onglet_configuration(tmp_path):
    ecrire_allocation(tmp_path, {"FR0000000000": "Actions"}, {"Actions": 60, "Obligations": 40})
    ecrire_configuration(tmp_path, {"parametres": {"assistant_actif": True}}, [], set())
    configuration = lire_configuration(tmp_path)
    assert configuration["classes"] == {"FR0000000000": "Actions"} and configuration["cible"]["Actions"] == 60


def test_la_vue_d_une_personne_ne_garde_que_ses_contrats_et_comptes(donnees):
    foyer, alice = etat_allocation(donnees), etat_allocation(donnees, "Alice")
    assert {p["titulaire"] for p in alice["positions"]} == {"Alice"} and alice["total"] < foyer["total"]


def test_une_classe_qui_s_ecarte_de_sa_cible_de_plus_de_cinq_points_derive():
    parts = {"Actions": Decimal("0.62"), "Obligations": Decimal("0.38")}
    assert derives(parts, {"Actions": Decimal("0.55"), "Obligations": Decimal("0.45")}) == {
        "Actions": Decimal("0.07"), "Obligations": Decimal("-0.07"),
    }  # fmt: skip
    assert derives(parts, {"Actions": Decimal("0.60"), "Obligations": Decimal("0.40")}) == {}
