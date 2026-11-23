"""Situation de contrat Suravenir (MODELE § 2.3) : lecture, contrôles, place dans le bilan, frais des fonds gardés."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from metabank.allocation import positions
from metabank.bilan import faire_bilans
from metabank.connecteurs.registre import lister_connecteurs, reconnaitre
from metabank.releves import ReleveRange, lire_releve
from metabank.releves.frais_supports import FraisSupport
from metabank.releves.suravenir_situation import est_situation_suravenir, lire_situation_suravenir
from metabank.releves.texte import ErreurLecture
from tests.conftest import ENTETE_PDF, EXEMPLES

SITUATION = (EXEMPLES / "suravenir_situation.txt").read_text(encoding="utf-8") + "\nVIE PLUS - Filière de SURAVENIR\n"


def test_la_situation_donne_date_numero_fonds_et_cumuls():
    r = lire_situation_suravenir(SITUATION, "s.pdf")
    assert (r.assureur, r.produit, r.numero, r.date_arrete) == (
        "Suravenir",
        "Patrimoine Vie Plus",
        "U2 123456789",
        date(2026, 11, 18),
    )
    assert (r.valeur, r.versements_bruts_depuis_origine, r.rachats_depuis_origine) == (
        Decimal(21000),
        Decimal(20000),
        Decimal(0),
    )
    assert [s.isin for s in r.supports] == ["FR0000000001", "LU0000000002", "FR00000000H3"]
    assert r.supports[0].parts == Decimal(10) and r.supports[0].valeur_part == Decimal(1000)
    assert not r.est_annuel and r.type_contrat == "assurance_vie" and r.anomalies == ()


def test_un_gain_qui_ne_recoupe_pas_la_performance_annoncee_est_signale():
    r = lire_situation_suravenir(SITUATION.replace("1 000,00 €\n", "900,00 €\n", 1), "s.pdf")
    assert any("performance annoncée" in a for a in r.anomalies)


def test_une_situation_sans_fonds_est_refusee():
    with pytest.raises(ErreurLecture, match="aucun fonds"):
        lire_situation_suravenir(SITUATION.split("Supports financiers")[0] + "Supports financiers\n", "s.pdf")


@pytest.mark.usefixtures("pdf_simules")
def test_situation_et_releve_annuel_sont_reconnus_par_des_connecteurs_differents():
    connecteurs = lister_connecteurs()
    assert est_situation_suravenir(SITUATION) and lire_releve(SITUATION).date_arrete == date(2026, 11, 18)
    assert reconnaitre(connecteurs, "s.pdf", ENTETE_PDF + SITUATION.encode()).etablissement == "Suravenir"
    annuel = (EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8")
    assert not est_situation_suravenir(annuel)


def test_une_situation_apres_les_releves_annuels_donne_la_valeur_et_le_gain_du_jour():
    annuel = lire_releve((EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8"), "", "assurance_vie")
    situation = replace(lire_situation_suravenir(SITUATION, "s.pdf"), numero=annuel.numero)
    [bilan] = faire_bilans([ReleveRange("Alice", annuel), ReleveRange("Alice", situation)])
    assert (bilan.valeur, bilan.date_valeur) == (Decimal(21000), date(2026, 11, 18))
    assert bilan.apports_cumules == Decimal(20000) and bilan.gain_cumule == Decimal(1000)
    assert [a.annee for a in bilan.annees] == [2025, 2026]


def test_les_frais_des_fonds_viennent_du_dernier_releve_qui_les_donne():
    frais = FraisSupport(
        "FR0000000001", *(Decimal(1),) * 2, Decimal("0.5"), Decimal(5), Decimal("1.5"), *(Decimal(0),) * 3
    )
    annuel = replace(
        lire_situation_suravenir(SITUATION, "a.pdf"), date_arrete=date(2025, 12, 31), frais_supports=(frais,)
    )
    situation = lire_situation_suravenir(SITUATION, "s.pdf")
    [p, *_] = positions([ReleveRange("Alice", annuel), ReleveRange("Alice", situation)], {})
    assert p.frais_totaux == Decimal("1.5")


def test_l_annee_en_cours_prend_versements_et_frais_dans_l_historique_des_operations():
    annuel = lire_releve((EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8"), "", "assurance_vie")
    situation = replace(lire_situation_suravenir(SITUATION, "s.pdf"), numero=annuel.numero)
    assert (situation.versements_annee_en_cours, situation.frais_annee_en_cours) == (Decimal(1000), Decimal(100))
    [bilan] = faire_bilans([ReleveRange("Alice", annuel), ReleveRange("Alice", situation)])
    en_cours = bilan.annees[-1]
    # Le versement de septembre 2025 et l'arbitrage de 2026 ne comptent pas comme versés en 2026.
    assert (en_cours.annee, en_cours.en_cours_au, en_cours.apports, en_cours.frais) == (
        2026, date(2026, 11, 18), Decimal(1000), Decimal(100),
    )  # fmt: skip
    assert en_cours.gain == Decimal(21000) - annuel.valeur - Decimal(1000)
    assert en_cours.rendement == en_cours.gain / (annuel.valeur + Decimal(500))


def test_sans_historique_des_operations_pas_d_annee_en_cours():
    sans_historique = "\n".join(l for l in SITUATION.splitlines() if not l.strip()[:2].isdigit() or "/" not in l[:40])
    annuel = lire_releve((EXEMPLES / "suravenir_av_2025.txt").read_text(encoding="utf-8"), "", "assurance_vie")
    situation = replace(lire_situation_suravenir(sans_historique, "s.pdf"), numero=annuel.numero)
    assert situation.versements_annee_en_cours is None
    [bilan] = faire_bilans([ReleveRange("Alice", annuel), ReleveRange("Alice", situation)])
    assert [a.annee for a in bilan.annees] == [2025]
