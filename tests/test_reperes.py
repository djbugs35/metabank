"""Repères publics (MODELE § 10) : valeurs publiées, sources, et leur place dans l'état de l'application."""

from dataclasses import fields
from decimal import Decimal

import pytest

from metabank.reperes import SOURCES, Reperes, reperes_de
from metabank.web import vues

pytestmark = pytest.mark.usefixtures("pdf_simules")


def test_les_reperes_2024_sont_ceux_publies_par_leurs_sources():
    r = reperes_de(2024)
    assert (r.fonds_euros, r.unites_de_compte, r.inflation, r.msci_world) == (
        Decimal("0.0263"), Decimal("0.054"), Decimal("0.02"), Decimal("0.266"),
    )  # fmt: skip
    assert r.livret_a == Decimal("0.03")


def test_une_annee_sans_publication_n_a_aucun_repere_devine():
    r = reperes_de(1999)
    assert (r.fonds_euros, r.unites_de_compte, r.inflation, r.msci_world) == (None, None, None, None)


def test_chaque_repere_a_sa_source():
    assert set(SOURCES) == {f.name for f in fields(Reperes)} - {"annee"}


def test_l_application_donne_les_reperes_des_annees_affichees(donnees):
    etat = vues.etat(donnees)
    annees = {str(a["annee"]) for v in etat["vues"] for a in v["annees"]}
    assert set(etat["reperes"]) == annees
    assert etat["reperes"]["2024"]["fonds_euros"] == 0.0263
    assert etat["sources_reperes"] == SOURCES
