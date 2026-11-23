"""Synoptique : fraîcheur de chaque compte (MODELE § 9), journal des 30 derniers jours, sorties de la machine."""

import json
from datetime import date, datetime

import pytest

from metabank.base.integration import FICHIER_BASE
from metabank.base.journal import noter_sans_archive
from metabank.base.schema import ouvrir
from metabank.synoptique import A_JOUR, EN_RETARD, JAMAIS, TRES_EN_RETARD, evaluer_fraicheur
from metabank.web.synoptique_vues import etat_synoptique

pytestmark = pytest.mark.usefixtures("pdf_simules")

AUJOURD_HUI = date(2026, 4, 30)
COURANT = "BNP:courant:****1234"


@pytest.mark.parametrize(
    ("derniere", "frequence", "attendu"),
    [
        (date(2026, 4, 1), 30, A_JOUR),
        (date(2026, 3, 31), 30, A_JOUR),
        (date(2026, 3, 30), 30, EN_RETARD),
        (date(2026, 3, 1), 30, EN_RETARD),
        (date(2026, 2, 28), 30, TRES_EN_RETARD),
        (None, 30, JAMAIS),
        (date(2020, 1, 1), None, A_JOUR),
    ],
)
def test_la_fraicheur_compare_l_age_de_la_derniere_donnee_a_la_frequence_attendue(derniere, frequence, attendu):
    assert evaluer_fraicheur(derniere, frequence, AUJOURD_HUI) == attendu


def _ligne(etat: dict, cle: str) -> dict:
    return next(c for c in etat["comptes"] if c["cle"] == cle)


def test_chaque_compte_a_sa_derniere_donnee_et_sa_fraicheur(donnees):
    courant = _ligne(etat_synoptique(donnees, AUJOURD_HUI), COURANT)
    # Export fictif : solde au 31/03/2026, 30 jours avant AUJOURD_HUI.
    assert (courant["derniere_donnee"], courant["frequence_jours"], courant["fraicheur"]) == ("2026-03-31", 30, A_JOUR)
    assert courant["principal"] == "Export des opérations BNP Paribas (CSV)" and courant["reseau"] == "local"
    assert "Télécharger mes opérations" in courant["mode_emploi"]
    assert courant["alimente"] == "solde, opérations, budget"


def test_la_frequence_saisie_change_la_fraicheur(donnees):
    (donnees / "configuration.json").write_text(json.dumps({"comptes": {COURANT: {"frequence_jours": 7}}}))
    assert _ligne(etat_synoptique(donnees, AUJOURD_HUI), COURANT)["fraicheur"] == TRES_EN_RETARD


def test_le_journal_du_compte_compte_reussites_et_echecs_sur_30_jours(donnees):
    etat_synoptique(donnees, AUJOURD_HUI)
    connexion = ouvrir(donnees / FICHIER_BASE)
    noter_sans_archive(connexion, "bnp_csv", COURANT, "erreur", "service injoignable")
    connexion.close()
    aujourd_hui = datetime.now().astimezone().date()
    courant = _ligne(etat_synoptique(donnees, aujourd_hui), COURANT)
    assert (courant["reussis_30_jours"], courant["echecs_30_jours"]) == (1, 1)
    assert [e["resultat"] for e in courant["journal"]] == ["erreur", "ok"]
    assert courant["journal"][1]["fichier"] == "export.csv"


def test_le_journal_ancien_ne_compte_pas_dans_les_30_jours(donnees):
    courant = _ligne(etat_synoptique(donnees, date(2099, 1, 1)), COURANT)
    assert (courant["reussis_30_jours"], courant["echecs_30_jours"], len(courant["journal"])) == (0, 0, 1)


def test_seul_l_assistant_sort_de_la_machine_et_son_etat_suit_la_configuration(donnees):
    (donnees / "configuration.json").write_text(json.dumps({"parametres": {"assistant_actif": False}}))
    sorties = etat_synoptique(donnees, AUJOURD_HUI)["sorties"]
    assert [(s["nom"], s["reseau"], s["etat"]) for s in sorties] == [("Assistant Claude", "claude", "désactivé")]
    assert "ni numéro" in sorties[0]["contenu"]


def test_sans_donnees_le_synoptique_est_vide(tmp_path):
    assert etat_synoptique(tmp_path / "absent", AUJOURD_HUI)["comptes"] == []
