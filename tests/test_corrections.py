import json
from datetime import date
from decimal import Decimal

from metabank.corrections import appliquer_verifications, date_ouverture, lire_ouvertures
from metabank.releves import ReleveRange
from metabank.releves.modele import Releve


def test_ouvertures_lues_et_reconnues_par_la_fin_du_numero(tmp_path):
    (tmp_path / "corrections.json").write_text(json.dumps({"ouvertures": {"270272854": "2023-03-30"}}))
    ouvertures = lire_ouvertures(tmp_path)
    assert date_ouverture("007935 U2 270272854", ouvertures) == date(2023, 3, 30)
    assert date_ouverture("999", ouvertures) is None


def test_sans_fichier_aucune_correction(tmp_path):
    assert lire_ouvertures(tmp_path) == {}


def _releve(annee: int, anomalies: tuple[str, ...]) -> Releve:
    return Releve("Suravenir", "PER", "007935 B7 270549974", "PER", date(annee, 12, 31), Decimal(1), (),
                  anomalies=anomalies)  # fmt: skip


def test_versements_verifies_retirent_l_ecart_de_cette_annee_seulement(tmp_path):
    (tmp_path / "corrections.json").write_text(json.dumps({"versements_verifies": {"270549974": [2024]}}))
    ecart = "versements de l'année : 40 € au tableau, 34 € dans la synthèse"
    releves = [ReleveRange("C", _releve(annee, (ecart, "autre"))) for annee in (2024, 2025)]
    resultat = appliquer_verifications(releves, tmp_path)
    assert resultat[0].releve.anomalies == ("autre",)
    assert resultat[1].releve.anomalies == (ecart, "autre")
