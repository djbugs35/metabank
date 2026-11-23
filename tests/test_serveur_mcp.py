"""Serveur MCP (lecture seule) : protocole JSON-RPC, outils, et aucun numéro de contrat dans les réponses."""

import io
import json
import re

import pytest

from metabank.outils_mcp import OUTILS
from metabank.releves import lire_dossier
from metabank.serveur_mcp import VERSIONS_DU_PROTOCOLE, repondre, servir

pytestmark = pytest.mark.usefixtures("pdf_simules")
ARGUMENTS_MINIMAUX = {
    "simuler_frais": {"valeur": 10000, "rendement_brut": 5, "frais_actuels": 2, "frais_vises": 0.5, "horizon": 10},
    "rembourser_ou_placer": {"credit": "Joint · Crédit rp BNP", "montant": 5000, "rendement": 2},
    "projeter_retraite": {"titulaire": "Bruno", "annee_depart": 2040, "versement": 0, "inflation": 2,
                          "duree_retrait": 20, "rendements": [1, 3, 5]},
}  # fmt: skip


def _appel(donnees, nom: str, arguments: dict) -> dict:
    message = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": nom, "arguments": arguments}}
    return repondre(message, donnees)["result"]


def test_l_initialisation_accepte_la_version_demandee_ou_propose_la_plus_recente(tmp_path):
    for demandee, rendue in (("2025-06-18", "2025-06-18"), ("1999-01-01", VERSIONS_DU_PROTOCOLE[0])):
        r = repondre(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": demandee}}, tmp_path
        )
        assert r["result"]["protocolVersion"] == rendue and "tools" in r["result"]["capabilities"]


def test_une_notification_n_a_pas_de_reponse(tmp_path):
    assert repondre({"jsonrpc": "2.0", "method": "notifications/initialized"}, tmp_path) is None


def test_la_liste_des_outils_donne_nom_description_et_schema(tmp_path):
    outils = repondre({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, tmp_path)["result"]["tools"]
    assert [o["name"] for o in outils] == [o.nom for o in OUTILS]
    assert all(o["description"] and o["inputSchema"]["type"] == "object" for o in outils)


def test_chaque_outil_repond_sans_jamais_livrer_un_numero_de_contrat(donnees):
    # Chaque groupe de plus de 4 chiffres d'un numéro de contrat (« 270549974 ») ne doit apparaître nulle part.
    groupes = {g for r in lire_dossier(donnees)[0] for g in re.findall(r"\d{5,}", r.releve.numero)}
    assert groupes
    for outil in OUTILS:
        resultat = _appel(donnees, outil.nom, ARGUMENTS_MINIMAUX.get(outil.nom, {}))
        texte = resultat["content"][0]["text"]
        assert not resultat["isError"], (outil.nom, texte)
        assert not any(re.search(rf"(?<!\d){g}(?!\d)", texte) for g in groupes), outil.nom
        assert not re.search(r"(\*|…)\d", texte), outil.nom


def test_le_patrimoine_rend_les_chiffres_du_tableau_de_bord(donnees):
    contenu = _appel(donnees, "patrimoine", {"vue": "Foyer"})["structuredContent"]
    assert contenu["actifs"] > 0 and len(contenu["fins_de_mois"]) == 13


def test_une_vue_inconnue_rend_une_erreur_que_claude_peut_corriger(donnees):
    resultat = _appel(donnees, "placements", {"vue": "Zoé"})
    assert resultat["isError"] and "vues possibles" in resultat["content"][0]["text"]


def test_un_outil_ou_une_methode_inconnus_sont_des_erreurs_json_rpc(tmp_path):
    inconnu = repondre({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "virer"}}, tmp_path)
    assert inconnu["error"]["code"] == -32602
    assert repondre({"jsonrpc": "2.0", "id": 4, "method": "resources/list"}, tmp_path)["error"]["code"] == -32601


def test_le_serveur_lit_une_ligne_par_message_et_signale_le_json_illisible(tmp_path):
    entree = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"ping"}\n\nnon json\n')
    sortie = io.StringIO()
    servir(tmp_path, entree, sortie)
    lignes = [json.loads(ligne) for ligne in sortie.getvalue().splitlines()]
    assert lignes[0] == {"jsonrpc": "2.0", "id": 1, "result": {}}
    assert lignes[1]["error"]["code"] == -32700
