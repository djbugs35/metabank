"""Crédits (MODELE § 7.11) : tableau d'amortissement, rembourser ou placer, assurance emprunteur."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from metabank.banque.credit import analyser_credit, echeances_a_venir
from metabank.banque.credit_simulation import comparer_remboursement, cout_assurance, echeancier
from metabank.web import vues
from metabank.web.credits_vues import simuler_remboursement
from tests.test_credit import _credit

pytestmark = pytest.mark.usefixtures("pdf_simules")
AUJOURD_HUI = date(2026, 6, 20)


def test_le_tableau_rembourse_tout_le_capital_avec_des_interets_qui_baissent():
    tableau = echeancier(Decimal(12000), Decimal("0.01"), Decimal("1066.19"), date(2026, 1, 1), 5)
    assert tableau.mois == 12
    assert sum((a.capital for a in tableau.annees), Decimal(0)) == Decimal(12000)
    assert tableau.annees[-1].restant_fin == 0
    assert tableau.interets == pytest.approx(Decimal("794.28"), abs=Decimal("0.10"))


def test_une_mensualite_qui_ne_couvre_pas_les_interets_est_refusee():
    with pytest.raises(ValueError, match="intérêts"):
        echeancier(Decimal(100000), Decimal("0.01"), Decimal(1000), date(2026, 1, 1), 5)


def test_les_echeances_a_venir_suivent_le_jour_du_pret():
    assert echeances_a_venir(date(2026, 1, 20), 31, 3) == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_rembourser_economise_des_interets_et_raccourcit_le_pret():
    analyse = analyser_credit(_credit(), [])
    r = comparer_remboursement(analyse, Decimal(20000), Decimal("0.02"), AUJOURD_HUI)
    assert r.interets_economises > 0 and r.mois_gagnes > 0
    # Plafond légal : min(6 mois d'intérêts sur 20 000 €, 3 % de 100 000 €).
    assert r.indemnites_max == min(Decimal(20000) * analyse.taux_annuel / 12 * 6, Decimal(3000)).quantize(
        Decimal("0.01")
    )
    assert r.patrimoine_si_place > Decimal(20000)


def test_placer_gagne_quand_le_placement_rapporte_bien_plus_que_le_pret():
    analyse = analyser_credit(_credit(), [])
    assert comparer_remboursement(analyse, Decimal(20000), Decimal("0.08"), AUJOURD_HUI).ecart < 0
    assert comparer_remboursement(analyse, Decimal(20000), Decimal(0), AUJOURD_HUI).ecart > 0


@pytest.mark.parametrize("montant", [Decimal(0), Decimal(200000)])
def test_un_montant_hors_du_capital_restant_est_refuse(montant):
    with pytest.raises(ValueError, match="capital restant"):
        comparer_remboursement(analyser_credit(_credit(), []), montant, Decimal("0.02"), AUJOURD_HUI)


def test_l_assurance_est_l_ecart_entre_le_preleve_et_la_mensualite_calculee():
    analyse = analyser_credit(_credit(), [])
    avec = replace(analyse, mensualite_prelevee=analyse.mensualite + Decimal(30))
    assert cout_assurance(avec) == (Decimal(30), Decimal(30) * analyse.mois_restants)
    assert cout_assurance(analyse) is None


def test_la_page_compare_rembourser_et_placer_pour_un_credit_des_donnees(donnees):
    r = simuler_remboursement(donnees, {"cle": "1234", "montant": "10000", "rendement": "2"}, AUJOURD_HUI)
    assert r["interets_economises"] > 0 and r["ecart"] == pytest.approx(
        r["patrimoine_si_rembourse"] - r["patrimoine_si_place"], abs=0.01
    )


@pytest.mark.parametrize(
    ("saisie", "motif"),
    [({"cle": "0000", "montant": 1}, "inconnu"), ({"cle": "1234", "montant": "x"}, "nombres"),
     ({"cle": "1234", "montant": 1, "rendement": 50}, "rendement")],
)  # fmt: skip
def test_une_simulation_hors_bornes_est_refusee(donnees, saisie, motif):
    with pytest.raises(ValueError, match=motif):
        simuler_remboursement(donnees, saisie, AUJOURD_HUI)


def test_le_tableau_de_bord_donne_l_echeancier_de_chaque_credit(donnees):

    credit = vues.etat(donnees, AUJOURD_HUI)["credits"][0]
    assert credit["echeancier"][0]["annee"] == 2026 and credit["echeancier"][-1]["restant"] == 0
