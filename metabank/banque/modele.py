"""Comptes bancaires (compte courant, Livret A, LDD) et leurs opérations, en euros."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Préfixe du nom de dossier (« CC - BNP - … ») -> type de compte.
TYPES_PAR_PREFIXE = {"CC": "courant", "LA": "livret_a", "LDD": "ldd"}
LIBELLES_TYPES = {"courant": "Compte courant", "livret_a": "Livret A", "ldd": "LDD"}


@dataclass(frozen=True)
class Operation:
    """Une ligne de l'export : montant positif pour une entrée, négatif pour une sortie."""

    jour: date
    type_banque: str
    sous_type: str
    libelle: str
    montant: Decimal


@dataclass(frozen=True)
class Export:
    """Un fichier d'export : le solde à une date, et les opérations qui y mènent."""

    nom: str
    numero_masque: str
    date_solde: date
    solde: Decimal
    operations: tuple[Operation, ...]
    fichier: str = ""


@dataclass(frozen=True)
class Compte:
    """Un compte bancaire, tous ses exports fusionnés : opérations sans doublon, solde du plus récent."""

    titulaire: str
    banque: str
    type_compte: str
    nom: str
    numero_masque: str
    date_solde: date
    solde: Decimal
    operations: tuple[Operation, ...]
    anomalies: tuple[str, ...] = field(default=())

    @property
    def libelle(self) -> str:
        """Rendre « Cédric · Compte courant BNP ****2513 »."""
        return f"{self.titulaire} · {LIBELLES_TYPES.get(self.type_compte, self.type_compte)} {self.banque} {self.numero_masque}"
