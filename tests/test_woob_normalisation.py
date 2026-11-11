from datetime import date
from decimal import Decimal

from woob.capabilities.bank import Account, AccountType
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable

from metabank.connecteurs.woob_normalisation import masquer_numero, traduire_compte, traduire_investissement


def _assurance_vie() -> Account:
    compte = Account("00012345678")
    compte.label = "Multiplacements 2"
    compte.type = AccountType.LIFE_INSURANCE
    compte.balance = Decimal("15234.56")
    compte.currency = "EUR"
    compte.number = "0001 2345 678"
    return compte


def _unite_de_compte() -> Investment:
    support = Investment()
    support.label = "Fonds actions monde"
    support.code = "FR0010315770"
    support.valuation = Decimal("8000.10")
    support.quantity = Decimal("42.5")
    support.unitvalue = Decimal("188.24")
    support.vdate = date(2026, 11, 6)
    return support


def test_assurance_vie_garde_type_solde_et_lignes():
    compte = traduire_compte("bnp", _assurance_vie(), [_unite_de_compte()])
    assert compte.type_compte == "assurance_vie"
    assert compte.solde == Decimal("15234.56")
    assert compte.source == "woob:bnp"
    assert compte.lignes[0].isin == "FR0010315770"
    assert compte.lignes[0].valorisation == Decimal("8000.10")


def test_numero_complet_jamais_repris():
    compte = traduire_compte("bnp", _assurance_vie())
    assert compte.numero_masque == "…5678"
    assert "2345" not in compte.numero_masque


def test_type_woob_inconnu_devient_autre():
    compte = _assurance_vie()
    compte.type = AccountType.REAL_ESTATE
    assert traduire_compte("bnp", compte).type_compte == "autre"


def test_type_per_reconnu():
    compte = _assurance_vie()
    compte.type = AccountType.PER
    assert traduire_compte("bnp", compte).type_compte == "per"


def test_valeur_non_disponible_rendue_inconnue():
    support = _unite_de_compte()
    support.diff = NotAvailable
    assert traduire_investissement(support).plus_value is None


def test_code_qui_n_est_pas_un_isin_ignore():
    """Les fonds en euros portent souvent un code interne à l'assureur, pas un ISIN."""
    support = _unite_de_compte()
    support.code = "FONDSEURO"
    assert traduire_investissement(support).isin is None


def test_numero_absent_rend_none():
    assert masquer_numero(None) is None
