"""Fiscalité et échéances (MODELE § 11) : 8 ans des assurances vie, abattement, transfert des PER."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from metabank.bilan import BilanContrat, faire_bilans
from metabank.fiscalite import ABATTEMENT_COUPLE, ABATTEMENT_SEUL, _anniversaire, echeances, rachat_couvert
from metabank.releves import lire_dossier
from metabank.web import vues

pytestmark = pytest.mark.usefixtures("pdf_simules")
AUJOURD_HUI = date(2026, 11, 23)


def _bilans(donnees):
    return faire_bilans(lire_dossier(donnees)[0])


def test_le_rachat_couvert_par_l_abattement_suit_la_part_de_gain():
    bilan = _bilans_fictifs()
    assert rachat_couvert(bilan, ABATTEMENT_SEUL) == Decimal(4600) * Decimal(50000) / Decimal(10000)
    assert rachat_couvert(replace(bilan, gain_cumule=Decimal(100)), ABATTEMENT_COUPLE) == Decimal(50000)
    assert rachat_couvert(replace(bilan, gain_cumule=Decimal(-5)), ABATTEMENT_SEUL) is None


def _bilans_fictifs():
    return BilanContrat("Alice", "Suravenir", "Vie Plus", "000 123456789", "assurance_vie", date(2025, 12, 31),
                        Decimal(50000), (), Decimal(40000), Decimal(0), Decimal(10000), None,
                        date_ouverture=date(2019, 3, 30))  # fmt: skip


def test_les_8_ans_d_une_assurance_vie_viennent_de_sa_date_d_ouverture():
    bilan = _bilans_fictifs()
    [e] = echeances([replace(bilan, date_ouverture=date(2020, 3, 30))], AUJOURD_HUI, False)
    assert (e.jour, e.quoi) == (date(2028, 3, 30), "8 ans de l'assurance vie")
    assert _anniversaire(date(2020, 2, 29), 5) == date(2025, 2, 28)
    assert "4600 €" in e.detail and "23 000 €" in e.detail


def test_sans_date_d_ouverture_l_echeance_est_a_saisir_et_vient_en_dernier(donnees):
    liste = echeances(_bilans(donnees), AUJOURD_HUI, False)
    assert liste[-1].jour is None and "Corrections" in liste[-1].detail


def test_un_per_rappelle_le_31_decembre_et_la_gratuite_du_transfert(donnees):
    bilans = [replace(b, date_ouverture=date(2022, 5, 10)) if b.type_contrat == "per" else b for b in _bilans(donnees)]
    quoi = {e.quoi: e.jour for e in echeances(bilans, AUJOURD_HUI, True)}
    assert quoi["Versements déductibles de l'année"] == date(2026, 12, 31)
    assert quoi["Transfert du PER sans frais"] == date(2027, 5, 10)


def test_une_echeance_atteinte_depuis_plus_d_un_an_n_est_plus_affichee():
    ancienne = replace(_bilans_fictifs(), date_ouverture=date(2010, 1, 1))
    assert echeances([ancienne], AUJOURD_HUI, False) == []


def test_l_application_liste_les_echeances_du_foyer(donnees):
    etat = vues.etat(donnees, AUJOURD_HUI)
    assert etat["echeances"] and all(
        {"jour", "titulaire", "contrat", "quoi", "detail"} <= set(e) for e in etat["echeances"]
    )
