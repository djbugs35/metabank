"""Historique mensuel du patrimoine sur 13 mois, reconstitué depuis les données en base. MODELE § 8.1.

Aucun instantané n'est stocké : chaque point se refait des soldes, opérations et relevés, comme la base se refait des
archives. Montants en euros.
"""

import calendar
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from metabank.banque.credit import projeter_credit
from metabank.banque.modele import TYPES_COURANTS, Compte
from metabank.releves import ReleveRange
from metabank.releves.modele import cle_du_contrat

ZERO = Decimal(0)
NOMBRE_DE_POINTS = 13
PLACEMENTS, EPARGNE, COURANTS, CREDITS = "Placements", "Épargne disponible", "Comptes courants", "Crédits"


@dataclass(frozen=True)
class PointPatrimoine:
    """Le patrimoine à une date, en euros, sur l'ensemble de comptes et contrats retenu pour toute la courbe."""

    jour: date
    actifs: Decimal
    credits: Decimal

    @property
    def net(self) -> Decimal:
        """Rendre actifs moins crédits, en euros."""
        return self.actifs - self.credits


@dataclass(frozen=True)
class Historique:
    """La courbe, et les comptes ou contrats comptés à leur première valeur avant d'être connus (libellés)."""

    points: list[PointPatrimoine]
    reportes: list[str]
    # Même courbe par famille (« Placements », « Épargne disponible », « Comptes courants », « Crédits »), en euros,
    # crédits en positif : de quoi tracer chaque bloc du tableau de bord.
    familles: dict[str, list[Decimal]] = field(default_factory=dict)


def jours_des_points(aujourd_hui: date, nombre: int = NOMBRE_DE_POINTS) -> list[date]:
    """Rendre la fin de chacun des nombre - 1 mois précédents, puis aujourd'hui, du plus ancien au plus récent."""
    jours = [aujourd_hui]
    annee, mois = aujourd_hui.year, aujourd_hui.month
    for _ in range(nombre - 1):
        annee, mois = (annee - 1, 12) if mois == 1 else (annee, mois - 1)
        jours.append(date(annee, mois, calendar.monthrange(annee, mois)[1]))
    return sorted(jours)


def solde_au(compte: Compte, jour: date) -> Decimal | None:
    """Rendre le solde du compte à la fin du jour, en euros, ou None s'il précède les opérations connues. MODELE § 8.1.

    Un crédit est projeté au-delà de son dernier export (MODELE § 7.10).
    """
    if jour >= compte.date_solde:
        return projeter_credit(compte, jour).solde if compte.type_compte == "credit" else compte.solde
    if not compte.operations or jour < min(o.jour for o in compte.operations) - timedelta(days=1):
        return None
    return compte.solde - sum((o.montant for o in compte.operations if jour < o.jour <= compte.date_solde), ZERO)


def valeur_au(releves: Sequence[ReleveRange], jour: date) -> Decimal | None:
    """Rendre la valeur du dernier relevé daté au plus tard du jour, en euros, ou None s'il n'y en a pas."""
    connus = [r.releve for r in releves if r.releve.date_arrete <= jour]
    return max(connus, key=lambda r: r.date_arrete).valeur if connus else None


def historique_patrimoine(
    releves: Sequence[ReleveRange], comptes: Sequence[Compte], biens: dict, aujourd_hui: date
) -> Historique:
    """Rendre la courbe du patrimoine (fins de mois puis aujourd'hui) et les comptes reportés. MODELE § 8.1.

    Args:
        releves: relevés d'assureurs des contrats retenus (un foyer ou une personne).
        comptes: comptes bancaires et crédits retenus, non projetés.
        biens: {fin du numéro du crédit : {"nom", "valeur"}} saisis dans Corrections ; comptés pour les crédits retenus.
    """
    jours = jours_des_points(aujourd_hui)
    # Un compte sans valeur connue au dernier point est laissé hors de la courbe (MODELE § 8.1).
    lignes = [ligne for ligne in _lignes(releves, comptes, jours) if ligne[2][-1] is not None]
    reportes = [nom for nom, _, valeurs in lignes if valeurs[0] is None]
    completes = [(famille == CREDITS, famille, _reporter(valeurs)) for _, famille, valeurs in lignes]
    immobilier = sum(
        (Decimal(str(biens[c.numero_masque.lstrip("*")]["valeur"])) for c in comptes
         if c.type_compte == "credit" and (biens.get(c.numero_masque.lstrip("*")) or {}).get("valeur")),
        ZERO,
    )  # fmt: skip
    points = [
        PointPatrimoine(
            jour,
            immobilier + sum((v[i] for credit, _, v in completes if not credit), ZERO),
            -sum((v[i] for credit, _, v in completes if credit), ZERO),
        )
        for i, jour in enumerate(jours)
    ]
    familles = {
        nom: [abs(sum((v[i] for _, f, v in completes if f == nom), ZERO)) for i in range(len(jours))]
        for nom in dict.fromkeys(f for _, f, _ in completes)
    }
    return Historique(points, reportes, familles)


def _reporter(valeurs: list[Decimal | None]) -> list[Decimal]:
    """Rendre les valeurs, chaque inconnue de tête remplacée par la première valeur connue (MODELE § 8.1)."""
    premiere = next(v for v in valeurs if v is not None)
    return [premiere if v is None else v for v in valeurs]


def _lignes(releves: Sequence[ReleveRange], comptes: Sequence[Compte], jours: list[date]) -> list[tuple]:
    """Rendre (libellé, famille, montant à chaque jour ou None) pour chaque contrat puis chaque compte."""
    contrats: dict[tuple[str, str], list[ReleveRange]] = {}
    for r in releves:
        contrats.setdefault((r.titulaire, cle_du_contrat(r.releve.numero)), []).append(r)
    lignes: list[tuple] = [
        (f"{titulaire} · {v[0].releve.produit}", PLACEMENTS, [valeur_au(v, j) for j in jours])
        for (titulaire, _), v in contrats.items()
    ]
    lignes += [(c.libelle, _famille(c.type_compte), [solde_au(c, j) for j in jours]) for c in comptes]
    return lignes


def _famille(type_compte: str) -> str:
    if type_compte == "credit":
        return CREDITS
    return COURANTS if type_compte in TYPES_COURANTS else EPARGNE
