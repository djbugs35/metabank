from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from metabank.releves import lire_releve
from metabank.releves.texte import ErreurLecture, en_decimal

EXEMPLES = Path(__file__).parent / "exemples"


def _lire(nom: str, type_indique: str | None = None):
    return lire_releve((EXEMPLES / nom).read_text(encoding="utf-8"), nom, type_indique)


def test_montant_francais_avec_milliers_et_virgule():
    assert en_decimal("57 994,02") == Decimal("57994.02")
    assert en_decimal("1\u202f418,01") == Decimal("1418.01")
    assert en_decimal("50") == Decimal(50)


def test_assurance_vie_valeur_date_et_valeur_precedente():
    releve = _lire("suravenir_av_2025.txt")
    assert releve.type_contrat == "assurance_vie"
    assert releve.date_arrete == date(2025, 12, 31)
    assert releve.valeur == Decimal("21100.00")
    assert releve.valeur_precedente == Decimal("15000.00")


def test_supports_avec_isin_et_fonds_euros_sans_isin():
    supports = _lire("suravenir_av_2025.txt").supports
    assert [s.isin for s in supports] == [None, "FR0000000001", "LU0000000002"]
    assert supports[0].libelle == "FONDS EUROS COMPARTIMENT LIBRE"
    assert supports[1].parts == Decimal("50.0000")


def test_ligne_de_pied_de_page_au_milieu_du_tableau_ignoree():
    """« Émis le … » tombe entre deux supports au saut de page : ce n'est pas un support."""
    releve = _lire("suravenir_av_2025.txt")
    assert len(releve.supports) == 3
    assert releve.anomalies == ()


def test_mouvements_par_libelle_y_compris_montant_sur_ligne_suivante():
    mouvements = _lire("suravenir_av_2025.txt").mouvements
    assert mouvements.versements_bruts == Decimal("5000.00")
    assert mouvements.frais_arbitrages == Decimal("10.00")
    assert mouvements.distributions == Decimal("100.00")
    assert mouvements.prelevements_sociaux == Decimal("3.44")


def test_frais_annuels_meme_si_la_phrase_est_coupee():
    frais = _lire("suravenir_av_2025.txt").frais
    assert frais.total == Decimal("315.00")
    assert frais.gestion_fonds_euros == Decimal("5.00")


def test_per_ecart_entre_synthese_et_versements_volontaires_signale():
    """Cas réel : le tableau « évolution du plan » compte plus de versements que la synthèse des mouvements."""
    releve = _lire("suravenir_per_2024.txt")
    assert releve.type_contrat == "per"
    assert releve.versements_volontaires_annee == Decimal("7060.00")
    assert releve.versements_bruts_depuis_origine == Decimal("11060.00")
    assert any("écart 1000.00" in anomalie for anomalie in releve.anomalies)


def test_type_indique_par_le_dossier_prioritaire():
    assert _lire("suravenir_per_2024.txt", "perp").type_contrat == "perp"


def test_situation_cardif_libelle_sur_deux_lignes_recolle():
    releve = _lire("cardif_situation.txt", "perp")
    assert releve.assureur == "Cardif"
    assert releve.numero == "12345678"
    assert releve.date_arrete == date(2026, 11, 18)
    assert releve.versements_bruts_depuis_origine == Decimal("18000.00")
    assert [s.libelle for s in releve.supports] == ["Produit Structuré Exemple Avril 2026", "Fonds Obligataire C"]
    assert not releve.est_annuel
    assert releve.anomalies == ()


def test_forme_inconnue_refusee():
    with pytest.raises(ErreurLecture):
        lire_releve("un texte quelconque", "x.pdf")


def test_titre_avec_apostrophe_typographique_reconnu():
    """Les relevés 2023 et 2024 ont une apostrophe typographique dans le titre : ils étaient refusés."""
    texte = (
        (EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8").replace("D'INFORMATION", "D\u2019INFORMATION")
    )
    assert lire_releve(texte).produit == "Patrimoine Vie Plus"
