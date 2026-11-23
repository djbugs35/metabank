"""Bien locatif (MODELE § 7.12) : loyers, charges et mensualités du compte locatif ; rendements et trésorerie."""

import json
from decimal import Decimal

import pytest

from metabank.web import vues
from tests.conftest import ranger

pytestmark = pytest.mark.usefixtures("pdf_simules")

# Trois mois : loyer 800 €, mensualité 500 €, taxe foncière 300 € une fois, un virement depuis un autre compte.
EXPORT_LOCATIF = (
    "Compte locatif;Compte locatif;****4444;31/03/2026;;1 000,00\n"
    + "".join(
        f"{jour}/2026;VIREMENT;VIR SEPA RECU;VIR SEPA RECU /DE M LOCATAIRE /MOTIF LOYER;800,00\n"
        f"{jour}/2026;PRELEVEMENT;ECHEANCE PRET;ECHEANCE PRET 1234;-500,00\n"
        for jour in ("01/01", "01/02", "01/03")
    )
    + "15/02/2026;PRELEVEMENT;PRLV SEPA;PRLV SEPA DGFIP TAXE FONCIERE;-300,00\n"
    + "20/02/2026;VIREMENT INTERNE;VIR CPTE A CPTE RECU;VIR CPTE A CPTE RECU /DE ALICE;200,00\n"
)
MOIS = Decimal(90) / Decimal("30.44")


@pytest.fixture
def avec_locatif(donnees):
    ranger(donnees, "Alice/LOCATIF - BNP - 4444/export.csv", EXPORT_LOCATIF.encode())
    (donnees / "corrections.json").write_text(
        json.dumps({"biens": {"1234": {"nom": "Bien locatif", "valeur": 200000}}})
    )
    return donnees


def test_loyers_charges_et_mensualites_viennent_du_compte_locatif_ramenes_a_l_annee(avec_locatif):
    b = vues.etat(avec_locatif)["locatif"]
    annuel = Decimal(12) / MOIS
    assert b["loyers"] == pytest.approx(float(2400 * annuel), abs=0.01)
    assert b["echeances"] == pytest.approx(float(1500 * annuel), abs=0.01)
    assert b["charges"] == pytest.approx(float(300 * annuel), abs=0.01)
    assert b["tresorerie_mensuelle"] == pytest.approx(float(600 / MOIS), abs=0.01)


def test_les_rendements_se_rapportent_a_la_valeur_saisie_du_bien(avec_locatif):
    b = vues.etat(avec_locatif)["locatif"]
    assert b["rendement_brut"] == pytest.approx(b["loyers"] / 200000, abs=1e-6)
    assert b["rendement_net"] == pytest.approx((b["loyers"] - b["charges"]) / 200000, abs=1e-6)
    assert b["interets"] > 0
    assert b["rendement_apres_interets"] == pytest.approx(
        (b["loyers"] - b["charges"] - b["interets"]) / 200000, abs=1e-6
    )


def test_sans_valeur_du_bien_les_montants_restent_et_les_rendements_disparaissent(avec_locatif):
    (avec_locatif / "corrections.json").write_text("{}")
    b = vues.etat(avec_locatif)["locatif"]
    assert b["loyers"] > 0 and (b["rendement_brut"], b["interets"]) == (None, None)


def test_sans_compte_locatif_pas_de_bloc(donnees):
    assert vues.etat(donnees)["locatif"] is None
