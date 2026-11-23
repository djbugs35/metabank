"""Contrat, registre et journal des connecteurs, avec les connecteurs fictifs de tests/connecteurs_fictifs/."""

from datetime import date

import pytest

from metabank.base.integration import FICHIER_BASE, importer_fichier, reconstruire
from metabank.base.journal import lire_journal, noter_sans_archive
from metabank.base.lot import LectureImpossible
from metabank.base.schema import ouvrir
from metabank.connecteurs.registre import (
    AccesCompte,
    AucunAccesDirect,
    ConnecteurInconnu,
    composer_lecteur,
    lister_connecteurs,
    synchroniser_compte,
    trouver,
)
from tests.connecteurs_fictifs.banque_directe import BanqueDirecte
from tests.connecteurs_fictifs.releve_texte import ReleveTexte

CONNECTEURS = lister_connecteurs("tests.connecteurs_fictifs")
CLE = "FICTIVE:courant:****1234"
PROVENANCE = "Alice/CC - Fictive - 1234"
JOUR = date(2026, 3, 2)


def _journal(dossier):
    connexion = ouvrir(dossier / FICHIER_BASE)
    try:
        return lire_journal(connexion)
    finally:
        connexion.close()


class SecoursDirect(BanqueDirecte):
    """Deuxième accès direct, pour essayer le secours."""

    nom = "secours_direct"
    reglages = ()


def test_un_connecteur_s_ajoute_en_ecrivant_un_seul_module():
    assert [c.nom for c in CONNECTEURS] == ["banque_directe", "releve_texte"]


def test_un_module_sans_connecteur_est_signale():
    with pytest.raises(TypeError, match="oubli"):
        lister_connecteurs("tests.connecteurs_sans_constante")


def test_le_paquet_des_connecteurs_de_metabank_se_charge():
    assert all(c.nom for c in lister_connecteurs())


def test_un_nom_inconnu_est_signale():
    with pytest.raises(ConnecteurInconnu):
        trouver(CONNECTEURS, "absent")


def test_un_connecteur_est_actif_quand_ses_reglages_sont_renseignes():
    direct = trouver(CONNECTEURS, "banque_directe")
    assert not direct.est_actif({})
    assert not direct.est_actif({"banque_directe.jeton": "  "})
    assert direct.est_actif({"banque_directe.jeton": "x"})
    assert trouver(CONNECTEURS, "releve_texte").est_actif({})


def test_chaque_fichier_va_au_connecteur_qui_le_reconnait():
    lire = composer_lecteur(CONNECTEURS)
    lot = lire(PROVENANCE, "r.txt", b"RELEVE\n2026-01-05;Boulangerie;-3.50\n")
    assert lot is not None and lot.connecteur == "releve_texte"
    assert lire(PROVENANCE, "x.bin", b"inconnu") is None


def test_un_fichier_reconnu_par_deux_connecteurs_est_refuse_plutot_que_confie_au_hasard():
    jumeau = ReleveTexte()
    jumeau.nom = "jumeau"
    with pytest.raises(LectureImpossible, match="jumeau"):
        composer_lecteur([*CONNECTEURS, jumeau])(PROVENANCE, "r.txt", b"RELEVE\n")


def test_une_synchronisation_archive_la_reponse_et_l_enregistre(tmp_path):
    acces = AccesCompte(CLE, PROVENANCE, "banque_directe")
    resultat = synchroniser_compte(tmp_path, CONNECTEURS, {"banque_directe.jeton": "x"}, acces, JOUR)
    assert (resultat.connecteur, resultat.elements) == ("banque_directe", 1)
    assert resultat.chemin == f"{PROVENANCE}/banque_directe-2026-03-02.json"


def test_l_acces_de_secours_prend_le_relais_et_l_echec_du_principal_est_journalise(tmp_path):
    connecteurs = [*CONNECTEURS, SecoursDirect()]
    acces = AccesCompte(CLE, PROVENANCE, "banque_directe", "secours_direct")
    resultat = synchroniser_compte(tmp_path, connecteurs, {"banque_directe.jeton": "refuse"}, acces, JOUR)
    assert resultat.elements == 1
    journal = _journal(tmp_path)
    assert [(e.connecteur, e.resultat) for e in journal] == [("secours_direct", "ok"), ("banque_directe", "erreur")]
    assert (journal[1].compte_cle, journal[1].message, journal[1].archive) == (CLE, "accord expiré", "")


def test_sans_acces_qui_reponde_le_compte_est_signale_non_a_jour(tmp_path):
    acces = AccesCompte(CLE, PROVENANCE, "banque_directe", "releve_texte")
    with pytest.raises(AucunAccesDirect, match="accord expiré"):
        synchroniser_compte(tmp_path, CONNECTEURS, {"banque_directe.jeton": "refuse"}, acces, JOUR)
    with pytest.raises(AucunAccesDirect, match="aucun accès direct actif"):
        synchroniser_compte(tmp_path, CONNECTEURS, {}, acces, JOUR)


def test_une_reponse_archivee_se_relit_meme_si_l_acces_a_ete_retire_depuis(tmp_path):
    acces = AccesCompte(CLE, PROVENANCE, "banque_directe")
    synchroniser_compte(tmp_path, CONNECTEURS, {"banque_directe.jeton": "x"}, acces, JOUR)
    reconstruire(tmp_path, composer_lecteur(CONNECTEURS))
    assert [(e.connecteur, e.resultat, e.compte_cle) for e in _journal(tmp_path)] == [("banque_directe", "ok", CLE)]


def test_le_journal_rend_les_entrees_recentes_d_abord_a_partir_d_une_date(tmp_path):
    lire = composer_lecteur(CONNECTEURS)
    importer_fichier(tmp_path, PROVENANCE, "r.txt", b"RELEVE\n2026-01-05;Boulangerie;-3.50\n", lire)
    connexion = ouvrir(tmp_path / FICHIER_BASE)
    noter_sans_archive(connexion, "banque_directe", CLE, "refus", "quota atteint")
    tout = lire_journal(connexion)
    recent = lire_journal(connexion, depuis=tout[0].le)
    with pytest.raises(ValueError, match="inconnu"):
        noter_sans_archive(connexion, "banque_directe", CLE, "peut-être", "")
    connexion.close()
    assert [e.connecteur for e in tout] == ["banque_directe", "releve_texte"]
    assert [e.message for e in recent] == ["quota atteint"]
