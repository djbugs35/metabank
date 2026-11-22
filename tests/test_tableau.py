from dataclasses import replace
from datetime import date
from pathlib import Path

from metabank.bilan import faire_bilans
from metabank.frais import analyser_frais
from metabank.releves import ReleveRange, lire_releve
from metabank.releves.frais_supports import lire_frais_supports
from metabank.tableau import Tableau, generer_html

EXEMPLES = Path(__file__).parent / "exemples"


def _page() -> str:
    releves = [
        ReleveRange("A", lire_releve((EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8"))),
        ReleveRange("B", lire_releve((EXEMPLES / "cardif_situation.txt").read_text(encoding="utf-8"), "", "perp")),
    ]
    return generer_html(Tableau(faire_bilans(releves), analyser_frais(releves), date(2026, 11, 22)))


def test_page_autonome_sans_ressource_en_ligne():
    """Les montants ne doivent fuiter vers personne : ni script, ni police, ni image chargés depuis Internet."""
    page = _page()
    assert "http://" not in page
    assert "https://" not in page
    assert "<script" not in page


def test_page_contient_les_contrats_et_le_total():
    page = _page()
    assert "Patrimoine du foyer" in page
    assert "B · PERP Cardif Essentiel Retraite (Cardif)" in page
    assert "41\u202f400 €" in page  # 21 100 + 20 300
    assert "gagné et payé en frais" in page


def test_situation_seule_signalee_dans_les_points_d_attention():
    assert "relevé de situation seul" in _page()


def test_un_bloc_par_personne():
    page = _page()
    assert "<h2>A</h2>" in page
    assert "<h2>B</h2>" in page


def test_texte_des_releves_echappe():
    """Un libellé de relevé contenant « < » ne doit pas casser la page."""
    texte = (EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8").replace("FONDS ACTIONS", "FONDS <ACTIONS>")
    frais, _ = lire_frais_supports((EXEMPLES / "suravenir_frais_supports.txt").read_text(encoding="utf-8"))
    releves = [ReleveRange("A", replace(lire_releve(texte), frais_supports=tuple(frais)))]
    page = generer_html(Tableau(faire_bilans(releves), analyser_frais(releves), date(2026, 11, 22)))
    assert "&lt;ACTIONS&gt;" in page
    assert "<ACTIONS>" not in page


def test_frais_inconnus_et_non_nuls_pour_un_releve_de_situation():
    """Un PERP sans relevé annuel affichait « 0 € » de frais : faux, ils sont seulement inconnus."""
    assert "inconnus (relevé de situation seul)" in _page()
