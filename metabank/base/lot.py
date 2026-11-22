"""Lot : ce qu'un connecteur rend après avoir lu un fichier ou interrogé un service, prêt à entrer en base."""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# « ****1234 » : au plus quatre chiffres visibles. Un numéro complet ou un IBAN n'entre jamais en base.
NUMERO_MASQUE = re.compile(r"\*+\d{1,4}")


class LectureImpossible(ValueError):
    """Le connecteur a reconnu le fichier mais ne peut pas le lire (format inattendu, contrôle échoué)."""


@dataclass(frozen=True)
class CompteLu:
    """Un compte tel que la source le décrit.

    Attributes:
        cle: identifiant stable choisi par le connecteur, sans numéro complet (« BNP:courant:****1234 »).
        numero_masque: « ****1234 ».
    """

    cle: str
    titulaire: str
    etablissement: str
    type_compte: str
    numero_masque: str
    libelle: str
    devise: str = "EUR"

    def __post_init__(self) -> None:
        if not NUMERO_MASQUE.fullmatch(self.numero_masque):
            raise ValueError("numéro de compte non masqué : seuls les quatre derniers chiffres sont admis")


@dataclass(frozen=True)
class OperationLue:
    """Un mouvement : montant positif pour une entrée, négatif pour une sortie, dans la devise indiquée.

    Attributes:
        identifiant: stable d'un import à l'autre, unique dans le compte : c'est lui qui écarte les doublons.
    """

    compte_cle: str
    identifiant: str
    jour: date
    libelle: str
    montant: Decimal
    nature: str = ""
    devise: str = "EUR"


@dataclass(frozen=True)
class SoldeLu:
    """Solde du compte à la fin d'un jour, dans la devise indiquée."""

    compte_cle: str
    jour: date
    montant: Decimal
    devise: str = "EUR"


@dataclass(frozen=True)
class Lot:
    """Tout ce qu'un import apporte ; chaque opération et chaque solde se rattache à un compte du lot."""

    connecteur: str
    comptes: tuple[CompteLu, ...] = field(default=())
    operations: tuple[OperationLue, ...] = field(default=())
    soldes: tuple[SoldeLu, ...] = field(default=())

    def __post_init__(self) -> None:
        cles = {c.cle for c in self.comptes}
        orphelins = ({o.compte_cle for o in self.operations} | {s.compte_cle for s in self.soldes}) - cles
        if orphelins:
            raise ValueError(f"comptes absents du lot : {', '.join(sorted(orphelins))}")
