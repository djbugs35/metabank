from datetime import date
from decimal import Decimal

import pytest

from metabank.banque import fusionner, lire_comptes
from metabank.banque.bnp import lire_export_bnp
from metabank.banque.credit import analyser_credit
from metabank.corrections import CorrectionInvalide, ecrire_corrections
from metabank.web.patrimoine import patrimoines


def _export_credit(capital: Decimal = Decimal(100000), taux_mensuel: Decimal = Decimal("0.001")) -> str:
    """Rendre un export de prêt fictif à mensualité constante : la part de capital croît du taux mensuel."""
    lignes, amortissement, jour = [], Decimal("500.00"), 5
    for mois in range(1, 7):
        lignes.append(
            f"{jour:02d}/{mois:02d}/2026;;; AMORTISSEMENT PRET 02701 60001234;{amortissement:.2f}".replace(".", ",")
        )
        amortissement *= 1 + taux_mensuel
    entete = f'"Cr&eacute;dit immobilier";"Cr&amp;eacute;dit immobilier";****1234;20/06/2026;;-{capital:.2f}'.replace(
        ".", ","
    )
    return entete + "\n" + "\n".join(lignes) + "\n"


def _credit():
    return fusionner("Joint", "BNP", "credit", [lire_export_bnp(_export_credit(), "credit.csv")])


def test_export_d_un_credit_lu_malgre_les_entites_html_de_son_nom():
    export = lire_export_bnp(_export_credit(), "credit.csv")
    assert export.nom == "Crédit immobilier"
    assert export.solde == Decimal(-100000)


def test_taux_mensualite_et_fin_deduits_de_la_part_de_capital():
    analyse = analyser_credit(_credit(), [])
    assert analyse.taux_annuel == pytest.approx(Decimal("0.012"), abs=Decimal("0.0001"))
    mensuel = analyse.taux_annuel / 12
    attendue = analyse.amortissement_mensuel * (1 + mensuel) + Decimal(100000) * mensuel
    assert analyse.mensualite == attendue
    assert analyse.interets_restants == pytest.approx(analyse.mensualite * analyse.mois_restants - Decimal(100000))
    assert analyse.fin_estimee > date(2026, 6, 20)


def test_mensualite_prelevee_retrouvee_par_le_numero_du_pret():
    commun = fusionner("Joint", "BNP", "courant", [lire_export_bnp(
        "Compte Commun;Compte Commun;****9999;20/06/2026;;100,00\n"
        "05/06/2026;ECHEANCE PRET;ECHEANCE PRET;ECHEANCE PRET 02701 60001234;-600,50\n", "cc.csv")])  # fmt: skip
    assert analyser_credit(_credit(), [commun]).mensualite_prelevee == Decimal("600.50")


def test_dossier_credits_hors_personne_rattache_au_joint(tmp_path):
    dossier = tmp_path / "credtis" / "locatif - BNP - 1234"
    dossier.mkdir(parents=True)
    (dossier / "pret.csv").write_text(_export_credit(), encoding="utf-8")
    comptes, erreurs = lire_comptes(tmp_path)
    assert erreurs == []
    assert [(c.titulaire, c.type_compte, c.libelle) for c in comptes] == [
        ("Joint", "credit", "Joint · Crédit locatif BNP ****1234")
    ]


def test_patrimoine_net_avec_valeur_du_bien_saisie():
    biens = {"1234": {"nom": "Maison", "valeur": 300000}}
    foyer = patrimoines([], [_credit()], biens)["foyer"]
    assert (foyer["total"], foyer["credits"], foyer["net"]) == (300000.0, 100000.0, 200000.0)
    assert foyer["credits_sans_bien"] is False
    sans = patrimoines([], [_credit()], {})["foyer"]
    assert sans["credits_sans_bien"] is True


def test_valeur_de_bien_invalide_refusee(tmp_path):
    with pytest.raises(CorrectionInvalide, match="valeur du bien"):
        ecrire_corrections(tmp_path, {"biens": {"1234": {"nom": "Maison", "valeur": "beaucoup"}}})
    assert ecrire_corrections(tmp_path, {"biens": {"1234": {"nom": "Maison", "valeur": 300000}}})["biens"] == {
        "1234": {"nom": "Maison", "valeur": 300000}
    }
