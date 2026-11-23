"""Revue mensuelle : actions tirées du synoptique, des échéances, du budget, de l'allocation ; trace dans data/revues/."""

import json
from datetime import date

import pytest

from metabank.__main__ import main
from metabank.configuration import ecrire_objectifs
from metabank.revue import SUJETS, Action, Revue, en_texte, enregistrer_revue, faire_revue
from metabank.web import vues
from tests.conftest import ranger

pytestmark = pytest.mark.usefixtures("pdf_simules")
AUJOURD_HUI = date(2026, 11, 23)


def test_un_compte_en_retard_demande_son_fichier_avec_le_mode_d_emploi(donnees):
    revue = faire_revue(donnees, AUJOURD_HUI)
    a_deposer = [a for a in revue.actions if a.sujet == "Fichiers à déposer"]
    assert any("Compte courant" in a.texte and "Télécharger mes opérations" in a.detail for a in a_deposer)


def test_les_echeances_proches_et_les_objectifs_depasses_figurent_dans_la_revue(donnees):
    ecrire_objectifs(donnees, {"Alimentation": 100})
    sujets = {a.sujet for a in faire_revue(donnees, AUJOURD_HUI).actions}
    assert {"Échéances", "Budget"} <= sujets


def test_les_fichiers_non_lus_sont_rappeles(donnees):
    ranger(donnees, "Alice/CC - BNP - 1234/abime.csv", b"Compte;x;****1234;01/01/2026;;1,00\nligne;cassee\n")
    assert any(a.sujet == "Fichiers non lus" for a in faire_revue(donnees, AUJOURD_HUI).actions)


def test_la_revue_en_texte_suit_l_ordre_des_sujets():
    texte = en_texte(Revue("2026-11", [Action("Budget", "B"), Action("Fichiers à déposer", "A", "comment")]))
    assert texte.index("## Fichiers à déposer") < texte.index("## Budget") and "comment" in texte
    assert en_texte(Revue("2026-11", [])).endswith("Rien à signaler ce mois-ci.\n")
    assert SUJETS[0] == "Fichiers à déposer"


def test_la_revue_du_mois_est_gardee_une_fois_puis_remplacee_seulement_sur_demande(donnees):
    revue = faire_revue(donnees, AUJOURD_HUI)
    chemin = enregistrer_revue(donnees, revue, remplacer=False)
    chemin.write_text("modifiée")
    assert enregistrer_revue(donnees, revue, remplacer=False).read_text() == "modifiée"
    assert enregistrer_revue(donnees, revue).read_text().startswith("# Revue de 2026-11")


def test_la_commande_revue_ecrit_le_fichier_du_mois(donnees, capsys):
    assert main(["revue", "--donnees", str(donnees)]) == 0
    assert "Enregistrée" in capsys.readouterr().out
    assert len(list((donnees / "revues").glob("*.md"))) == 1


def test_le_dossier_des_revues_n_est_pas_un_titulaire(donnees):
    enregistrer_revue(donnees, faire_revue(donnees, AUJOURD_HUI))
    assert "revues" not in vues.etat(donnees)["titulaires"]
    assert json.dumps(vues.etat(donnees)["erreurs"]).count("revues") == 0
