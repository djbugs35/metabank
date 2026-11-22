from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from metabank.bilan import faire_bilans
from metabank.releves import ReleveRange, lire_releve
from metabank.releves.modele import Frais, Mouvements, Releve

EXEMPLES = Path(__file__).parent / "exemples"


def _av_2025() -> Releve:
    return lire_releve((EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8"))


def _annee(annee: int, valeur: str, verse: str, precedente: str | None) -> Releve:
    return Releve(
        assureur="Test",
        produit="Contrat",
        numero="000 111",
        type_contrat="assurance_vie",
        date_arrete=date(annee, 12, 31),
        valeur=Decimal(valeur),
        supports=(),
        valeur_precedente=Decimal(precedente) if precedente else None,
        mouvements=Mouvements(versements_nets=Decimal(verse)),
        frais=Frais(total=Decimal(100)),
    )


def test_annee_gain_rendement_et_frais_sur_encours():
    """Valeurs de l'exemple calculées à la main (MODELE § 1)."""
    annee = faire_bilans([ReleveRange("A", _av_2025())])[0].annees[0]
    assert annee.gain == Decimal("1100.00")
    assert round(annee.rendement, 6) == Decimal("0.062857")
    assert round(annee.rendement_avant_frais, 6) == Decimal("0.080857")
    assert round(annee.frais_sur_encours, 5) == Decimal("0.01745")


def test_premiere_annee_sans_rendement_car_date_d_ouverture_inconnue():
    bilan = faire_bilans([ReleveRange("A", _annee(2023, "10500", "10000", None))])[0]
    assert bilan.annees[0].gain == Decimal(500)
    assert bilan.annees[0].rendement is None


def test_cumul_depuis_l_origine_sur_plusieurs_annees():
    releves = [
        ReleveRange("A", _annee(2023, "10500", "10000", None)),
        ReleveRange("A", _annee(2024, "16000", "5000", "10500")),
    ]
    bilan = faire_bilans(releves)[0]
    assert bilan.apports_cumules == Decimal(15000)
    assert bilan.gain_cumule == Decimal(1000)
    assert bilan.frais_cumules == Decimal(200)
    assert bilan.anomalies == ()


def test_valeur_de_debut_incoherente_avec_l_annee_precedente_signalee():
    releves = [
        ReleveRange("A", _annee(2023, "10500", "10000", None)),
        ReleveRange("A", _annee(2024, "16000", "5000", "10400")),
    ]
    assert any("≠ valeur de fin" in a for a in faire_bilans(releves)[0].anomalies)


def test_annee_manquante_signalee():
    releves = [
        ReleveRange("A", _annee(2023, "10500", "10000", None)),
        ReleveRange("A", _annee(2025, "16000", "5000", "10500")),
    ]
    assert any("2024 absent" in a for a in faire_bilans(releves)[0].anomalies)


def test_contrats_separes_par_titulaire_et_numero():
    autre = replace(_annee(2023, "1000", "1000", None), numero="999")
    releves = [ReleveRange("A", _annee(2023, "10500", "10000", None)), ReleveRange("B", autre)]
    assert [(b.titulaire, b.numero) for b in faire_bilans(releves)] == [("A", "000 111"), ("B", "999")]


def test_situation_seule_cumul_donne_par_l_assureur():
    situation = lire_releve((EXEMPLES / "cardif_situation.txt").read_text(encoding="utf-8"), "", "perp")
    bilan = faire_bilans([ReleveRange("B", situation)])[0]
    assert bilan.annees == ()
    assert bilan.gain_cumule == Decimal("2300.00")
    assert bilan.frais_cumules is None
