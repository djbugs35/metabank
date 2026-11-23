"""Connecteur Enable Banking : synchronisation (faux serveur), anti-doublon avec le CSV (MODELE § 7.1 bis), archives."""

import json
import subprocess
from datetime import date
from urllib.parse import urlsplit

import pytest

import metabank.connecteurs._enable_banking as enable_banking
from metabank.base.integration import FICHIER_BASE, reconstruire
from metabank.base.schema import ouvrir
from metabank.connecteurs.registre import composer_lecteur, lister_connecteurs
from metabank.synchronisation import synchroniser_tout

pytestmark = pytest.mark.usefixtures("pdf_simules")
AUJOURD_HUI = date(2026, 4, 10)


def _operation(jour: str, montant: str, sens: str, ident: str, statut: str = "BOOK") -> dict:
    return {"transaction_id": ident, "booking_date": jour, "status": statut, "credit_debit_indicator": sens,
            "transaction_amount": {"amount": montant, "currency": "EUR"}, "remittance_information": [f"OP {ident}"],
            "debtor_account": {"iban": "FR7630004000312345678901143"}}  # fmt: skip


OPERATIONS = [
    _operation("2026-03-01", "3000.00", "CRDT", "t1"),  # même jour que le CSV
    _operation("2026-03-07", "200.00", "DBIT", "t2"),  # CSV le 05/03 : deux jours d'écart
    _operation("2026-04-02", "45.50", "DBIT", "t3"),  # après le dernier export CSV : nouvelle
    _operation("2026-04-03", "12.00", "DBIT", "t4", "PDNG"),  # en attente : pas encore importée
]


@pytest.fixture
def relie(donnees, monkeypatch):
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-out", str(enable_banking.CLE)], check=True,
                   capture_output=True)  # fmt: skip
    enable_banking.enregistrer_accord({"application": "app", "session": "s1", "fin": "2026-10-01T00:00:00",
                                       "comptes": [{"uid": "u1", "masque": "****1234", "nom": "Courant", "devise": "EUR"},
                                                   {"uid": "u9", "masque": "****9999", "nom": "Autre", "devise": "EUR"}]})  # fmt: skip

    def banque(_methode, adresse, _entetes, _corps):
        chemin = urlsplit(adresse).path
        if chemin.endswith("/balances"):
            return {"balances": [{"balance_type": "CLBD", "reference_date": "2026-04-09",
                                  "balance_amount": {"amount": "10954.50", "currency": "EUR"}}]}  # fmt: skip
        return {"transactions": OPERATIONS}

    monkeypatch.setattr(enable_banking, "_transport_reseau", banque)
    return donnees


def _compter(dossier, requete: str) -> int:
    connexion = ouvrir(dossier / FICHIER_BASE)
    try:
        return connexion.execute(requete).fetchone()[0]
    finally:
        connexion.close()


def test_seules_les_operations_nouvelles_entrent_et_les_jumelles_du_csv_sont_reconnues(relie):
    messages = synchroniser_tout(relie, AUJOURD_HUI)
    assert any("BNP:courant:****1234 : 2 élément(s)" in m for m in messages)  # t3 et le solde
    assert any("****9999 : pas encore en base" in m for m in messages)
    assert _compter(relie, "SELECT count(*) FROM jumelles") == 2
    assert _compter(relie, "SELECT count(*) FROM operations WHERE identifiant LIKE 'eb:%'") == 1


def test_une_seule_synchronisation_par_jour_sauf_si_on_la_force(relie):
    synchroniser_tout(relie, AUJOURD_HUI)
    assert any("déjà mis à jour aujourd'hui" in m for m in synchroniser_tout(relie, AUJOURD_HUI))
    operations = _compter(relie, "SELECT count(*) FROM operations")
    synchroniser_tout(relie, AUJOURD_HUI, forcer=True)
    assert _compter(relie, "SELECT count(*) FROM operations") == operations


def test_la_reponse_archivee_ne_garde_aucun_iban_complet(relie):
    synchroniser_tout(relie, AUJOURD_HUI)
    [archive] = (relie / "archives").rglob("enable_banking-*.json")
    texte = archive.read_text()
    assert "FR76" not in texte and "****9011" in texte and json.loads(texte)["source"] == "enable_banking"


def test_la_base_reconstruite_garde_les_memes_operations_et_jumelles(relie):
    synchroniser_tout(relie, AUJOURD_HUI)
    avant = (_compter(relie, "SELECT count(*) FROM operations"), _compter(relie, "SELECT count(*) FROM jumelles"))
    reconstruire(relie, composer_lecteur(lister_connecteurs()))
    assert (
        _compter(relie, "SELECT count(*) FROM operations"),
        _compter(relie, "SELECT count(*) FROM jumelles"),
    ) == avant


def test_le_solde_du_jour_vient_de_la_banque(relie):
    synchroniser_tout(relie, AUJOURD_HUI)
    requete = (
        "SELECT max(s.jour) = '2026-04-09' FROM soldes s JOIN comptes c ON c.id = s.compte_id "
        "WHERE c.cle = 'BNP:courant:****1234'"
    )
    assert _compter(relie, requete) == 1


def test_sans_accord_rien_n_est_synchronise(donnees):
    assert synchroniser_tout(donnees, AUJOURD_HUI) == []
