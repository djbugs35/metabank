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


def test_situation_datee_entre_dans_la_rentabilite_annualisee():
    """PERP sans relevé annuel : 10 000 € versés à l'ouverture, 12 100 € deux ans plus tard : 10 % par an."""
    from pathlib import Path  # noqa: PLC0415

    from metabank.releves import lire_releve  # noqa: PLC0415

    texte = (Path(__file__).parent / "exemples" / "cardif_situation.txt").read_text(encoding="utf-8")
    texte = texte.replace("18 000,00", "10 000,00").replace("20 300,00", "12 100,00")
    releves = [ReleveRange("B", lire_releve(texte, "", "perp"))]
    s = synthetiser("B", faire_bilans(releves, {"12345678": date(2024, 11, 18)}), [])
    assert round(s.rendement_annualise, 2) == Decimal("0.10")
    assert s.situations_dans_rendement


def test_gros_versements_rendement_approximatif_avec_fourchette():
    """Cas réel (PER 2024) : 6 000 € au départ, 34 000 € versés, 1 900 € gagnés : 4,75 % à 31,7 % selon les dates."""
    releves = [_annee(2024, "41900", "34000", "6000", "A")]
    annee = synthetiser("A", faire_bilans(releves), []).annees[0]
    assert annee.approximatif
    assert annee.rendement_min == Decimal("0.0475")
    assert round(annee.rendement_max, 3) == Decimal("0.317")


def test_petits_versements_rendement_sans_fourchette():
    releves = [_annee(2024, "10600", "1000", "10000", "A")]
    assert not synthetiser("A", faire_bilans(releves), []).annees[0].approximatif


def test_la_progression_donne_valeur_variation_verse_et_gagne_cumules_fin_d_annee():
    """A ouvre en 2023 (10 000 versés, vaut 10 250), verse 2 000 en 2024 et vaut 11 900 : perte de 350 en 2024."""
    releves = [_annee(2023, "10250", "10000", None, "A"), _annee(2024, "11900", "2000", "10250", "A")]
    [fin_2023, fin_2024] = synthetiser("Foyer", faire_bilans(releves), []).progression
    assert (fin_2023.valeur, fin_2023.variation, fin_2023.verse_cumule, fin_2023.gain_cumule) == (
        Decimal(10250), Decimal(10250), Decimal(10000), Decimal(250),
    )  # fmt: skip
    assert (fin_2024.variation, fin_2024.verse_net_annee, fin_2024.gain_annee) == (Decimal(1650), Decimal(2000),
                                                                                  Decimal(-350))  # fmt: skip
    assert (fin_2024.verse_cumule, fin_2024.gain_cumule) == (Decimal(12000), Decimal(-100))


def test_un_contrat_anterieur_a_ses_releves_part_de_sa_valeur_de_debut():
    releves = [_annee(2024, "10500", "0", "10000", "A"), _annee(2024, "5100", "0", "5000", "B")]
    [fin_2024] = synthetiser("Foyer", faire_bilans(releves), []).progression
    assert (fin_2024.valeur, fin_2024.verse_cumule, fin_2024.gain_cumule) == (Decimal(15600), Decimal(15000),
                                                                             Decimal(600))  # fmt: skip


def test_un_contrat_sans_chiffres_une_annee_garde_sa_derniere_valeur_dans_la_progression():
    """B n'a pas encore de relevé 2025 : il reste dans la barre 2025 avec sa valeur de fin 2024, sans variation."""
    releves = [_annee(2024, "10500", "0", "10000", "A"), _annee(2025, "11000", "0", "10500", "A"),
               _annee(2024, "5100", "0", "5000", "B")]  # fmt: skip
    synthese = synthetiser("Foyer", faire_bilans(releves), [])
    fin_2025 = synthese.progression[-1]
    assert (fin_2025.valeur, fin_2025.variation, fin_2025.gain_cumule) == (Decimal(16100), Decimal(500), Decimal(1100))


def test_le_gain_de_chaque_annee_se_lit_contrat_par_contrat():
    releves = [_annee(2024, "10500", "0", "10000", "A"), _annee(2024, "4900", "0", "5000", "B")]
    synthese = synthetiser("Foyer", faire_bilans(releves), [])
    assert sorted(c.gains[2024] for c in synthese.contrats) == [Decimal(-100), Decimal(500)]
    assert sum(c.gains[2024] for c in synthese.contrats) == synthese.annees[0].gain
