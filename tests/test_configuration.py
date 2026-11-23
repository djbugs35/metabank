"""Onglet Configuration : registre des comptes, réglages, paramètres ; titulaire saisi appliqué aux chiffres."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from metabank.configuration import ConfigurationInvalide, ecrire_configuration, lire_configuration
from metabank.connecteurs.contrat import ConnecteurFichier, Reglage
from metabank.connecteurs.registre import lister_connecteurs
from metabank.donnees import charger
from metabank.web import configuration_vues as vues_configuration
from metabank.web.configuration_vues import enregistrer_configuration, etat_configuration
from metabank.web.serveur import creer_serveur

pytestmark = pytest.mark.usefixtures("pdf_simules")

COURANT = "BNP:courant:****1234"
ASSURANCE_VIE = "Suravenir:assurance_vie:Alice:****6789"


class AvecReglages(ConnecteurFichier):
    """Connecteur de test : un réglage ordinaire, un secret."""

    nom = "avec_reglages"
    reglages = (Reglage("avec_reglages.dossier", "Dossier"), Reglage("avec_reglages.cle", "Clé", secret=True))

    def reconnaitre(self, nom: str, contenu: bytes) -> None:
        """Ne reconnaître aucun fichier."""


CONNECTEURS = [*lister_connecteurs(), AvecReglages()]


def _ecrire(dossier, configuration):
    return ecrire_configuration(dossier, configuration, CONNECTEURS, {COURANT, ASSURANCE_VIE})


def test_sans_fichier_la_configuration_est_vide_et_l_assistant_actif(tmp_path):
    assert lire_configuration(tmp_path) == {
        "comptes": {},
        "reglages": {},
        "parametres": {"assistant_actif": True},
        "dossiers": {"depot": ""},
        "objectifs": {},
    }


def test_une_configuration_valide_est_enregistree_puis_relue(tmp_path):
    saisie = {
        "comptes": {COURANT: {"titulaire": " Bruno ", "principal": "bnp_csv", "secours": "", "frequence_jours": 15}},
        "reglages": {"avec_reglages.dossier": " /Volumes/Depot ", "avec_reglages.cle": ""},
        "parametres": {"assistant_actif": False},
    }
    assert _ecrire(tmp_path, saisie) == {
        "comptes": {COURANT: {"titulaire": "Bruno", "principal": "bnp_csv", "secours": "", "frequence_jours": 15}},
        "reglages": {"avec_reglages.dossier": "/Volumes/Depot"},
        "parametres": {"assistant_actif": False},
        "dossiers": {"depot": ""},
        "objectifs": {},
    }


@pytest.mark.parametrize(
    ("saisie", "motif"),
    [
        ({"comptes": {"BNP:courant:****9999": {}}}, "compte inconnu"),
        ({"comptes": {COURANT: {"titulaire": "../hors"}}}, "titulaire invalide"),
        ({"comptes": {COURANT: {"principal": "absent"}}}, "connecteur inconnu"),
        ({"comptes": {COURANT: {"principal": "bnp_csv", "secours": "bnp_csv"}}}, "doit différer"),
        ({"comptes": {COURANT: {"frequence_jours": 0}}}, "fréquence"),
        ({"comptes": {COURANT: {"frequence_jours": True}}}, "fréquence"),
        ({"reglages": {"avec_reglages.cle": "secret"}}, "coffre"),
        ({"reglages": {"inconnu.x": "1"}}, "réglage inconnu"),
        ({"parametres": {"assistant_actif": "oui"}}, "vrai ou faux"),
        ({"parametres": {"autre": True}}, "paramètre inconnu"),
        ({"comptes": []}, "objet attendu"),
    ],
)
def test_une_saisie_hors_format_est_refusee_sans_rien_ecrire(tmp_path, saisie, motif):
    with pytest.raises(ConfigurationInvalide, match=motif):
        _ecrire(tmp_path, saisie)
    assert not (tmp_path / "configuration.json").exists()


def test_le_titulaire_saisi_remplace_celui_du_dossier_dans_les_chiffres(donnees):
    _ecrire(donnees, {"comptes": {COURANT: {"titulaire": "Bruno"}, ASSURANCE_VIE: {"titulaire": "Bruno"}}})
    resultat = charger(donnees)
    courant = next(c for c in resultat.comptes if c.type_compte == "courant")
    assurance_vie = next(r for r in resultat.releves if r.releve.type_contrat == "assurance_vie")
    assert (courant.titulaire, assurance_vie.titulaire) == ("Bruno", "Bruno")


def test_l_onglet_propose_le_dernier_connecteur_et_la_frequence_du_type_par_defaut(donnees):
    etat = etat_configuration(donnees)
    courant = next(c for c in etat["comptes"] if c["cle"] == COURANT)
    assert (courant["principal"], courant["secours"], courant["frequence_jours"]) == ("bnp_csv", "", 30)
    assert courant["connecteurs_possibles"] == ["bnp_csv"]
    assert courant["derniere_donnee"] and len(etat["comptes"]) == 6
    assert [c["nom"] for c in etat["connecteurs"]] == ["bnp_csv", "cardif_pdf", "suravenir_pdf"]


def test_un_reglage_secret_n_est_jamais_renvoye(donnees, monkeypatch):
    monkeypatch.setattr(vues_configuration, "lister_connecteurs", lambda: CONNECTEURS)
    (donnees / "configuration.json").write_text(json.dumps({"reglages": {"avec_reglages.cle": "ne-pas-montrer"}}))
    fiche = next(c for c in etat_configuration(donnees)["connecteurs"] if c["nom"] == "avec_reglages")
    assert "ne-pas-montrer" not in json.dumps(fiche)
    assert [r["renseigne"] for r in fiche["reglages"]] == [False, True]


def test_enregistrer_depuis_l_onglet_rend_l_etat_a_jour(donnees):
    etat = enregistrer_configuration(donnees, {"comptes": {COURANT: {"frequence_jours": 7}}})
    assert next(c for c in etat["comptes"] if c["cle"] == COURANT)["frequence_jours"] == 7


@pytest.fixture
def serveur(donnees):
    instance = creer_serveur(donnees, port=0)
    threading.Thread(target=instance.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{instance.server_port}"
    instance.shutdown()
    instance.server_close()


def _requete(url: str, donnees: dict | None = None) -> tuple[int, dict]:
    corps = None if donnees is None else json.dumps(donnees).encode()
    requete = urllib.request.Request(url, data=corps, headers={"X-Metabank": "1"})
    try:
        with urllib.request.urlopen(requete, timeout=5) as reponse:
            return reponse.status, json.loads(reponse.read())
    except urllib.error.HTTPError as erreur:
        return erreur.code, json.loads(erreur.read())


def test_le_serveur_sert_et_enregistre_la_configuration(serveur):
    statut, etat = _requete(serveur + "/api/configuration")
    assert statut == 200 and len(etat["comptes"]) == 6
    statut, etat = _requete(serveur + "/api/configuration", {"comptes": {COURANT: {"titulaire": "Bruno"}}})
    assert statut == 200
    assert next(c for c in etat["comptes"] if c["cle"] == COURANT)["titulaire_saisi"] == "Bruno"
    assert _requete(serveur + "/api/configuration", {"comptes": {"inconnu": {}}})[0] == 400


def test_l_assistant_desactive_ne_part_pas_vers_claude(serveur):
    _requete(serveur + "/api/configuration", {"parametres": {"assistant_actif": False}})
    assert _requete(serveur + "/api/etat")[1]["assistant_disponible"] is False
    statut, reponse = _requete(serveur + "/api/assistant", {"question": "Combien ?"})
    assert statut == 503 and "désactivé" in reponse["erreur"]
