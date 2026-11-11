"""Traduction pure des objets woob (Account, Investment) vers le modèle metabank.

Sans réseau ni état : testée directement avec de vrais objets woob construits à la main.
"""

import re

from woob.capabilities.bank import AccountType
from woob.capabilities.base import empty

from metabank.modele import Compte, Ligne

# Noms de woob.capabilities.bank.AccountType -> type metabank. Un type absent devient « autre ».
TYPES_WOOB = {
    "CHECKING": "courant",
    "CARD": "courant",
    "JOINT": "courant",
    "SAVINGS": "livret",
    "DEPOSIT": "livret",
    "LIVRET_A": "livret",
    "LIVRET_B": "livret",
    "LDDS": "livret",
    "CEL": "livret",
    "PEL": "livret",
    "CSL": "livret",
    "CAT": "livret",
    "LIFE_INSURANCE": "assurance_vie",
    "CAPITALISATION": "capitalisation",
    "PER": "per",
    "PERP": "per",
    "PERCO": "per",
    "MADELIN": "per",
    "ARTICLE_83": "per",
    "PEA": "pea",
    "MARKET": "cto",
    "LOAN": "credit",
    "MORTGAGE": "credit",
    "CONSUMER_CREDIT": "credit",
    "REVOLVING_CREDIT": "credit",
}

NOMS_TYPES_WOOB = {valeur: nom for nom, valeur in vars(AccountType).items() if nom.isupper()}

MOTIF_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
CHIFFRES_VISIBLES = 4


def traduire_compte(nom_backend: str, compte_woob, investissements=()) -> Compte:
    """Rendre le Compte metabank d'un Account woob et de ses Investment.

    Le numéro complet et l'IBAN ne sont pas repris : seuls les derniers chiffres servent à reconnaître le compte.
    """
    type_woob = _nom_type(_valeur(compte_woob, "type"))
    return Compte(
        source=f"woob:{nom_backend}",
        identifiant=f"{nom_backend}:{compte_woob.id}",
        libelle=_valeur(compte_woob, "label") or compte_woob.id,
        type_compte=TYPES_WOOB.get(type_woob, "autre"),
        solde=_valeur(compte_woob, "balance"),
        devise=_valeur(compte_woob, "currency"),
        numero_masque=masquer_numero(_valeur(compte_woob, "number") or compte_woob.id),
        lignes=tuple(traduire_investissement(investissement) for investissement in investissements),
    )


def traduire_investissement(investissement) -> Ligne:
    """Rendre la Ligne metabank d'un Investment woob (montants dans la devise du compte)."""
    code = _valeur(investissement, "code")
    return Ligne(
        libelle=_valeur(investissement, "label") or code or "?",
        valorisation=_valeur(investissement, "valuation"),
        isin=code if code and MOTIF_ISIN.match(code) else None,
        quantite=_valeur(investissement, "quantity"),
        valeur_unitaire=_valeur(investissement, "unitvalue"),
        prix_revient_unitaire=_valeur(investissement, "unitprice"),
        plus_value=_valeur(investissement, "diff"),
        date_valeur=_valeur(investissement, "vdate"),
    )


def masquer_numero(numero: str | None) -> str | None:
    """Rendre « …1234 » : assez pour reconnaître un compte, sans exposer le numéro."""
    if not numero:
        return None
    chiffres = re.sub(r"\s", "", numero)
    return "…" + chiffres[-CHIFFRES_VISIBLES:]


def _nom_type(valeur) -> str:
    # AccountType est une énumération maison de woob : ses membres sont de simples entiers (PER = 20),
    # sans « .name » ni conversion AccountType(20) ; on retrouve le nom par l'attribut de classe.
    return NOMS_TYPES_WOOB.get(valeur, "UNKNOWN")


def _valeur(objet, champ: str):
    # woob distingue NotLoaded et NotAvailable ; pour l'analyse, les deux signifient « inconnu ».
    valeur = getattr(objet, champ, None)
    return None if empty(valeur) else valeur
