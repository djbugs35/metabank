"""Simulateur d'arbitrage (MODELE § 14) : effet des frais à rendement égal, coût immédiat, point mort."""

from decimal import Decimal

import pytest

from metabank.arbitrage import simuler_arbitrage
from metabank.releves import lire_dossier
from metabank.web.allocation_vues import etat_allocation, simuler_arbitrage_saisi

pytestmark = pytest.mark.usefixtures("pdf_simules")


def test_un_fonds_moins_cher_rattrape_les_frais_d_arbitrage_puis_les_depasse():
    a = simuler_arbitrage(Decimal(10000), Decimal(2), Decimal("0.5"), Decimal(1), Decimal(5), 15)
    assert a.cout_immediat == Decimal(100)
    assert a.garder[15] == pytest.approx(Decimal(10000) * Decimal("1.03") ** 15)
    assert a.arbitrer[15] == pytest.approx(Decimal(9900) * Decimal("1.045") ** 15)
    assert a.point_mort == 1 and a.ecart > 0


def test_sans_baisse_de_frais_un_arbitrage_payant_n_a_pas_de_point_mort():
    a = simuler_arbitrage(Decimal(10000), Decimal(1), Decimal(1), Decimal("0.5"), Decimal(5), 10)
    assert a.point_mort is None and a.ecart < 0


def test_les_frais_d_un_fonds_viennent_du_tableau_de_son_dernier_releve(donnees):
    releves = lire_dossier(donnees)[0]
    connus = {f.isin: f.frais_totaux for r in releves for f in r.releve.frais_supports}
    positions = etat_allocation(donnees)["positions"]
    assert all(p["frais_totaux"] == float(connus[p["cle"]]) for p in positions if p["cle"] in connus)
    assert any(p["frais_totaux"] is None for p in positions)


@pytest.mark.parametrize(
    ("cle", "valeur"), [("montant", -1), ("frais_arbitrage", 6), ("horizon", 0), ("rendement", "x")]
)
def test_une_saisie_hors_bornes_est_refusee(cle, valeur):
    saisie = {"montant": 1000, "frais_source": 2, "frais_cible": 1, "frais_arbitrage": 0, "rendement": 5, "horizon": 15}
    with pytest.raises(ValueError, match=cle):
        simuler_arbitrage_saisi(None, {**saisie, cle: valeur})
