from pathlib import Path

import pytest

from metabank.banque import fusionner
from metabank.banque.bnp import decoder, lire_export_bnp
from metabank.bilan import faire_bilans
from metabank.releves import ReleveRange, lire_releve
from metabank.web.epargne import syntheses_epargne
from metabank.web.patrimoine import COURANTS, EPARGNE, PLACEMENTS, patrimoines

EXEMPLES = Path(__file__).parent / "exemples"


def _patrimoines():
    releves = [ReleveRange("Alice", lire_releve((EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8")))]
    comptes = [
        fusionner("Alice", "BNP", type_, [lire_export_bnp(decoder((EXEMPLES / nom).read_bytes()), nom)])
        for nom, type_ in [("bnp_courant.csv", "courant"), ("bnp_livret.csv", "livret_a")]
    ]
    comptes.append(
        fusionner(
            "Bruno", "BNP", "courant", [lire_export_bnp(decoder((EXEMPLES / "bnp_courant.csv").read_bytes()), "b")]
        )
    )
    return patrimoines(faire_bilans(releves), comptes)


def test_patrimoine_du_foyer_somme_placements_livrets_et_comptes_courants():
    foyer = _patrimoines()["foyer"]
    familles = {f["famille"]: f["montant"] for f in foyer["familles"]}
    assert familles == {PLACEMENTS: 21100.0, EPARGNE: 10150.0, COURANTS: 20000.0}
    assert foyer["total"] == 51250.0
    assert sum(f["part"] for f in foyer["familles"]) == pytest.approx(1)
    assert len(foyer["lignes"]) == 4


def test_patrimoine_par_personne_avec_ses_seuls_comptes():
    tous = _patrimoines()
    assert tous["p:Bruno"]["total"] == 10000.0
    assert [f["famille"] for f in tous["p:Bruno"]["familles"]] == [COURANTS]
    assert tous["p:Alice"]["total"] == 41250.0


def test_synthese_de_l_epargne_interets_taux_et_plafond():
    livret = fusionner(
        "Alice", "BNP", "livret_a", [lire_export_bnp(decoder((EXEMPLES / "bnp_livret.csv").read_bytes()), "l")]
    )
    epargne = syntheses_epargne([livret], {"foyer": 20300.0, "p:Alice": 20300.0})
    foyer = epargne["foyer"]
    assert (foyer["solde"], foyer["annee_interets"], foyer["interets"]) == (10150.0, 2025, 150.0)
    assert foyer["taux_obtenu"] == pytest.approx(150 / 10000.41, abs=1e-6)
    assert foyer["part_patrimoine"] == pytest.approx(0.5)
    assert foyer["versements_possibles"] == 22950 - 10150
    assert set(epargne) == {"foyer", "p:Alice"}
