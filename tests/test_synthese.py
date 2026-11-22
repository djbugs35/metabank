from datetime import date
from decimal import Decimal

from metabank.bilan import faire_bilans
from metabank.releves import ReleveRange
from metabank.releves.modele import Frais, Mouvements, Releve
from metabank.synthese import synthetiser, taux_rendement_interne


def test_taux_rendement_interne_un_an_a_10_pour_cent():
    flux = [(date(2024, 1, 1), -1000.0), (date(2025, 1, 1), 1100.0)]
    assert round(taux_rendement_interne(flux), 3) == 0.1


def _annee(annee: int, valeur: str, verse: str, precedente: str | None, titulaire: str) -> ReleveRange:
    releve = Releve(
        assureur="T", produit="Contrat", numero=titulaire, type_contrat="per", date_arrete=date(annee, 12, 31),
        valeur=Decimal(valeur), supports=(), valeur_precedente=Decimal(precedente) if precedente else None,
        mouvements=Mouvements(versements_nets=Decimal(verse)), frais=Frais(total=Decimal(10)),
    )  # fmt: skip
    return ReleveRange(titulaire, releve)


def test_annees_sommees_sur_deux_personnes():
    """2024 : A part de 10 000 et gagne 500 ; B part de 5 000 et gagne 100. Dietz : 600 / 15 000 = 4 %."""
    releves = [_annee(2024, "10500", "0", "10000", "A"), _annee(2024, "5100", "0", "5000", "B")]
    s = synthetiser("Foyer", faire_bilans(releves), [])
    annee = s.annees[0]
    assert annee.gain == Decimal(600)
    assert annee.rendement == Decimal("0.04")
    assert annee.frais_releve == Decimal(20)


def test_annee_d_ouverture_marquee_et_rentabilite_annualisee():
    releves = [_annee(2023, "10250", "10000", None, "A"), _annee(2024, "10660", "0", "10250", "A")]
    s = synthetiser("A", faire_bilans(releves), [])
    assert s.annees[0].ouverture_dans_l_annee
    assert s.rendement_annualise is not None
    assert Decimal("0.03") < s.rendement_annualise < Decimal("0.05")
