import json
import threading
import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from metabank.corrections import (
    CorrectionInvalide,
    date_ouverture,
    ecrire_corrections,
    lire_corrections,
    lire_ouvertures,
)
from metabank.frais import projeter
from metabank.releves import ReleveRange, lire_releve
from metabank.web import assistant, depot, vues
from metabank.web.depot import DepotRefuse, deposer_releve
from metabank.web.serveur import creer_serveur
from metabank.web.simulation import SimulationInvalide, simuler

EXEMPLES = Path(__file__).parent / "exemples"
PDF = b"%PDF-1.4 faux contenu"


def _texte(nom: str) -> str:
    return (EXEMPLES / nom).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def lecture_av(monkeypatch):
    """Le PDF déposé est « lu » comme l'exemple d'assurance vie : pas besoin d'un vrai PDF."""
    monkeypatch.setattr(depot, "extraire_texte", lambda _: _texte("suravenir_av_2025.txt"))


def test_releve_annuel_range_par_titulaire_contrat_et_annee(tmp_path):
    resultat = deposer_releve(tmp_path, "Alice", "releve 2025.pdf", PDF)
    chemin = tmp_path / resultat["chemin"]
    assert chemin.read_bytes() == PDF
    assert chemin.parent.name == "2025"
    assert chemin.parent.parent.name.startswith("AV - ")
    assert chemin.parent.parent.parent.name == "Alice"


def test_meme_releve_depose_deux_fois_n_est_pas_duplique(tmp_path):
    deposer_releve(tmp_path, "Alice", "r.pdf", PDF)
    assert deposer_releve(tmp_path, "Alice", "r.pdf", PDF)["deja_present"] is True
    assert len(list(tmp_path.rglob("*.pdf"))) == 1


def test_releve_va_dans_le_dossier_existant_du_contrat(tmp_path):
    numero = lire_releve(_texte("suravenir_av_2025.txt")).numero.split()[-1]
    existant = tmp_path / "Alice" / f"AV - mon contrat {numero}"
    existant.mkdir(parents=True)
    resultat = deposer_releve(tmp_path, "Alice", "r.pdf", PDF)
    assert resultat["chemin"].startswith(f"Alice/AV - mon contrat {numero}/")


@pytest.mark.parametrize(
    ("titulaire", "contenu", "motif"),
    [("../hors", PDF, "titulaire"), ("Alice", b"pas un pdf", "ni un relevé"), ("Alice", b"", "vide")],
)
def test_depot_refuse_sans_rien_ecrire(tmp_path, titulaire, contenu, motif):
    with pytest.raises(DepotRefuse, match=motif):
        deposer_releve(tmp_path, titulaire, "r.pdf", contenu)
    assert not any(tmp_path.iterdir())


def test_nom_de_fichier_ne_peut_pas_sortir_du_dossier(tmp_path):
    resultat = deposer_releve(tmp_path, "Alice", "../../etc/passwd", PDF)
    assert (tmp_path / resultat["chemin"]).resolve().is_relative_to(tmp_path.resolve())


def test_corrections_enregistrees_puis_relues(tmp_path):
    ecrire_corrections(tmp_path, {"ouvertures": {"12345678": "2023-03-30", "87654321": ""},
                                  "versements_verifies": {"12345678": [2025, 2024, 2024]}})  # fmt: skip
    assert lire_corrections(tmp_path) == {
        "ouvertures": {"12345678": "2023-03-30"},
        "versements_verifies": {"12345678": [2024, 2025]},
        "biens": {},
    }


@pytest.mark.parametrize(
    "corrections",
    [{"ouvertures": {"12345678": "30/03/2023"}}, {"ouvertures": {"../x": "2023-03-30"}},
     {"versements_verifies": {"12345678": ["2024"]}}, {"ouvertures": ["2023-03-30"]}],
)  # fmt: skip
def test_correction_invalide_refusee_et_fichier_intact(tmp_path, corrections):
    (tmp_path / "corrections.json").write_text('{"ouvertures": {"11112222": "2020-01-01"}}')
    with pytest.raises(CorrectionInvalide):
        ecrire_corrections(tmp_path, corrections)
    assert lire_corrections(tmp_path)["ouvertures"] == {"11112222": "2020-01-01"}


def test_simulation_reprend_la_projection_du_modele():
    r = simuler({"valeur": 10000, "rendement_brut": 5, "frais_actuels": 2.5, "frais_vises": 1, "horizon": 10})
    assert r["frais_actuels"][-1] == round(float(projeter(Decimal(10000), Decimal(5), Decimal("2.5"), 10)), 2)
    assert r["ecart"] == pytest.approx(r["frais_vises"][-1] - r["frais_actuels"][-1], abs=0.01)
    assert r["frais_payes_vises"] < r["frais_payes_actuels"]


