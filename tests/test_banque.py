from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from metabank.banque import fusionner, lire_comptes
from metabank.banque.analyse import TAUX_LIVRET_A, analyser
from metabank.banque.bnp import ExportIllisible, decoder, lire_export_bnp
from metabank.banque.categories import DEPENSE, INTERNE, REVENU, classer
from metabank.web.assistant import contexte
from metabank.web.banque_vues import etat_banque
from metabank.web.depot import deposer_releve

EXEMPLES = Path(__file__).parent / "exemples"


def _export(nom: str = "bnp_courant.csv"):
    return lire_export_bnp(decoder((EXEMPLES / nom).read_bytes()), nom)


def _compte(nom: str = "bnp_courant.csv", type_compte: str = "courant"):
    return fusionner("Alice", "BNP", type_compte, [_export(nom)])


def test_export_bnp_lu_avec_solde_date_et_operations_dans_l_ordre():
    export = _export()
    assert export.numero_masque == "****1234"
    assert export.date_solde == date(2026, 3, 31)
    assert export.solde == Decimal("10000.00")
    assert len(export.operations) == 22
    assert export.operations[0].jour <= export.operations[-1].jour
    assert export.operations[0].montant == Decimal("3000.00")


def test_operation_sans_type_lue_quand_meme():
    """Le remboursement par carte n'a ni type ni sous-type : c'est une vraie ligne, pas une erreur."""
    rembourse = [o for o in _export().operations if o.montant == Decimal("50.00")]
    assert rembourse[0].type_banque == ""


def test_fichier_d_un_autre_format_refuse():
    with pytest.raises(ExportIllisible, match="en-tête"):
        lire_export_bnp("Date;Libellé;Montant\n01/01/2026;X;1,00\n", "autre.csv")


def test_deux_exports_qui_se_chevauchent_ne_doublent_pas_les_operations():
    complet = _export()
    ancien = complet.__class__(complet.nom, complet.numero_masque, date(2026, 1, 31), Decimal("7066.00"),
                               tuple(o for o in complet.operations if o.jour <= date(2026, 1, 31)), "ancien.csv")  # fmt: skip
    compte = fusionner("Alice", "BNP", "courant", [ancien, complet])
    assert len(compte.operations) == len(complet.operations)
    assert compte.solde == Decimal("10000.00")
    assert compte.anomalies == ()


def test_solde_d_un_ancien_export_incoherent_signale():
    complet = _export()
    faux = complet.__class__(complet.nom, complet.numero_masque, date(2026, 1, 31), Decimal("1.00"), (), "faux.csv")
    assert "faux.csv" in fusionner("Alice", "BNP", "courant", [faux, complet]).anomalies[0]


def test_salaire_reconnu_par_sa_regularite_et_virements_internes_a_part():
    classees = {c.operation.libelle[:40]: c for c in classer(_compte().operations, [])}
    salaire = next(c for l, c in classees.items() if "SOCIETE EXEMPLE" in l)
    assert (salaire.categorie, salaire.nature) == ("Salaires et revenus réguliers", REVENU)
    assert next(c for l, c in classees.items() if "CPTE A CPTE" in l).nature == INTERNE
    assert next(c for l, c in classees.items() if "CARREFOUR" in l).categorie == "Alimentation"


def test_regle_personnelle_passe_avant_les_regles_du_code():
    classees = classer(_compte().operations, [("CARREFOUR", "Courses du week-end")])
    carrefour = next(c for c in classees if "CARREFOUR" in c.operation.libelle)
    assert (carrefour.categorie, carrefour.nature) == ("Courses du week-end", DEPENSE)


def test_achat_rembourse_diminue_la_depense_au_lieu_d_etre_un_revenu():
    analyse = analyser(_compte(), [])
    categories = dict(analyse.depenses_par_categorie)
    assert categories["Achats en ligne"] == Decimal("30.00")
    assert analyse.revenus == Decimal("12000.00")


def test_budget_du_compte_courant():
    analyse = analyser(_compte(), [])
    assert analyse.depenses == Decimal("902.00")
    assert analyse.epargne == Decimal("1200.00")
    assert analyse.interne == Decimal("4000.00")
    assert analyse.frais_bancaires == Decimal("72.00")
    assert analyse.taux_epargne == (Decimal(12000) - Decimal(902)) / Decimal(12000)


def test_solde_de_fin_de_mois_recalcule_depuis_le_solde_de_l_export():
    mois = {m.mois: m for m in analyser(_compte(), []).mois}
    assert mois["2026-03"].solde_fin == Decimal("10000.00")
    assert mois["2025-12"].solde_fin == Decimal("5584.00")
    assert mois["2025-12"].complet is True


def test_argent_qui_dort_au_dela_de_deux_mois_de_depenses():
    analyse = analyser(_compte(), [])
    assert analyse.coussin == analyse.depenses / analyse.nombre_mois * 2
    assert analyse.argent_qui_dort == analyse.solde_moyen - analyse.coussin
    assert analyse.manque_a_gagner == analyse.argent_qui_dort * TAUX_LIVRET_A


def test_interets_du_livret_et_taux_obtenu():
    analyse = analyser(_compte("bnp_livret.csv", "livret_a"), [])
    annee, interets, moyenne = analyse.interets_par_an[0]
    assert (annee, interets) == (2025, Decimal("150.00"))
    assert moyenne == pytest.approx(Decimal("10000.41"), abs=Decimal("0.01"))
    assert analyse.argent_qui_dort == 0


def test_comptes_lus_depuis_les_dossiers_cc_la_ldd(tmp_path):
    dossier = tmp_path / "Alice" / "CC - BNP - 1234 "
    dossier.mkdir(parents=True)
    (dossier / "export.csv").write_bytes((EXEMPLES / "bnp_courant.csv").read_bytes())
    (tmp_path / "Alice" / "AV - Suravenir - X 1").mkdir()
    comptes, erreurs = lire_comptes(tmp_path)
    assert erreurs == []
    assert [(c.type_compte, c.banque, c.libelle) for c in comptes] == [
        ("courant", "BNP", "Alice · Compte courant BNP ****1234")
    ]


def test_export_depose_dans_la_page_range_dans_le_dossier_du_compte(tmp_path):
    existant = tmp_path / "Alice" / "CC - BNP - 0001234"
    existant.mkdir(parents=True)
    resultat = deposer_releve(tmp_path, "Alice", "export.csv", (EXEMPLES / "bnp_courant.csv").read_bytes())
    assert resultat["chemin"] == "Alice/CC - BNP - 0001234/export.csv"
    livret = deposer_releve(tmp_path, "Alice", "livret.csv", (EXEMPLES / "bnp_livret.csv").read_bytes())
    assert livret["chemin"] == "Alice/LA - BNP - 5678/livret.csv"


def test_contexte_de_l_assistant_sans_numero_de_compte(tmp_path):
    dossier = tmp_path / "Alice" / "CC - BNP - 1234"
    dossier.mkdir(parents=True)
    (dossier / "export.csv").write_bytes((EXEMPLES / "bnp_courant.csv").read_bytes())
    vues, _ = etat_banque(tmp_path)
    texte = contexte({"vues": [], "fonds": [], "points": [], "banque": vues})
    assert "Alice · Compte courant BNP" in texte
    assert "1234" not in texte
