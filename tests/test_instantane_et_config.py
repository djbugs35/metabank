import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from metabank.config import lire_config
from metabank.instantane import ecrire_instantane
from metabank.modele import Compte, Ligne

MOMENT = datetime(2026, 11, 11, 15, 30, tzinfo=timezone(timedelta(hours=1)))


def _compte() -> Compte:
    ligne = Ligne(libelle="ETF Monde", valorisation=Decimal("1000.01"), isin="FR0011869353")
    return Compte("woob:bnp", "bnp:1", "PEA", "pea", Decimal("1000.01"), "EUR", "…0001", (ligne,))


def test_montants_ecrits_en_texte_sans_perte(tmp_path):
    chemin = ecrire_instantane([_compte()], tmp_path, "woob", MOMENT)
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    assert contenu["comptes"][0]["solde"] == "1000.01"
    assert contenu["comptes"][0]["lignes"][0]["valorisation"] == "1000.01"


def test_instantane_nomme_par_date_sans_temporaire_restant(tmp_path):
    chemin = ecrire_instantane([_compte()], tmp_path, "woob", MOMENT)
    assert chemin.name == "2026-11-11_1530_woob.json"
    assert list(chemin.parent.glob("*.tmp")) == []


def test_config_ignore_aide_et_applique_surcharge_locale(tmp_path):
    (tmp_path / "config").mkdir()
    principal = tmp_path / "config" / "metabank.json"
    local = tmp_path / "config" / "local.json"
    principal.write_text(
        json.dumps({"_aide": {}, "woob_backends": ["bnp"], "dossier_donnees": "data", "dossier_session_woob": "~/s"})
    )
    local.write_text(json.dumps({"woob_backends": ["bnp", "revolut"]}))
    config = lire_config(principal, local)
    assert "_aide" not in config
    assert config["woob_backends"] == ["bnp", "revolut"]
    assert config["dossier_donnees"] == tmp_path / "data"
    assert config["dossier_session_woob"].is_absolute()