def test_simulation_hors_bornes_refusee():
    with pytest.raises(SimulationInvalide, match="horizon"):
        simuler({"valeur": 1, "rendement_brut": 5, "frais_actuels": 1, "frais_vises": 1, "horizon": 0})


@pytest.fixture
def etat_exemple(tmp_path, monkeypatch):
    releves = [
        ReleveRange("Alice", lire_releve(_texte("suravenir_av_2025.txt"))),
        ReleveRange("Bruno", lire_releve(_texte("cardif_situation.txt"), "", "perp")),
    ]
    monkeypatch.setattr(vues, "lire_dossier", lambda _: (releves, []))
    return vues.etat(tmp_path), releves


def test_etat_donne_foyer_personnes_et_contrats_en_euros_et_en_taux(etat_exemple):
    etat, _ = etat_exemple
    niveaux = [v["niveau"] for v in etat["vues"]]
    assert niveaux == ["foyer", "personne", "contrat", "personne", "contrat"]
    foyer = etat["vues"][0]
    assert foyer["valeur"] == 41400.0
    assert foyer["part_valeur"] == 1.0
    assert foyer["gain_taux"] == pytest.approx(foyer["gain"] / foyer["verse"], abs=1e-6)


def test_contexte_envoye_a_claude_sans_numero_de_contrat(etat_exemple):
    etat, releves = etat_exemple
    texte = assistant.contexte(etat)
    assert "Alice" in texte
    for range_ in releves:
        assert range_.releve.numero.split()[-1] not in texte


def test_question_passe_par_claude_code_sans_outil_dans_un_dossier_vide(etat_exemple, monkeypatch):
    etat, _ = etat_exemple
    appels = {}

    def faux_run(commande, **options):
        appels.update(commande=commande, **options)
        return type("R", (), {"returncode": 0, "stdout": "Réponse.", "stderr": ""})()

    monkeypatch.setattr(assistant, "trouver_claude", lambda: "/bin/claude")
    monkeypatch.setattr(assistant.subprocess, "run", faux_run)
    assert assistant.demander("Mes frais ?", [], etat) == "Réponse."
    assert "--disallowedTools" in appels["commande"]
    assert "Question : Mes frais ?" in appels["input"]
    assert Path(appels["cwd"]) != Path.cwd()
    assert not Path(appels["cwd"]).exists()  # dossier temporaire, supprimé après la réponse


def test_sans_claude_code_l_assistant_le_dit(etat_exemple, monkeypatch):
    monkeypatch.setattr(assistant, "trouver_claude", lambda: None)
    with pytest.raises(assistant.AssistantIndisponible, match="introuvable"):
        assistant.demander("Mes frais ?", [], etat_exemple[0])


@pytest.fixture
def serveur(tmp_path):
    instance = creer_serveur(tmp_path, port=0)
    threading.Thread(target=instance.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{instance.server_port}"
    instance.shutdown()
    instance.server_close()


def _requete(url: str, donnees: dict | None = None, entetes: dict | None = None) -> tuple[int, bytes]:
    corps = None if donnees is None else json.dumps(donnees).encode()
    requete = urllib.request.Request(url, data=corps, headers=entetes or {})
    try:
        with urllib.request.urlopen(requete, timeout=5) as reponse:
            return reponse.status, reponse.read()
    except urllib.error.HTTPError as erreur:
        return erreur.code, erreur.read()


def test_serveur_local_sert_la_page_et_l_etat(serveur):
    statut, page = _requete(serveur + "/")
    assert statut == 200
    assert b"metabank" in page
    statut, corps = _requete(serveur + "/api/etat")
    assert statut == 200
    assert json.loads(corps)["vues"][0]["nom"] == "Foyer"


def test_rapport_pdf_servi_avec_ses_vues_en_parametre(serveur):
    statut, page = _requete(serveur + "/rapport?vues=foyer,p:Alice&fonds=1")
    assert statut == 200
    assert b"rapport.js" in page
    assert _requete(serveur + "/rendu.js")[0] == 200


def test_serveur_refuse_un_envoi_venu_d_une_autre_page(serveur):
    """Une page web quelconque ouverte dans le navigateur ne doit pas pouvoir écrire dans data/."""
    simulation = {"valeur": 1, "rendement_brut": 5, "frais_actuels": 1, "frais_vises": 1, "horizon": 1}
    assert _requete(serveur + "/api/simulation", simulation)[0] == 403
    entetes = {"X-Metabank": "1", "Origin": "http://exemple.com"}
    assert _requete(serveur + "/api/simulation", simulation, entetes)[0] == 403
    assert _requete(serveur + "/api/simulation", simulation, {"X-Metabank": "1"})[0] == 200


def test_ouverture_lue_avec_le_contrat(tmp_path):
    ecrire_corrections(tmp_path, {"ouvertures": {"12345678": "2023-03-30"}})
    assert date_ouverture("U2 12345678", lire_ouvertures(tmp_path)) == date(2023, 3, 30)
