"""Projection retraite (MODELE § 12) : capital au départ, euros d'aujourd'hui, retrait mensuel, saisie bornée."""

from datetime import date
from decimal import Decimal

import pytest

from metabank.retraite import mois_jusqu_au_depart, projeter
from metabank.web.retraite_vues import simuler_retraite

pytestmark = pytest.mark.usefixtures("pdf_simules")
AUJOURD_HUI = date(2026, 11, 23)
SAISIE = {"titulaire": "Bruno", "annee_depart": 2040, "versement": 100, "inflation": 2, "duree_retrait": 20,
          "rendements": [1, 3, 5]}  # fmt: skip


def test_les_mois_courent_jusqu_au_premier_janvier_du_depart():
    assert mois_jusqu_au_depart(date(2026, 11, 23), 2027) == 2
    assert mois_jusqu_au_depart(date(2026, 11, 23), 2026) == 0


def test_sans_rendement_le_capital_est_la_somme_des_versements():
    s = projeter(Decimal(1000), Decimal(100), 24, Decimal(0), Decimal(0), 10)
    assert (s.capital, s.capital_reel, s.retrait_mensuel) == (Decimal(3400), Decimal(3400), Decimal(3400) / 120)


def test_le_capital_croit_au_rendement_compose_et_l_inflation_le_ramene_en_euros_d_aujourd_hui():
    s = projeter(Decimal(10000), Decimal(0), 120, Decimal("0.05"), Decimal("0.02"), 20)
    assert s.capital == pytest.approx(Decimal(10000) * Decimal("1.05") ** 10, rel=Decimal("1e-9"))
    assert s.capital_reel == pytest.approx(s.capital / Decimal("1.02") ** 10, rel=Decimal("1e-9"))
    # Retraits égaux sur 20 ans qui épuisent exactement le capital réel au même rendement.
    r = Decimal("1.05") ** (Decimal(1) / 12) - 1
    assert s.retrait_mensuel * (1 - (1 + r) ** -240) / r == pytest.approx(s.capital_reel, rel=Decimal("1e-9"))


def test_la_projection_retient_les_per_et_perp_du_titulaire(donnees):
    r = simuler_retraite(donnees, SAISIE, AUJOURD_HUI)
    assert len(r["contrats"]) == 2 and r["mois"] == 158
    capitaux = [s["capital"] for s in r["scenarios"]]
    assert capitaux == sorted(capitaux) and capitaux[0] > r["capital_actuel"]


def test_sans_per_ni_perp_il_faut_cocher_les_assurances_vie(donnees):
    with pytest.raises(ValueError, match="assurances vie"):
        simuler_retraite(donnees, {**SAISIE, "titulaire": "Alice"}, AUJOURD_HUI)
    assert simuler_retraite(donnees, {**SAISIE, "titulaire": "Alice", "inclure_av": True}, AUJOURD_HUI)["contrats"]


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [("annee_depart", 2020), ("versement", -1), ("duree_retrait", 0), ("inflation", "x"), ("rendements", [1, 2])],
)
def test_une_saisie_hors_bornes_est_refusee(donnees, champ, valeur):
    with pytest.raises(ValueError):
        simuler_retraite(donnees, {**SAISIE, champ: valeur}, AUJOURD_HUI)
