import json
from datetime import date

from metabank.corrections import date_ouverture, lire_ouvertures


def test_ouvertures_lues_et_reconnues_par_la_fin_du_numero(tmp_path):
    (tmp_path / "corrections.json").write_text(json.dumps({"ouvertures": {"270272854": "2023-03-30"}}))
    ouvertures = lire_ouvertures(tmp_path)
    assert date_ouverture("007935 U2 270272854", ouvertures) == date(2023, 3, 30)
    assert date_ouverture("999", ouvertures) is None


def test_sans_fichier_aucune_correction(tmp_path):
    assert lire_ouvertures(tmp_path) == {}
