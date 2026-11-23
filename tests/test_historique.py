"""Historique mensuel du patrimoine (MODELE § 8.1) : soldes reconstitués, paliers des relevés, montants inconnus."""

from datetime import date
from decimal import Decimal

import pytest

from metabank.banque import lire_comptes
from metabank.historique import historique_patrimoine, jours_des_points, solde_au, valeur_au
from metabank.releves import lire_dossier
from metabank.web import vues

pytestmark = pytest.mark.usefixtures("pdf_simules")


def _compte(donnees, type_compte: str):
    return next(c for c in lire_comptes(donnees)[0] if c.type_compte == type_compte)


def test_les_points_sont_les_fins_des_douze_mois_precedents_puis_aujourd_hui():
    jours = jours_des_points(date(2026, 3, 15))
    assert (len(jours), jours[0], jours[1], jours[-2], jours[-1]) == (
        13, date(2025, 3, 31), date(2025, 4, 30), date(2026, 2, 28), date(2026, 3, 15),
    )  # fmt: skip


def test_le_solde_d_une_fin_de_mois_retire_les_operations_qui_suivent(donnees):
    courant = _compte(donnees, "courant")
    apres = sum((o.montant for o in courant.operations if o.jour > date(2026, 1, 31)), Decimal(0))
    assert solde_au(courant, date(2026, 1, 31)) == courant.solde - apres
    assert solde_au(courant, date(2026, 6, 30)) == courant.solde


def test_avant_la_premiere_operation_connue_le_solde_est_inconnu(donnees):
    assert solde_au(_compte(donnees, "courant"), date(2025, 11, 29)) is None
    assert solde_au(_compte(donnees, "courant"), date(2025, 11, 30)) is not None


def test_un_credit_est_projete_au_dela_de_son_export(donnees):
    credit = _compte(donnees, "credit")
    assert solde_au(credit, date(2026, 9, 30)) > credit.solde


def test_un_contrat_vaut_son_dernier_releve_publie_a_la_date(donnees):
    releves = [r for r in lire_dossier(donnees)[0] if r.releve.type_contrat == "assurance_vie"]
    arrete = releves[0].releve.date_arrete
    assert valeur_au(releves, arrete) == releves[0].releve.valeur
    assert valeur_au(releves, date(arrete.year, 1, 1)) is None


def test_avant_sa_premiere_valeur_un_compte_compte_a_cette_valeur_et_jamais_a_zero(donnees):
    releves, comptes = lire_dossier(donnees)[0], lire_comptes(donnees)[0]
    historique = historique_patrimoine(releves, comptes, {}, date(2026, 12, 15))
    credit = next(c for c in comptes if c.type_compte == "credit")
    # Le prêt fictif n'est connu qu'à partir du 4 janvier 2026 : avant, son premier capital connu est reporté.
    assert len(historique.points) == 13 and credit.libelle in historique.reportes
    assert historique.points[0].credits == historique.points[1].credits > 0
    assert historique.points[-1].net == historique.points[-1].actifs - historique.points[-1].credits


def test_un_compte_inconnu_au_dernier_point_reste_hors_courbe(donnees):
    releves, comptes = lire_dossier(donnees)[0], lire_comptes(donnees)[0]
    premier = min(r.releve.date_arrete for r in releves)
    historique = historique_patrimoine(releves, comptes, {}, premier)
    assert (
        historique.points[-1].actifs < historique_patrimoine(releves, comptes, {}, date(2026, 12, 15)).points[-1].actifs
    )


def test_la_valeur_d_un_bien_saisi_compte_a_chaque_point(donnees):
    releves, comptes = lire_dossier(donnees)[0], lire_comptes(donnees)[0]
    sans = historique_patrimoine(releves, comptes, {}, date(2026, 4, 15)).points
    avec = historique_patrimoine(
        releves, comptes, {"1234": {"nom": "Maison", "valeur": 300000}}, date(2026, 4, 15)
    ).points
    assert all(b.actifs - a.actifs == 300000 for a, b in zip(sans, avec, strict=True))


def test_l_application_donne_une_courbe_au_foyer_et_a_chaque_personne(donnees):
    etat = vues.etat(donnees, date(2026, 12, 15))
    assert set(etat["historique"]) == set(etat["patrimoine"])
    foyer = etat["historique"]["foyer"]
    assert len(foyer["points"]) == 13 and foyer["points"][-1]["actifs"] == etat["patrimoine"]["foyer"]["total"]
