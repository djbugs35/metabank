"""Ce qu'un relevé d'assureur dit d'un contrat, quel que soit l'assureur.

Montants en euros, en Decimal ; None = absent du relevé (différent de zéro).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from metabank.releves.frais_supports import FraisSupport


@dataclass(frozen=True)
class Support:
    """Ligne détenue à la date du relevé : fonds en euros, unité de compte, produit structuré."""

    libelle: str
    valeur: Decimal
    isin: str | None = None
    parts: Decimal | None = None
    valeur_part: Decimal | None = None


@dataclass(frozen=True)
class Frais:
    """Frais prélevés sur l'année, tels que totalisés par l'assureur."""

    sur_operations: Decimal = Decimal(0)
    gestion_unites_compte: Decimal = Decimal(0)
    gestion_fonds_euros: Decimal = Decimal(0)
    total: Decimal = Decimal(0)


@dataclass(frozen=True)
class Mouvements:
    """Synthèse des mouvements de l'année (versements nets de frais, frais à part)."""

    versements_nets: Decimal = Decimal(0)
    frais_versements: Decimal = Decimal(0)
    rachats: Decimal = Decimal(0)
    arbitrages_debit: Decimal = Decimal(0)
    arbitrages_credit: Decimal = Decimal(0)
    frais_arbitrages: Decimal = Decimal(0)
    distributions: Decimal = Decimal(0)
    revalorisation_fonds_euros: Decimal = Decimal(0)
    prelevements_sociaux: Decimal = Decimal(0)

    @property
    def versements_bruts(self) -> Decimal:
        """Rendre ce qui est sorti de la poche de l'épargnant : versement net plus frais d'entrée."""
        return self.versements_nets + self.frais_versements


@dataclass(frozen=True)
class Releve:
    """Relevé d'un contrat à une date : annuel (Suravenir) ou situation ponctuelle (Cardif)."""

    assureur: str
    produit: str
    numero: str
    type_contrat: str
    date_arrete: date
    valeur: Decimal
    supports: tuple[Support, ...]
    valeur_precedente: Decimal | None = None
    mouvements: Mouvements | None = None
    frais: Frais | None = None
    versements_volontaires_annee: Decimal | None = None
    versements_bruts_depuis_origine: Decimal | None = None
    rachats_depuis_origine: Decimal | None = None
    frais_supports: tuple[FraisSupport, ...] = field(default=())
    taux_frais_fonds_euros: Decimal | None = None
    anomalies: tuple[str, ...] = field(default=())
    fichier: str = ""

    @property
    def est_annuel(self) -> bool:
        """Rendre vrai si le relevé couvre une année civile entière (mouvements et frais de l'année)."""
        return self.mouvements is not None
