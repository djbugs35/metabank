from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from metabank.frais import analyser_frais, projeter
from metabank.releves import ReleveRange, lire_releve
from metabank.releves.frais_supports import lire_frais_supports, taux_frais_fonds_euros

EXEMPLES = Path(__file__).parent / "exemples"


def _tableau() -> str:
    return (EXEMPLES / "suravenir_frais_supports.txt").read_text(encoding="utf-8")


def test_frais_lus_sur_trois_lignes_par_support():
    frais, _ = lire_frais_supports(_tableau())
    premier = frais[0]
    assert premier.isin == "FR0000000001"
    assert premier.frais_support == Decimal("1.40")
    assert premier.retrocessions == Decimal("0.70")
    assert premier.frais_contrat == Decimal("1.08")
    assert premier.frais_contrat_euros == Decimal("108.00")
    assert premier.frais_totaux == Decimal("2.48")
    assert premier.performance_finale == Decimal("3.62")


def test_ligne_dont_les_taux_ne_se_recoupent_pas_ecartee():
    """FR0000000009 : brute 3,00 moins support 1,00 ≠ nette 2,50 : on ne devine pas, on signale."""
    frais, anomalies = lire_frais_supports(_tableau())
    assert [f.isin for f in frais] == ["FR0000000001", "LU0000000002", "FR0000000005"]
    assert any("FR0000000009" in a and "incohérents" in a for a in anomalies)


def test_taux_du_fonds_euros():
    assert taux_frais_fonds_euros(_tableau()) == Decimal("0.80")


def _releve_avec_frais():
    releve = lire_releve((EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8"))
    frais, _ = lire_frais_supports(_tableau())
    return replace(releve, frais_supports=tuple(frais), taux_frais_fonds_euros=Decimal("0.80"))


def test_couts_par_support_et_frais_caches():
    """Exemple : 10 000 € à 1,40 + 1,08 %, 10 000 € à 0,20 + 1,08 %, 1 100 € de fonds euros à 0,80 %."""
    analyse = analyser_frais([ReleveRange("A", _releve_avec_frais())])[0]
    assert analyse.cout_total == Decimal(248) + Decimal(128) + Decimal("8.8")
    assert analyse.frais_dans_supports == Decimal(160)
    assert analyse.retrocessions == Decimal(70)


def test_simulation_ne_baisse_que_les_supports_plus_chers_que_la_cible():
    analyse = analyser_frais([ReleveRange("A", _releve_avec_frais())], frais_support_cible=Decimal("0.20"))[0]
    assert analyse.economie_annuelle == Decimal(120)
    assert analyse.ecart_projete > 0


def test_projection_composee():
    assert projeter(Decimal(1000), Decimal(5), Decimal(1), 2) == Decimal("1081.6000")


def test_performance_a_trois_chiffres_remontee_d_une_ligne():
    """Cas réel (fonds or 2025) : « 121,74 » est imprimé au-dessus de la ligne de l'ISIN, son « % » en dessous."""
    frais, _ = lire_frais_supports(_tableau())
    fonds_or = next(f for f in frais if f.isin == "FR0000000005")
    assert fonds_or.performance_brute == Decimal("121.74")
    assert fonds_or.performance_finale == Decimal("118.74")
    assert fonds_or.frais_support == Decimal("2.00")
    assert fonds_or.retrocessions == Decimal("0.93")
