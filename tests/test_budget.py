"""Budget (MODELE § 7.13) : dépenses régulières, objectifs par catégorie, d'une année sur l'autre."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from metabank.banque.budget import comparer_annees, depenses_par_mois, reperer_abonnements, suivre_objectifs
from metabank.banque.categories import classer
from metabank.banque.modele import Operation
from metabank.configuration import ConfigurationInvalide, ecrire_configuration, ecrire_objectifs, lire_configuration
from metabank.web import vues

pytestmark = pytest.mark.usefixtures("pdf_simules")
FIN = date(2026, 6, 30)


def _operations(libelle: str, montants: list[str], debut: date = date(2026, 1, 10)) -> list[Operation]:
    return [
        Operation(debut + timedelta(days=31 * rang), "PRELEVEMENT", "", libelle, -Decimal(m))
        for rang, m in enumerate(montants)
    ]


def test_un_prelevement_stable_sur_plusieurs_mois_est_repere():
    classees = classer(tuple(_operations("PRLV SEPA NETFLIX.COM 123", ["15.99"] * 4)), [])
    [abonnement] = reperer_abonnements(classees, FIN)
    assert (abonnement.montant_habituel, abonnement.mois, abonnement.cout_12_mois) == (
        Decimal("15.99"), 4, Decimal("63.96"),
    )  # fmt: skip


@pytest.mark.parametrize("montants", [["10", "50", "100", "20"], ["15.99", "15.99"]])
def test_des_montants_irreguliers_ou_trop_peu_de_mois_ne_font_pas_un_abonnement(montants):
    assert reperer_abonnements(classer(tuple(_operations("PRLV SEPA SALLE DE SPORT", montants)), []), FIN) == []


def test_un_objectif_depasse_le_dernier_mois_complet_est_signale():
    par_mois = depenses_par_mois(classer(tuple(_operations("FACTURE CARTE RESTAURANT", ["100", "200", "400"])), []))
    [objectif] = suivre_objectifs(par_mois, {"Restaurants": Decimal(250)}, ["2026-01", "2026-02", "2026-03"])
    assert objectif.depasse and objectif.depense_mois == 400
    assert objectif.moyenne_3_mois == Decimal(700) / 3


def test_la_comparaison_annuelle_demande_douze_mois_complets_et_vingt_quatre_pour_la_colonne_precedente():
    mois = [f"{2024 + (m - 1) // 12}-{(m - 1) % 12 + 1:02d}" for m in range(1, 25)]
    par_mois = {"Restaurants": {m: Decimal(10) for m in mois}}
    assert comparer_annees(par_mois, mois[:11]) == []
    assert comparer_annees(par_mois, mois[:12]) == [("Restaurants", Decimal(120), None)]
    assert comparer_annees(par_mois, mois) == [("Restaurants", Decimal(120), Decimal(120))]


def test_les_objectifs_se_gardent_quand_l_onglet_configuration_enregistre(tmp_path):
    ecrire_objectifs(tmp_path, {"Restaurants": 250, "Loisirs": ""})
    ecrire_configuration(tmp_path, {"parametres": {"assistant_actif": False}}, [], set())
    assert lire_configuration(tmp_path)["objectifs"] == {"Restaurants": 250}


@pytest.mark.parametrize("objectifs", [{"Restaurants": -1}, {"": 10}, {"Restaurants": "beaucoup"}])
def test_un_objectif_hors_format_est_refuse(tmp_path, objectifs):
    with pytest.raises(ConfigurationInvalide):
        ecrire_objectifs(tmp_path, objectifs)


def test_l_onglet_budget_recoit_abonnements_objectifs_et_categories(donnees):
    ecrire_objectifs(donnees, {"Alimentation": 100})
    courant = next(v for v in vues.etat(donnees)["banque"] if v["type"] == "courant")
    assert any("CARREFOUR" in a["marchand"] for a in courant["abonnements"])
    assert courant["objectifs"][0]["categorie"] == "Alimentation" and courant["objectifs"][0]["depasse"]
    assert "Alimentation" in courant["categories_budget"]
