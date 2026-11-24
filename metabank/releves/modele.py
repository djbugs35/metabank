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
    # Prix moyen d'achat d'une part, en euros, tel que l'assureur l'imprime (situation Suravenir). MODELE § 13.1.
    prix_de_revient: Decimal | None = None


@dataclass(frozen=True)
class Operation:
    """Une ligne de l'historique des opérations d'un document : jour, nature imprimée, support nommé, montant (€).

    isin : celui du fonds détenu que la ligne nomme, sinon None. Le montant est celui imprimé (signe compris).
    """

    jour: date
    nature: str
    libelle: str
    isin: str | None
    montant: Decimal


@dataclass(frozen=True)
class Distribution:
    """Coupon versé par un fonds (ligne « DISTRIBUTION » de l'historique), en euros. MODELE § 13.1."""

    jour: date
    support: str
    montant: Decimal


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
    # Assurance vie : primes versées et non remboursées au 31/12 (tableau fiscal du relevé annuel), pour mémoire :
    # ce n'est pas le cumul des versements.
    primes_non_remboursees: Decimal | None = None
    # Situation : versements, rachats et frais de son année, lus dans l'historique des opérations. MODELE § 2.4.
    versements_annee_en_cours: Decimal | None = None
    rachats_annee_en_cours: Decimal | None = None
    frais_annee_en_cours: Decimal | None = None
    # Situation : « Performance (+/- value fiscale) en € » imprimée par l'assureur ; elle fait foi. MODELE § 2.3.
    performance_annoncee: Decimal | None = None
    # Situation : coupons de l'historique, clé du support (ISIN, sinon libellé en majuscules). MODELE § 13.1.
    distributions: tuple[Distribution, ...] = field(default=())
    # Historique des opérations imprimé par le document (situation Suravenir), tel quel. MODELE § 0.
    operations: tuple[Operation, ...] = field(default=())
    anomalies: tuple[str, ...] = field(default=())
    fichier: str = ""

    @property
    def est_annuel(self) -> bool:
        """Rendre vrai si le relevé couvre une année civile entière (mouvements et frais de l'année)."""
        return self.mouvements is not None


def cle_du_contrat(numero: str) -> str:
    """Rendre ce qui identifie un contrat d'un document à l'autre : le dernier groupe de son numéro (« 270549974 »).

    Le relevé annuel Suravenir imprime un préfixe (« 0000067935 B7 270549974 »), la situation non (« B7 270549974 ») :
    seul le dernier groupe est commun.
    """
    return numero.rsplit(maxsplit=1)[-1] if numero.strip() else numero
